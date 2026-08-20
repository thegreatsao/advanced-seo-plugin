#!/usr/bin/env python3
"""Assess citation and entity readiness for AI answers."""

from __future__ import annotations

import argparse
import json
import re
from urllib.parse import urlparse

from seo_common import (
    CONTRIBUTION_KEYS,
    load_source,
    page_author_names,
    page_nodes,
    parse_html,
    under_foreign_credit,
)


CLAIM_RE = re.compile(
    r"(\d+(?:\.\d+)?%|\$[\d,.]+|\b(?:20\d{2}|19\d{2})\b|"
    r"\b(?:study|research|survey|report|data|according to|found that|shows that|largest|first|only|most)\b)",
    re.I,
)
HIGH_TRUST_HOST_RE = re.compile(
    r"((^|\.)gov(\.|$)|(^|\.)edu$|who\.int$|nih\.gov$|cdc\.gov$|worldbank\.org$|oecd\.org$|wikipedia\.org$)",
    re.I,
)


# Which of somebody else's nodes this reader stops at, and why it is neither
# CONTRIBUTION_KEYS nor FOREIGN_CREDIT_KEYS.
#
# 0.68 gave this reader the narrow set with a reason: "the reviewed book is what a
# review page is about, and its Wikidata sameAs is the page's best evidence that its
# subject resolves". That holds, and `itemReviewed` and `isBasedOn` keep their place on
# it — a derivative work's subject is the work it derives from. It was written about
# one key and does not carry to the third. **A page is not about the works it cites.**
#
# Measured before this was changed: a page about nothing in particular that declares
# four `citation` nodes with DOIs took the whole 20-point entity component — a third of
# the floor of 60 that GO-145 and GEO-005 assert, both `high` — for identifiers that
# resolve somebody else's work. No test asserted that behaviour, which is how it lasted.
#
# `citation` is not merely dropped. `claim_coverage` below counts `cite`, `blockquote`
# and footnote links out of the DOM and has never read JSON-LD, so deleting the key here
# would make a machine-readable bibliography worth nothing on an item called *Content is
# citation-ready for AI search*. It moves to the component whose name it already carries:
# `_schema_citations` counts it into `citation_capacity`.
ENTITY_EXCLUDE = CONTRIBUTION_KEYS | {"citation"}


def _schema_entity_signals(schema_items: list, protected=frozenset()) -> dict:
    """The entities the page declares as its own, and the subject it is about.

    `protected` is the `mainEntityOfPage` exemption, and it is threaded here for the
    same reason the author, reviewer and date readers thread it: a node the page itself
    declares to be its subject stays the page's own however it is referenced. Without
    it, an `Organization` claimed by an `acceptedAnswer` is dropped even where the page
    says in as many words that the node is what it is about.
    """
    names = set()
    same_as = set()
    types = set()
    for item in schema_items:
        for node in page_nodes(item, exclude=ENTITY_EXCLUDE,
                               hoisted=ENTITY_EXCLUDE, protected=protected):
            if node.get("@type"):
                types.add(str(node["@type"]))
            if node.get("name"):
                names.add(str(node["name"]))
            value = node.get("sameAs")
            if isinstance(value, str):
                same_as.add(value)
            elif isinstance(value, list):
                same_as.update(str(v) for v in value)
    return {"types": sorted(types), "names": sorted(names), "sameAs": sorted(same_as)}


def _schema_citations(schema_items: list, protected=frozenset()) -> int:
    """How many works the page's own nodes declare they cite.

    Read through the same boundary as the entity signals, so a work cited inside a
    customer's review is not counted as a citation the page made. The node the key
    points at is never descended into — one `citation` value is one declared citation
    whether it is written out in place or hoisted into `@graph` behind an `@id`.

    Two behaviours are deliberate rather than overlooked, both measured:

    * **the same work cited twice counts twice.** So do two `<cite>` tags naming one
      source and two links to one URL, and this number joins theirs in
      `citation_capacity`. Deduplicating here alone would make one of the four sources
      count differently from the other three;
    * **a `citation` under an excluded key is never counted, however the page declares
      that node its own.** The `mainEntityOfPage` exemption is an `@id` mechanism: it
      readmits a *hoisted* node the page names, and a node written out in place under
      `review` is neither hoisted nor, usually, carrying an `@id` at all. That is a
      property of `page_nodes` and it is shared by all four readers of this graph, not
      something this counter introduces.
    """
    total = 0
    for item in schema_items:
        for node in page_nodes(item, exclude=ENTITY_EXCLUDE,
                               hoisted=ENTITY_EXCLUDE, protected=protected):
            value = node.get("citation")
            if isinstance(value, list):
                total += sum(1 for entry in value if entry)
            elif value:
                total += 1
    return total


