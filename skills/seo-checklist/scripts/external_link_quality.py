#!/usr/bin/env python3
"""Audit external links for status, redirects, rel attributes, and trust patterns."""

from __future__ import annotations

import argparse
from collections import Counter
from urllib.parse import urlparse

from seo_common import (DEAD_FETCH_ERROR_KINDS, fetch_url, normalize_url,
                        parse_html, print_json_or_text, same_host)


# basis: inherited — 200 distinct external links, present at import as a default
#  argument, which is where no instrument could see it. BL-083 passes when
#  `summary.broken_links` is 0, and that is a count over these 200; the links past
#  them were never requested. Named here so the cap is visible and `truncated`
#  says when it bit.
DEFAULT_MAX_LINKS = 200

LOW_TRUST_HOST_HINTS = (
    "bit.ly",
    "goo.gl",
    "tinyurl.com",
    "t.co",
    "ow.ly",
    "buff.ly",
    "linktr.ee",
    "adf.ly",
    "clickbank.net",
)


def extract_external_links(html: str, page_url: str, site_url: str) -> list[dict]:
    parsed = parse_html(html, page_url)
    output = []
    for link in parsed.get("links", []):
        href = link.get("href") or ""
        if not href or same_host(site_url, href):
            continue
        rel = [str(v).lower() for v in (link.get("rel") or [])]
        output.append(
            {
                "source": page_url,
                "url": normalize_url(href, page_url),
                "anchor": link.get("text") or "",
                "rel": rel,
                "nofollow": "nofollow" in rel,
                "sponsored": "sponsored" in rel,
                "ugc": "ugc" in rel,
            }
        )
    return output


def _is_dead(error_kind: str | None) -> bool:
    return error_kind in DEAD_FETCH_ERROR_KINDS


def _check_external_url(url: str, timeout: int) -> dict:
    head = fetch_url(url, method="HEAD", timeout=timeout, allow_redirects=True, max_bytes=0)
    if head.get("status") in (405, 403, None) and head.get("error"):
        return fetch_url(url, method="GET", timeout=timeout, allow_redirects=True, max_bytes=200_000)
    return head


