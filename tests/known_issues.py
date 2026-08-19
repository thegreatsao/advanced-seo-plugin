#!/usr/bin/env python3
"""Which KNOWN-ISSUES entries still describe this tree.

`KNOWN-ISSUES.md` is the one file in this repository that claims things about the
code and is read by nothing. Every other claim here has a reader: the registry has
`build_checklist --check`, the translations have `i18n_digest --check`, the
thresholds have `audit_thresholds`, and the verdicts have two ledgers. A defect
written down and then repaired leaves its entry standing, and the entry keeps
reading as open for as long as nobody re-runs it by hand.

That is not a hypothesis. Measured on 0.79.0, three entries described a tree that no
longer existed: the privacy and trust links got their boundary in 0.75.0, the private
author and date answers went in 0.77.0, and KW-071 was repointed at
`summary.contested_queries` in 0.43.0 — `v0.42.0` carries the old field and `v0.43.0`
the new one. Each entry outlived its repair because the release that fixed the code had
no reason to open this file.

So each entry in section 6 carries a marker — `<!-- ki: slug -->` — and this
instrument holds a probe beside it. The probe re-runs the entry's own measurement and
records what the tree answers today. `--check` fails when an answer moves, which is
the moment somebody has to decide whether the entry is now wrong or the tree is.

    python tests/known_issues.py                    # measure and report
    python tests/known_issues.py --out FILE         # refresh the record
    python tests/known_issues.py --check FILE       # exit 1 if the record is stale

**What this cannot do.** It does not read prose, and it must not start. The probe is
written by the person writing the entry and asserts nothing about whether the entry's
English is true; it asserts that the number the entry quotes is the number the tree
still produces. An entry whose claim has no executable witness — the polarity one says
so in as many words — carries `why` instead of a probe, and the count of those is
printed, because a ledger where everything is exempt is a ledger that has stopped
working.

The scope is section 6, deliberately, and it is not the whole file. Sections 1 and 4
and 5 are closed narratives; sections 2 and 3 each end on a standing limitation, and
those two are outside this reading — said here so the boundary is a decision somebody
made rather than a place nobody looked. All three of the stale entries found in 0.80.0
were in section 6, which is where entries written in the present tense collect.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, "skills", "seo-checklist")
SCRIPTS = os.path.join(SKILL_DIR, "scripts")
TOOLS = os.path.join(SKILL_DIR, "tools")
REGISTRY = os.path.join(SKILL_DIR, "resources", "config", "checklist.json")
KNOWN_ISSUES = os.path.join(ROOT, "KNOWN-ISSUES.md")
RECORD = os.path.join(ROOT, "tests", "known-issues.json")

sys.path.insert(0, SCRIPTS)
sys.path.insert(0, TOOLS)

MARKER = re.compile(r"^<!-- ki: ([a-z0-9-]+) -->$")
# An entry opens either as a bullet or as a numbered item, and in both cases its
# first words are bold. Nothing else in the file starts a line that way. The `*`
# spelling of a bullet is here although this file does not use it: a scan that knows
# one spelling reports an absence it never looked for.
ENTRY = re.compile(r"^(?:[-*] |\d+\. )\*\*")
SECTION = re.compile(r"^## ")
STATES = ("open", "closed", "history")

# Every probe pins whatever would otherwise move on its own. A date is the obvious
# one: an age in days is a different number tomorrow, and a gate that reddens
# overnight teaches people to re-record it without reading.
PINNED_TODAY = date(2026, 8, 19)
PAGE_URL = "https://example.test/p"
CANONICAL = '<link rel="canonical" href="%s">' % PAGE_URL

_PROBES = {}


def probe(name):
    def register(fn):
        _PROBES[name] = fn
        return fn
    return register


def _registry() -> dict:
    with open(REGISTRY, encoding="utf-8") as stream:
        return json.load(stream)


def _items_by_id() -> dict:
    return {item["id"]: item for item in _registry()["items"]}


def _page(body: str) -> str:
    return ('<!doctype html><html lang="en"><head><title>T</title>'
            + CANONICAL + "</head><body>" + body + "</body></html>")


def _temp_page(body: str) -> str:
    handle = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                         encoding="utf-8")
    handle.write(_page(body))
    handle.close()
    return handle.name


# ── the probes ────────────────────────────────────────────────────────────────

@probe("threshold_declarations")
def _threshold_declarations() -> dict:
    import audit_thresholds

    named, unnamed = audit_thresholds.scan()
    return {
        "counted": len([t for t in named if t["kind"] != "presentation"]),
        "presentation": len([t for t in named if t["kind"] == "presentation"]),
        # The names, not the count. The entry is about four particular constants, and
        # a count of 25 survives judging those four while four others arrive.
        "uncounted": sorted(row["name"] for row in audit_thresholds.scan_uncounted()),
        "unnamed": len(unnamed),
        # Separators are normalised because this record is compared on three
        # platforms. A path recorded as `scripts\\robots_path_tester.py` is a
        # disagreement about Windows, not about the tree.
        "non_numeric_basis": sorted(
            "%s:%s" % (row["file"].replace(os.sep, "/"), row["line"])
            for row in audit_thresholds.scan_non_numeric_basis()),
    }


@probe("rendered_mobile_metrics")
def _rendered_mobile_metrics() -> dict:
    import rendered_audit

    # Sorted, not as declared: the claim is about which measures exist, and an order
    # that came from a set would move on its own and teach people to re-record.
    return {"mobile_metrics": sorted(rendered_audit.MOBILE_METRICS)}


@probe("cn_068_scores_on_the_good_fixture")
def _cn_068_scores() -> dict:
    import eeat_signal_checker

    good = os.path.join(ROOT, "tests", "fixtures", "good")
    scores = {}
    for name in ("index.html", "about.html", "privacy.html"):
        path = os.path.join(good, name)
        if os.path.exists(path):
            scores[name] = eeat_signal_checker.check_eeat(path)["score"]
    item = _items_by_id().get("CN-068", {})
    floor = ((item.get("check") or {}).get("assert") or {}).get("gte")
    return {"scores": scores, "floor": floor}


@probe("thin_assertions")
def _thin_assertions() -> dict:
    """Both halves of the gap, because either half can be the repair.

    The entry says a title promises more than its assertion requires. Recording only
    the assertion would let somebody bring the title down to the assertion — the other
    way to close it — and leave this reading green on an entry that had become false.
    """
    items = _items_by_id()
    return {item_id: {"title": items[item_id]["title"],
                      "assert": (items[item_id]["check"] or {}).get("assert")}
            for item_id in ("AR-152", "CN-056")}


@probe("severity_vocabulary_proofs")
def _severity_vocabulary_proofs() -> dict:
    import audit_reachability

    proved = sorted(item_id for item_id, proof in audit_reachability.proofs().items()
                    if proof.get("mechanism") == "severity_vocabulary")
    return {"items_proved": proved}


@probe("kw_071_assertion")
def _kw_071_assertion() -> dict:
    """The item, and the whole registry's use of the field it used to assert.

    The entry says `worst_spread` is gone from the contract, which is a claim about
    215 items and not about one: attaching the old field to a different item would
    leave a KW-071-only reading green.
    """
    item = _items_by_id()["KW-071"]
    with open(REGISTRY, encoding="utf-8") as stream:
        whole = stream.read()
    return {"title": item["title"],
            "assert": item["check"].get("assert"),
            "warn": item["check"].get("warn"),
            "items_naming_worst_spread": [
                other["id"] for other in _registry()["items"]
                if "worst_spread" in json.dumps(other.get("check") or {})],
            "worst_spread_anywhere_in_the_registry": "worst_spread" in whole}


@probe("eeat_reviewed_languages")
def _eeat_reviewed_languages() -> dict:
    """The reviewed vocabularies, and what a page in an unreviewed language is graded on.

    Listing the three languages says nothing about the half of the entry that matters:
    that everything outside them is graded on English alone. Two identical pages, one
    declaring a reviewed language and one declaring German, answer that by scoring the
    same — the German page is being read with the English vocabulary.
    """
    import eeat_signal_checker

    body = ('<h1>Our kitchen</h1><p>Reviewed by a certified expert with fifteen years '
            'of experience. In our own tests we baked this every week.</p>'
            '<a href="/privacy">Privacy policy</a><a href="/about">About us</a>'
            '<a href="mailto:hello@example.test">Contact</a>')
    read = {}
    for lang in ("en", "de", "lt"):
        page = _page(body).replace('<html lang="en">', '<html lang="%s">' % lang)
        handle = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                             encoding="utf-8")
        handle.write(page)
        handle.close()
        result = eeat_signal_checker.check_eeat(handle.name)
        signals = result["signals"]
        read[lang] = {"score": result["score"],
                      "credential_markers": len(signals["credential_markers"]),
                      "privacy_links": len(signals["privacy_links"]),
                      "trust_links": len(signals["trust_links"])}
    return {"languages": sorted(eeat_signal_checker._TERMS["languages"]),
            "one_english_page_read_under_each_declared_language": read}


@probe("ci_002_title")
def _ci_002_title() -> dict:
    """The title and what the item is run with.

    The open half is that no site-wide indexation claim is made, and a title alone
    cannot witness that: the arguments are where a set of URLs would have to appear.
    """
    item = _items_by_id()["CI-002"]
    return {"title": item["title"],
            "script": item["check"]["script"],
            "args": item["check"]["args"]}


@probe("negative_polarity_share")
def _negative_polarity_share() -> dict:
    """The share the polarity entry quotes, with the definition its prose gives.

    "Passing requires a path to be absent or bounded" is the whole rule, and it has
    nine spellings in this registry. The entry quoted 74 of 215 and left the
    spellings to the reader, so the number could not be re-derived from the file it
    describes — recovering it took a search over candidate definitions. That is the
    defect this instrument exists to stop, applied to itself.
    """
    def bounded(block) -> bool:
        if not isinstance(block, dict):
            return False
        return bool(block.get("falsy") or block.get("none_matching")
                    or block.get("none_severity")
                    or block.get("eq") == 0 or block.get("len_eq") == 0
                    or "lt" in block or "lte" in block or "len_lte" in block
                    or "count_matching_lte" in block)

    items = _registry()["items"]
    negative = [item for item in items
                if any(bounded((item.get("check") or {}).get(block))
                       for block in ("assert", "warn"))]
    return {"items": len(items), "negative_polarity": len(negative)}


@probe("gsc_threshold_values")
def _gsc_threshold_values() -> dict:
    import gsc_cannibalization
    import gsc_checker
    import gsc_links_csv

    import audit_thresholds

    wanted = {
        "STRIKING_DISTANCE_MIN_POSITION": gsc_checker,
        "STRIKING_DISTANCE_MAX_POSITION": gsc_checker,
        "STRIKING_DISTANCE_MIN_IMPRESSIONS": gsc_checker,
        "TOP_POSITION_MAX": gsc_checker,
        "LOW_CTR_PCT": gsc_checker,
        "VERY_LOW_CTR_PCT": gsc_checker,
        "RANKS_FIRST_POSITION": gsc_cannibalization,
        "HIGH_SEVERITY_IMPRESSIONS": gsc_cannibalization,
        "TOP1_SHARE_PCT": gsc_links_csv,
    }
    # The value alone is the weaker half of the claim. "Deliberately not calibrated"
    # is about the basis each one declares, and relabelling one `measured` without
    # touching its value is exactly the move this entry says has not been made.
    kind = {row["name"]: row["kind"] for row in audit_thresholds.scan()[0]}
    return {name: {"value": getattr(module, name), "basis": kind.get(name)}
            for name, module in sorted(wanted.items())}


def _css_calibration() -> dict:
    path = os.path.join(TOOLS, "calibration", "css-minification.json")
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


@probe("css_minification_corpus")
def _css_minification_corpus() -> dict:
    data = _css_calibration()
    distributions = data["signal_distributions"]["bytes_per_line"]["by_package"]
    return {
        "pairs": data["counts"]["pairs"],
        "bulma_minified_min": distributions["bulma"]["minified"]["min"],
        "codicons_source_median": distributions["@vscode/codicons"]["source"]["p50"],
    }


@probe("wasted_bytes_definition")
def _wasted_bytes_definition() -> dict:
    """What the field counts, not only what the corpus measured.

    The corpus figures are the entry's evidence; its claim is about the shipped
    field. Redefining `wasted_bytes` to charge for compressed bytes would leave a
    corpus-only reading green, so the fraction it multiplies, the threshold it
    reports against and the fields it declares are recorded beside them.
    """
    import css_minify_check

    shapes = os.path.join(SKILL_DIR, "resources", "references", "script-output-shapes.md")
    with open(shapes, encoding="utf-8") as stream:
        text = stream.read()
    section = text.split("### css_minify_check.py", 1)[1].split("\n### ", 1)[0]
    fields = re.findall(r"^`([^`]+)`", section, flags=re.M)
    return {
        "pairs": _css_calibration()["counts"]["pairs"],
        "savings_fraction": css_minify_check.MINIFICATION_SAVINGS_FRACTION,
        "warn_threshold": css_minify_check.WASTED_BYTES_WARN,
        "declared_fields": fields,
    }


@probe("go_138_matches_a_field")
def _go_138_matches_a_field() -> dict:
    return {"assert": _items_by_id()["GO-138"]["check"].get("assert")}


@probe("russian_item_coverage")
def _russian_item_coverage() -> dict:
    path = os.path.join(SKILL_DIR, "resources", "i18n", "ru.json")
    with open(path, encoding="utf-8") as stream:
        russian = json.load(stream)
    ids = {item["id"] for item in _registry()["items"]}
    # Both maps by id, not by length. Two maps of the right size can disagree about
    # which items they cover, and the entry claims coverage.
    return {
        "registry_items": len(ids),
        "item_titles": len(russian["item_titles"]),
        "item_fixes": len(russian["item_fixes"]),
        "ids_with_no_title": sorted(ids - set(russian["item_titles"])),
        "ids_with_no_fix": sorted(ids - set(russian["item_fixes"])),
        "translated_ids_not_in_the_registry":
            sorted((set(russian["item_titles"]) | set(russian["item_fixes"])) - ids),
    }


@probe("freshness_foreign_dates")
def _freshness_foreign_dates() -> dict:
    import freshness_checker

    stamp = '<time datetime="2019-03-01">1 March 2019</time>'
    shapes = {
        "class_named_comment": '<h1>H</h1><p>Body.</p><div class="comment">%s</div>' % stamp,
        "h_cite_comment": '<h1>H</h1><p>Body.</p><div class="h-cite">%s</div>' % stamp,
        "declared_itemprop_comment": (
            '<article itemscope itemtype="https://schema.org/Article"><h1>H</h1>'
            '<p>Body.</p><div itemprop="comment" itemscope '
            'itemtype="https://schema.org/Comment">%s</div></article>' % stamp),
    }
    out = {}
    for label, body in shapes.items():
        result = freshness_checker.check_freshness(_temp_page(body), today=PINNED_TODAY)
        out[label] = {"age_days": result["age_days"], "latest_date": result["latest_date"]}
    return out


@probe("credit_boundary_and_itemref")
def _credit_boundary_and_itemref() -> dict:
    import seo_common

    referenced_out = ('<div itemprop="comment" itemref="c1"></div>'
                      '<span id="c1" class="author">D Petras</span>')
    nested_claimed = ('<div itemprop="comment"><span id="b1" class="author">'
                      'M Kazlauskiene</span></div><article itemscope itemref="b1"></article>')
    return {
        "referenced_byline_outside_the_comment":
            seo_common.page_author_names(seo_common.parse_html(_page(referenced_out), PAGE_URL)),
        "page_byline_nested_in_the_comment":
            seo_common.page_author_names(seo_common.parse_html(_page(nested_claimed), PAGE_URL)),
    }


@probe("class_named_comment_author")
def _class_named_comment_author() -> dict:
    import seo_common

    body = '<div class="comment"><span class="author">D Petras</span></div>'
    return {"authors": seo_common.page_author_names(
        seo_common.parse_html(_page(body), PAGE_URL))}


@probe("privacy_and_trust_links_boundary")
def _privacy_and_trust_links_boundary() -> dict:
    import eeat_signal_checker

    body = ('<article itemscope itemtype="https://schema.org/Article">'
            '<h1>Unauthored</h1><p>Body text about the topic.</p>'
            '<div itemprop="comment" itemscope itemtype="https://schema.org/Comment">'
            '<span class="author">D Petras</span>'
            '<a href="mailto:commenter@example.com">write me</a>'
            '<a href="/privacy">Privacy policy</a></div></article>')
    signals = eeat_signal_checker.check_eeat(_temp_page(body))["signals"]
    return {
        "authors": signals["authors"],
        "privacy_links": len(signals["privacy_links"]),
        "trust_links": len(signals["trust_links"]),
        "policy_links": len(signals["policy_links"]),
    }


@probe("article_seo_shares_the_answers")
def _article_seo_shares_the_answers() -> dict:
    import article_seo
    import seo_common

    shapes = {
        "author_grid": ('<div class="author-grid"><p>Meet the team</p>'
                        '<p>Recipes by many hands</p></div><h1>H</h1><p>Body.</p>'),
        "published_widget": ('<div class="published-widget"><p>Newsletter</p>'
                             '<p>Sign up</p></div><h1>H</h1><p>Body.</p>'),
    }
    out = {}
    for label, body in shapes.items():
        parsed = seo_common.parse_html(_page(body), PAGE_URL)
        content = article_seo.extract_content(parsed, "unknown")
        out[label] = {"authors": content["authors"], "publish_date": content["publish_date"]}

    fixtures = sorted((os.path.join(folder, name)
                       for folder, _, names in os.walk(os.path.join(ROOT, "tests", "fixtures"))
                       for name in names if name.endswith(".html")))
    divergent = []
    for path in fixtures:
        with open(path, encoding="utf-8", errors="replace") as stream:
            parsed = seo_common.parse_html(stream.read(), "")
        content = article_seo.extract_content(parsed, "unknown")
        dates = seo_common.declared_publication_dates(parsed)
        if (content["authors"] != seo_common.page_author_names(parsed)
                or content["publish_date"] != (dates[0] if dates else "")):
            divergent.append(os.path.relpath(path, ROOT).replace(os.sep, "/"))
    out["fixtures"] = len(fixtures)
    out["divergent_fixtures"] = divergent
    return out


@probe("foreign_credit_keys")
def _foreign_credit_keys() -> dict:
    import seo_common

    body = ('<article itemscope itemtype="https://schema.org/Article">'
            '<div itemprop="about" itemscope itemtype="https://schema.org/Book">'
            '<span class="author">Herman Melville</span></div></article>')
    return {
        "keys": sorted(seo_common.FOREIGN_CREDIT_KEYS),
        "author_of_a_book_the_page_is_about":
            seo_common.page_author_names(seo_common.parse_html(_page(body), PAGE_URL)),
    }


# ── the file, the record, and the comparison ──────────────────────────────────

def entries_in_the_file(path: str = KNOWN_ISSUES) -> list[dict]:
    """Every section 6 entry, in file order, with the marker that closes it.

    The marker sits at the end of the entry and indented into it, which is the one
    placement that changes nothing about how the file renders: an HTML comment at
    column 0 between two list items ends the list, and two of these entries are a
    numbered pair whose numbering that would restate.

    An entry with no marker is reported with `slug: None`, not skipped. A scan that
    passes silently over what it cannot read is the failure this whole file is about.
    """
    with open(path, encoding="utf-8") as stream:
        lines = stream.read().splitlines()
    found, in_section = [], False
    for number, line in enumerate(lines, start=1):
        if SECTION.match(line):
            in_section = line.startswith("## 6.")
            continue
        if not in_section:
            continue
        if ENTRY.match(line):
            found.append({"slug": None, "line": number, "lead": line.strip()[:90]})
            continue
        match = MARKER.match(line.strip())
        if match and found:
            if found[-1]["slug"] is not None:
                found.append({"slug": match.group(1), "line": number,
                              "lead": "second marker on one entry"})
            else:
                found[-1]["slug"] = match.group(1)
    return found


def measure(names: list[str] | None = None) -> dict:
    return {name: _PROBES[name]() for name in (names or sorted(_PROBES))}


def build(previous: dict | None = None) -> dict:
    """Refresh the record, keeping every judgement a person wrote into it."""
    previous = previous or {}
    old = previous.get("entries", {})
    entries = {}
    for found in entries_in_the_file():
        slug = found["slug"]
        if slug is None:
            continue
        kept = dict(old.get(slug, {}))
        kept.setdefault("state", "unclassified")
        kept.setdefault("claim", "")
        kept.setdefault("probe", None)
        if kept["probe"]:
            kept["measured"] = _PROBES[kept["probe"]]()
        else:
            kept.pop("measured", None)
            kept.setdefault("why", "")
        entries[slug] = kept
    probed = [e for e in entries.values() if e["probe"]]
    return {
        "entry_count": len(entries),
        "probed_entry_count": len(probed),
        "unprobed_entry_count": len(entries) - len(probed),
        "entries": entries,
    }


def differences(record: dict) -> list[str]:
    """Every way the record and the file can have come apart, named."""
    problems = []
    found = entries_in_the_file()
    unmarked = [f for f in found if f["slug"] is None]
    for entry in unmarked:
        problems.append("KNOWN-ISSUES.md:%d has no `<!-- ki: slug -->` marker: %s"
                        % (entry["line"], entry["lead"]))
    slugs = [f["slug"] for f in found if f["slug"]]
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    for slug in duplicates:
        problems.append("marker %r is used more than once" % slug)

    recorded = record.get("entries", {})
    for slug in sorted(set(slugs) - set(recorded)):
        problems.append("entry %r is in KNOWN-ISSUES.md and not in the record" % slug)
    for slug in sorted(set(recorded) - set(slugs)):
        problems.append("entry %r is in the record and not in KNOWN-ISSUES.md" % slug)

    # A probe nothing references is a probe that stopped being a witness without
    # anybody deciding to stop witnessing.
    referenced = {entry.get("probe") for entry in recorded.values() if entry.get("probe")}
    for name in sorted(set(_PROBES) - referenced):
        problems.append("probe %r is defined and no entry uses it" % name)

    for slug in sorted(set(slugs) & set(recorded)):
        entry = recorded[slug]
        if entry.get("state") not in STATES:
            problems.append("entry %r has state %r, which is not one of %s"
                            % (slug, entry.get("state"), ", ".join(STATES)))
        if not entry.get("claim"):
            problems.append("entry %r records no claim" % slug)
        name = entry.get("probe")
        if not name:
            if not entry.get("why"):
                problems.append("entry %r has neither a probe nor a reason for having none"
                                % slug)
            continue
        if name not in _PROBES:
            problems.append("entry %r names probe %r, which does not exist" % (slug, name))
            continue
        now = _PROBES[name]()
        if now != entry.get("measured"):
            problems.append(
                "entry %r no longer measures what it recorded.\n"
                "      recorded: %s\n"
                "      measured: %s"
                % (slug, json.dumps(entry.get("measured"), sort_keys=True),
                   json.dumps(now, sort_keys=True)))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Re-run what KNOWN-ISSUES section 6 says about this tree",
        epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", metavar="FILE", help="write the refreshed record")
    parser.add_argument("--check", metavar="FILE", nargs="?", const=RECORD,
                        help="exit 1 if the record and the tree disagree")
    args = parser.parse_args(argv)

    if args.check:
        with open(args.check, encoding="utf-8") as stream:
            record = json.load(stream)
        problems = differences(record)
        for problem in problems:
            print("  " + problem)
        if problems:
            print("\n%d disagreement(s) between KNOWN-ISSUES.md and the tree it describes."
                  "\nRead the entry, decide whether the tree moved or the entry is now "
                  "wrong, then re-record with\n  python tests/known_issues.py --out %s"
                  % (len(problems), os.path.relpath(args.check, ROOT).replace(os.sep, "/")))
            return 1
        print("%d entries, %d with a probe, all in step with the tree."
              % (record["entry_count"], record["probed_entry_count"]))
        return 0

    previous = {}
    if os.path.exists(RECORD):
        with open(RECORD, encoding="utf-8") as stream:
            previous = json.load(stream)
    record = build(previous)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        print("wrote %s" % os.path.relpath(args.out, ROOT).replace(os.sep, "/"))

    by_state = {}
    for entry in record["entries"].values():
        by_state[entry["state"]] = by_state.get(entry["state"], 0) + 1
    print("%d entries in section 6:" % record["entry_count"])
    for state in sorted(by_state):
        print("  %-14s %3d" % (state, by_state[state]))
    print("\n%d carry a probe; %d carry a written reason for having none."
          % (record["probed_entry_count"], record["unprobed_entry_count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