def check_citation_readiness(source: str, timeout: int = 15) -> dict:
    html, url, fetched = load_source(source, timeout)
    parsed = parse_html(html, url)
    soup = parsed["soup"]
    page_host = urlparse(url).netloc if url else ""

    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", parsed.get("body_text", "")) if sentence.strip()]
    factual_claims = [sentence for sentence in sentences if CLAIM_RE.search(sentence)]
    external_links = []
    trusted_links = []
    for link in parsed.get("links", []):
        host = urlparse(link.get("href", "")).netloc
        if not host or host == page_host:
            continue
        external_links.append(link)
        if HIGH_TRUST_HOST_RE.search(host):
            trusted_links.append(link)

    cite_tags = [tag.get_text(" ", strip=True)
                 for tag in soup.find_all(["cite", "blockquote"])
                 if not under_foreign_credit(
                     tag, claimed=parsed.get("foreign_itemref_ids"))]
    footnote_links = [
        link for link in parsed.get("links", [])
        if re.search(r"(footnote|reference|citation|source)", " ".join(map(str, link.get("rel", []))) + " " + link.get("href", ""), re.I)
    ]
    page_own = parsed.get("page_own_ids", frozenset())
    schema_items = parsed.get("page_schema", [])
    entity_signals = _schema_entity_signals(schema_items, protected=page_own)
    schema_citations = _schema_citations(schema_items, protected=page_own)
    # The substring match handed a layout class fifteen points on the score GO-145
    # and GEO-005 both assert; page_author_names uses only vocabulary tokens to name
    # a byline.
    #
    # Author credits now come from the shared source used by eeat_signal_checker. No
    # fallback `or` belongs here: page_author_names already reads byline classes.
    author_signals = bool(page_author_names(parsed))

    citation_capacity = (len(external_links) + len(cite_tags)
                         + len(footnote_links) + schema_citations)
    claim_coverage = min(1.0, citation_capacity / max(1, len(factual_claims)))
    score = 0
    score += int(claim_coverage * 35)
    score += min(20, len(trusted_links) * 5)
    score += 15 if author_signals else 0
    score += min(20, len(entity_signals["sameAs"]) * 5)
    score += 10 if parsed.get("canonical") else 0

    issues = []
    if factual_claims and citation_capacity < len(factual_claims):
        issues.append({"severity": "warning", "message": "Factual claims outnumber visible citation/source signals."})
    if not trusted_links:
        issues.append({"severity": "info", "message": "No high-trust external source domains detected."})
    if not author_signals:
        issues.append({"severity": "warning", "message": "No clear author or byline signal detected."})
    if not entity_signals["sameAs"]:
        issues.append({"severity": "info", "message": "No sameAs entity links found in JSON-LD."})

    return {
        "url": url or source,
        "score": min(100, score),
        "factual_claims": len(factual_claims),
        "claim_samples": factual_claims[:10],
        "citation_signals": {
            "external_links": len(external_links),
            "trusted_external_links": len(trusted_links),
            "cite_or_blockquote_tags": len(cite_tags),
            "footnote_links": len(footnote_links),
            "schema_citations": schema_citations,
        },
        "entity_signals": entity_signals,
        "issues": issues,
        "fetch_error": fetched.get("error"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Assess source, claim, author, and entity citation readiness.")
    parser.add_argument("source", help="URL or local HTML file")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    args = parser.parse_args()

    result = check_citation_readiness(args.source, args.timeout)
    print(json.dumps(result, indent=2) if args.json else f"Score: {result['score']} Claims: {result['factual_claims']}")


if __name__ == "__main__":
    main()