def audit_external_links(urls: list[str], check_status: bool = True, timeout: int = 15,
                         max_links: int = DEFAULT_MAX_LINKS) -> dict:
    pages = []
    links = []
    errors = []
    for source in urls:
        source_url = normalize_url(source)
        fetched = fetch_url(source_url, timeout=timeout, max_bytes=2_000_000)
        pages.append({"url": source_url, "status": fetched.get("status"),
                      "error": fetched.get("error"),
                      "error_kind": fetched.get("error_kind")})
        if fetched.get("status") != 200 or not fetched.get("text"):
            errors.append({"url": source_url, "status": fetched.get("status"),
                           "error": fetched.get("error"),
                           "error_kind": fetched.get("error_kind")})
            continue
        links.extend(extract_external_links(fetched["text"], fetched.get("url") or source_url, source_url))

    deduped = {}
    for link in links:
        deduped.setdefault(link["url"], link)

    # The cap this script has always had, now reported. It was the one of the
    # thirteen assertions over a capped input that did not even say it had capped:
    # a page with 500 distinct outbound links had 300 of them never requested, and
    # BL-083 read `broken_links: 0` off the other 200 as "no broken external links".
    # `unique_external_links` and `checked_links` were both already in the summary,
    # so the fact was derivable and nothing derived it.
    capped = list(deduped.values())[:max_links] if max_links else list(deduped.values())
    truncated = len(capped) < len(deduped)

    checked = []
    for link in capped:
        row = dict(link)
        host = urlparse(link["url"]).netloc.lower()
        row["host"] = host
        row["low_trust_pattern"] = any(host == hint or host.endswith(f".{hint}") for hint in LOW_TRUST_HOST_HINTS)
        if check_status:
            fetched = _check_external_url(link["url"], timeout=timeout)
            row["status"] = fetched.get("status")
            row["final_url"] = fetched.get("url")
            row["redirect_chain"] = fetched.get("redirect_chain", [])
            row["error"] = fetched.get("error")
            row["error_kind"] = fetched.get("error_kind")
        checked.append(row)

    # An error kind says whether no status is evidence about the link. Before that
    # typed contract this guessed from Requests/urllib3 prose, so changing an error
    # message could make the same dead domain stop counting. Resolution, refusal and
    # TLS failures are link defects; our policy and robots refusals are not.
    #
    # A timeout is deliberately not in that set. It means the request did not finish,
    # which is a fact about this run rather than about the link, and calling it broken
    # would put a slow host in a client's fix list as a dead one.
    unreachable = [link for link in checked
                   if link.get("status") is None
                   and _is_dead(link.get("error_kind"))]
    unchecked = [link for link in checked
                 if link.get("status") is None
                 and not _is_dead(link.get("error_kind"))]
    broken = [link for link in checked
              if (link.get("status") and link["status"] >= 400)] + unreachable
    redirects = [link for link in checked if link.get("redirect_chain")]
    low_trust = [link for link in checked if link.get("low_trust_pattern")]
    commercial_without_rel = [link for link in checked
                              if not (link.get("nofollow") or link.get("sponsored")
                                      or link.get("ugc")) and _looks_commercial(link)]
    hosts = Counter(link["host"] for link in checked if link.get("host"))
    issues = []
    if broken:
        issues.append({"severity": "error", "type": "broken_external_links", "count": len(broken),
                       "message": "External links are dead: 4xx/5xx, resolution, "
                                  "connection refusal or TLS failure"})
    if unchecked:
        # Reported, and not as a defect in the site: the run could not settle these,
        # which is the honest thing to say about them.
        issues.append({"severity": "info", "type": "unchecked_external_links",
                       "count": len(unchecked),
                       "message": "External links could not be checked (timeout, "
                                  "policy, robots or an unclassified failure)"})
    if redirects:
        issues.append({"severity": "warning", "type": "redirecting_external_links", "count": len(redirects), "message": "External links redirect"})
    if low_trust:
        issues.append({"severity": "warning", "type": "low_trust_patterns", "count": len(low_trust), "message": "External links match shortener or low-trust host patterns"})
    if commercial_without_rel:
        issues.append({"severity": "info", "type": "commercial_rel_review", "count": len(commercial_without_rel), "message": "Commercial-looking links may need rel=sponsored/nofollow review"})

    return {
        "sources": urls,
        "pages": pages,
        "summary": {
            "external_links_found": len(links),
            "unique_external_links": len(deduped),
            "checked_links": len(checked),
            # BL-083 reads `broken_links`. `unreachable_links` is the subset of it
            # that answered nothing at all, kept separate so a fix list can say
            # "this domain is gone" rather than "this link returns 404".
            "broken_links": len(broken),
            "unreachable_links": len(unreachable),
            "unchecked_links": len(unchecked),
            "redirecting_links": len(redirects),
            "low_trust_pattern_links": len(low_trust),
            "commercial_rel_review": len(commercial_without_rel),
        },
        # Read by the runner: an assertion that passes by finding none of the bad
        # thing must not pass over links nobody requested.
        # True for either reason an answer can rest on less than the whole input:
        # links past `--max-links` were never requested, and links in `unchecked`
        # were requested and answered nothing that decides them. `unreachable` is
        # not here — a dead host is a finding, and it is already counted as broken.
        "truncated": truncated or bool(unchecked),
        "top_external_hosts": [{"host": host, "count": count} for host, count in hosts.most_common(25)],
        "links": checked,
        "issues": issues,
        "errors": errors,
        # `errors` is per-source-page and stays that way. This says the audit read no
        # page at all, which is different from "no external link was broken" — and
        # BL-083 was reporting the second when the first was true.
        "fetch_error": None if any(p.get("status") == 200 for p in pages)
                       else "no source page could be read",
    }


def _looks_commercial(link: dict) -> bool:
    text = f"{link.get('anchor', '')} {link.get('url', '')}".lower()
    return any(token in text for token in ("affiliate", "sponsor", "coupon", "deal", "promo", "ref=", "utm_medium=affiliate"))


def _read_url_file(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.lstrip().startswith("#")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit external link quality")
    parser.add_argument("url", nargs="?", help="Page URL to audit")
    parser.add_argument("--url-file", help="File containing page URLs to audit")
    parser.add_argument("--no-check-status", action="store_true", help="Skip status/redirect checks")
    parser.add_argument("--max-links", type=int, default=DEFAULT_MAX_LINKS,
                        help="Maximum unique external links to check")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    args = parser.parse_args()

    urls = []
    if args.url:
        urls.append(args.url)
    if args.url_file:
        urls.extend(_read_url_file(args.url_file))
    if not urls:
        parser.error("Provide a URL or --url-file")

    result = audit_external_links(urls, check_status=not args.no_check_status, timeout=args.timeout, max_links=args.max_links)
    lines = [
        f"External link quality audit for {len(urls)} page(s)",
        (
            f"Unique external links: {result['summary']['unique_external_links']}  "
            f"Broken: {result['summary']['broken_links']}  "
            f"Redirects: {result['summary']['redirecting_links']}"
        ),
    ]
    lines.extend(f"[{issue['severity']}] {issue['message']}: {issue['count']}" for issue in result["issues"])
    print_json_or_text(result, args.json, lines)


if __name__ == "__main__":
    main()
