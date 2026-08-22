#!/usr/bin/env python3
"""
Detect keyword cannibalization and branded-query ownership from Search Console.

Two checks no crawler can make, because both need real query data:

  cannibalization — one query pulling impressions across several of your URLs.
                    Google has to pick a winner per query; when it keeps
                    switching, every candidate ranks worse than one focused
                    page would.
  branded query   — whether the homepage actually owns the site's own name.

Auth is the same service account gsc_checker.py uses.

Usage:
    python gsc_cannibalization.py sc-domain:example.com --credentials key.json --json
    python gsc_cannibalization.py https://example.com/ --credentials key.json --days 28
"""

import argparse
import json
import os
import sys
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import urlparse


# Not every caller is the runner. This script prints `ensure_ascii=False` JSON, and a
# bare `python <script> …` on Windows encodes stdout with the ANSI codepage — so a
# Greek query or a Polish name raises UnicodeEncodeError and the script produces
# nothing at all. The runner now hands its children a UTF-8 environment; this is the
# same guarantee for somebody running the script by hand.
def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):  # already wrapped, or not a TextIO
            pass


_utf8_stdout()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from gsc_checker import build_service
    from hreflang_checker import locale_page_key, run_hreflang_check
except ImportError:
    print("Error: gsc_checker.py must be importable from the same directory")
    sys.exit(1)

# basis: inherited — average position 1.5, present at import. Blocker: one property in one language cannot establish branded-query ownership across markets; this needs many properties across markets.
RANKS_FIRST_POSITION = 1.5
# basis: inherited — 100 impressions, present at import. Blocker: this only splits an already-fired finding into high versus medium severity, so it is a prioritisation convention rather than a search-analytics measurement.
HIGH_SEVERITY_IMPRESSIONS = 100

# basis: inherited — present at import, and the one cap here that decides a verdict.
#  One request, no `startRow`, so a property with more than this many query/page
#  rows in the window is analysed from the first 5000 and MS-023 and KW-071 — both
#  `high` — read `eq 0` off them as "no query on this site splits across URLs".
#  `truncated` below says when that happened; raising it means paginating.
ROW_LIMIT = 5000
# basis: inherited — 10 impressions, present at import. Below it two pages sharing a
#  query is noise rather than cannibalisation, but the number was not measured
MIN_IMPRESSIONS = 10       # below this, page-splitting is noise, not a pattern
# basis: inherited — present at import, and definitional rather than calibratable: one
#  page cannot compete with itself
MIN_PAGES = 2
# basis: convention — two results within three average-position places are close
# enough that the number alone cannot identify a settled winner. This reuses the
# former registry band without claiming that a wider raw spread is worse.
CONTESTED_POSITION_BAND = 3.0
# basis: convention — shorter normalized terms collide with too many ordinary words.
MIN_NEAR_BRAND_LENGTH = 5
# basis: convention — one typo is the precision cap below ten normalized characters.
SHORT_NEAR_BRAND_LENGTH = 10
# basis: convention — one edit catches a dropped or doubled letter in a short term.
SHORT_NEAR_BRAND_EDITS = 1
# basis: convention — two edits allow the same typo rate across longer brand forms.
LONG_NEAR_BRAND_EDITS = 2
# basis: convention — 1000 retains 243 queries whole without unbounded evidence.
QUERY_EVIDENCE_LIMIT = 1000


def fetch_query_page_rows(service, site_url: str, days: int):
    end = datetime.now().date()
    start = end - timedelta(days=days)
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": ["query", "page"],
        "rowLimit": ROW_LIMIT,
    }
    resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    rows = []
    for r in resp.get("rows", []):
        rows.append({
            "query": r["keys"][0],
            "page": r["keys"][1],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "position": round(r.get("position", 0), 1),
        })
    return rows, start.isoformat(), end.isoformat()


def _group_locale_pages(hits: list, alternate_urls: list[str]) -> list:
    grouped = {}
    for hit in hits:
        key = locale_page_key(hit["page"], alternate_urls)
        grouped.setdefault(key, []).append(hit)
    pages = []
    for members in grouped.values():
        representative = max(members, key=lambda row: row["impressions"])
        impressions = sum(row["impressions"] for row in members)
        weighted = sum(row["position"] * row["impressions"] for row in members
                       if row["position"])
        positioned = sum(row["impressions"] for row in members if row["position"])
        pages.append({
            "page": representative["page"],
            "clicks": sum(row["clicks"] for row in members),
            "impressions": impressions,
            "position": round(weighted / positioned, 1) if positioned else 0,
            "alternates": sorted({row["page"] for row in members}),
        })
    return sorted(pages, key=lambda page: -page["impressions"])


def find_query_spreads(rows: list, alternate_urls: list[str] | None = None) -> list:
    by_query: dict = {}
    for r in rows:
        by_query.setdefault(r["query"], []).append(r)

    out = []
    for query, hits in by_query.items():
        eligible = [hit for hit in hits if hit["impressions"] >= MIN_IMPRESSIONS]
        if len(eligible) < MIN_PAGES:
            continue
        out.append(_query_summary(query, eligible, alternate_urls))
    out.sort(key=lambda c: (-c["impressions"], -c["spread"]))
    return out


def _query_summary(query: str, eligible: list,
                   alternate_urls: list[str] | None = None) -> dict:
    pages = _group_locale_pages(eligible, alternate_urls or [])
    positions = [p["position"] for p in pages if p["position"]]
    return {
        "query": query,
        "pages": pages[:5],
        "page_count": len(pages),
        "clicks": sum(p["clicks"] for p in pages),
        "impressions": sum(p["impressions"] for p in pages),
        # Raw distance between the best and worst logical page positions. A
        # wide value means one page outranks another; it does not by itself
        # mean Google is undecided or that keyword copy is duplicated.
        "spread": round(max(positions) - min(positions), 1) if len(positions) > 1 else 0,
        "positions_compared": len(positions),
    }


def find_cannibalization(rows: list, alternate_urls: list[str] | None = None) -> list:
    """Return query spreads that still contain at least two logical pages."""
    return [row for row in find_query_spreads(rows, alternate_urls)
            if row["page_count"] >= MIN_PAGES]


def _brand_form(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in decomposed
                   if char.isalnum() and not unicodedata.combining(char))


def _bounded_edit_distance(left: str, right: str, limit: int) -> int | None:
    """Return the edit distance when it is no greater than ``limit``."""
    if abs(len(left) - len(right)) > limit:
        return None
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, 1):
        current = [left_index]
        for right_index, right_char in enumerate(right, 1):
            current.append(min(
                current[-1] + 1,
                previous[right_index] + 1,
                previous[right_index - 1] + (left_char != right_char),
            ))
        if min(current) > limit:
            return None
        previous = current
    distance = previous[-1]
    return distance if distance <= limit else None


def _near_brand_match(query: str, brand_query: str) -> tuple[str, int] | None:
    brand_words = [_brand_form(word) for word in str(brand_query).split()]
    brand_words = [word for word in brand_words if word]
    brand_terms = [_brand_form(brand_query)]
    if len(brand_words) >= 2:
        brand_terms.append("".join(brand_words[:2]))
    brand_terms = list(dict.fromkeys(term for term in brand_terms if term))
    query_terms = [_brand_form(query)]
    query_terms.extend(_brand_form(word) for word in str(query).split())
    query_terms = list(dict.fromkeys(term for term in query_terms if term))

    for brand_term in brand_terms:
        for query_term in query_terms:
            # Precision guard: terms below five are
            # too easily ordinary words; under ten gets one edit, longer terms two.
            # This catches common dropped/doubled letters without making a quiet
            # cannibalization count out of unrelated short queries.
            if min(len(brand_term), len(query_term)) < MIN_NEAR_BRAND_LENGTH:
                continue
            limit = (SHORT_NEAR_BRAND_EDITS
                     if len(brand_term) < SHORT_NEAR_BRAND_LENGTH
                     else LONG_NEAR_BRAND_EDITS)
            distance = _bounded_edit_distance(query_term, brand_term, limit)
            if distance is not None:
                return brand_term, distance
    return None


def _brand_match(query: str, brand_query: str) -> tuple[str, int] | None:
    """Return the normalized brand term and edit distance that claimed a query."""
    query_form, brand_form = _brand_form(query), _brand_form(brand_query)
    if not query_form or not brand_form:
        return None
    if brand_form in query_form:
        return brand_form, 0
    brand_words = [_brand_form(word) for word in str(brand_query).split()]
    brand_words = [word for word in brand_words if word]
    if len(brand_words) >= 2:
        shorter_brand = "".join(brand_words[:2])
        if shorter_brand in query_form:
            return shorter_brand, 0
    # The inferred brand often includes a location suffix. Preserve a substantial
    # shorter form such as "acme valley" / "acmevalley" as the same brand.
    if query_form in brand_form and len(query_form) >= max(5, len(brand_form) // 2):
        return query_form, 0
    return _near_brand_match(query, brand_query)


def is_branded_query(query: str, brand_query: str) -> bool:
    """Match normalized brand forms and deliberately bounded misspellings."""
    return _brand_match(query, brand_query) is not None


def _query_evidence(rows: list, alternate_urls: list[str] | None,
                    result: dict, owns_brand: bool) -> tuple[list, bool]:
    by_query: dict = {}
    for row in rows:
        by_query.setdefault(row["query"], []).append(row)

    brand_query = result["branded"].get("query", "") if owns_brand else ""
    evidence = []
    for query, hits in by_query.items():
        eligible = [hit for hit in hits if hit["impressions"] >= MIN_IMPRESSIONS]
        summary = _query_summary(query, eligible, alternate_urls)
        brand_match = _brand_match(query, brand_query) if brand_query else None
        is_spread = len(eligible) >= MIN_PAGES
        if is_spread and brand_match:
            bucket = "branded_spread"
        elif summary["page_count"] >= MIN_PAGES:
            bucket = ("contested"
                      if summary["positions_compared"] >= MIN_PAGES
                      and summary["spread"] <= CONTESTED_POSITION_BAND
                      else "cannibalized")
        else:
            bucket = "single_page"
        item = {
            "query": query,
            "brand_form": _brand_form(query),
            "page_count": summary["page_count"],
            "impressions": summary["impressions"],
            "spread": summary["spread"],
            "positions_compared": summary["positions_compared"],
            "bucket": bucket,
        }
        if brand_match:
            item["matched_brand_term"], item["edit_distance"] = brand_match
        evidence.append(item)

    # The human-facing classified lists are bounded to 25 apiece. Put every query
    # that satisfies a classification rule first, so the evidence cap does not
    # inherit those display caps or orphan a classified query.
    evidence.sort(key=lambda item: (
        item["bucket"] == "single_page",
        -item["impressions"],
        item["query"],
    ))
    return evidence[:QUERY_EVIDENCE_LIMIT], len(evidence) > QUERY_EVIDENCE_LIMIT


def find_branded(rows: list, site_url: str) -> dict:
    """The highest-click query is treated as the brand term. Reports which page
    Google actually serves for it, and whether that is the homepage."""
    if not rows:
        return {"checked": False, "reason": "no query data in range"}
    host = urlparse(site_url.replace("sc-domain:", "https://")).netloc
    best = max(rows, key=lambda r: r["clicks"])
    same_query = [r for r in rows if r["query"] == best["query"]]
    owner = max(same_query, key=lambda r: r["clicks"])
    path = urlparse(owner["page"]).path.rstrip("/")
    return {
        "checked": True,
        "query": best["query"],
        "owner_page": owner["page"],
        "position": owner["position"],
        "clicks": owner["clicks"],
        "owns_homepage": path in ("", "/"),
        "ranks_first": owner["position"] <= RANKS_FIRST_POSITION,
        "host": host,
    }


def hreflang_alternates(site_url: str) -> list[str]:
    """Read locale alternates with the same parser as the hreflang audit."""
    homepage = (site_url.replace("sc-domain:", "https://", 1)
                if site_url.startswith("sc-domain:") else site_url)
    try:
        report = run_hreflang_check(homepage)
    except Exception:
        return []
    return [tag["url"] for tag in report.get("tags", []) if tag.get("url")]


def analyze(site_url: str, credentials: str, days: int,
            alternate_urls: list[str] | None = None) -> dict:
    result = {
        "property": site_url,
        "period": {"start": None, "end": None},
        "queries_analyzed": 0,
        "queries": [],
        "queries_truncated": False,
        # Not the same cap as `queries_truncated`, which trims the evidence list
        # after the counting is done. This one is upstream of every count in
        # `summary`: it says the API answered with a full page of rows, so there
        # were rows this analysis never saw.
        "truncated": False,
        "cannibalized": [],
        "branded_spread": [],
        "contested": [],
        "branded": {},
        # Empty, not `{"cannibalized_queries": None, …}`. `eq` and `truthy` read a
        # None as a *failing value* rather than as silence, so pre-seeding the keys
        # turned a revoked token or an exhausted quota into "two of your URLs compete
        # for one query" and "you do not rank first for your own brand" — four
        # fabricated `high` verdicts about a property nobody managed to open. The
        # measurement fills these in on success; an absent key is NO_DATA, which is
        # what "we could not ask" actually is.
        "summary": {},
        "issues": [],
        "error": None,
    }
    try:
        service = build_service(credentials)
        rows, start, end = fetch_query_page_rows(service, site_url, days)
    except Exception as exc:
        result["error"] = str(exc)[:300]
        # And `issues`, for the same reason the summary is empty: an empty list
        # satisfies `none_severity` and reads as "nothing wrong here".
        result.pop("issues", None)
        return result

    result["period"] = {"start": start, "end": end}
    result["truncated"] = len(rows) >= ROW_LIMIT
    result["queries_analyzed"] = len({r["query"] for r in rows})
    result["branded"] = find_branded(rows, site_url)
    spreads = find_query_spreads(rows, alternate_urls)
    brand = result["branded"]
    owns_brand = bool(brand.get("checked") and brand.get("owns_homepage"))
    if owns_brand:
        result["branded_spread"] = [
            spread for spread in spreads
            if is_branded_query(spread["query"], brand.get("query", ""))
        ][:25]
    # Counted whole, then capped for reading. The 25 is a human-facing cap and
    # `script-output-shapes.md` has always said so — it also says
    # `summary.cannibalized_queries = bucket[cannibalized] + bucket[contested]`,
    # over the classified queries rather than over the shortened list. The code
    # took `len()` of the shortened list instead, so a property with sixty
    # cannibalised queries reported twenty-five of them and the document that
    # said otherwise was the only place the real number existed. It cannot fake a
    # PASS — twenty-five is not zero — but it is the measure MS-023 and KW-071
    # print, and a fix list sized from it is short by every query past the cap.
    cannibalized_all = [
        spread for spread in spreads
        if spread["page_count"] >= MIN_PAGES
        and not (owns_brand
                 and is_branded_query(spread["query"], brand.get("query", "")))
    ]
    contested_all = [
        spread for spread in cannibalized_all
        if spread["positions_compared"] >= MIN_PAGES
        and spread["spread"] <= CONTESTED_POSITION_BAND
    ]
    result["cannibalized"] = cannibalized_all[:25]
    result["contested"] = contested_all[:25]
    result["summary"] = {
        "cannibalized_queries": len(cannibalized_all),
        "contested_queries": len(contested_all),
    }
    result["queries"], result["queries_truncated"] = _query_evidence(
        rows, alternate_urls, result, owns_brand)

    for c in result["cannibalized"][:10]:
        result["issues"].append({
            "severity": "high" if c["impressions"] > HIGH_SEVERITY_IMPRESSIONS else "medium",
            "message": f"'{c['query']}' splits across {c['page_count']} URLs "
                       f"({c['impressions']} impressions, rank spread {c['spread']}) — "
                       f"pick one target and consolidate",
        })
    b = result["branded"]
    if b.get("checked") and not b.get("owns_homepage"):
        result["issues"].append({
            "severity": "high",
            "message": f"Top query '{b['query']}' is served by {b['owner_page']}, "
                       f"not the homepage",
        })
    if b.get("checked") and not b.get("ranks_first"):
        result["issues"].append({
            "severity": "high",
            "message": f"Top query '{b['query']}' averages position {b['position']}",
        })
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Find keyword cannibalization and branded-query ownership via GSC")
    parser.add_argument("site_url", help="GSC property (sc-domain:example.com or URL)")
    parser.add_argument("--credentials", default="",
                        help="Service account JSON (or GSC_CREDENTIALS_PATH / GV_SA_KEY)")
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    creds = (args.credentials or os.environ.get("GSC_CREDENTIALS_PATH")
             or os.environ.get("GV_SA_KEY")
             or os.path.expanduser("~/.config/gcloud/gsc-service-account.json"))

    result = analyze(args.site_url, creds, args.days,
                     alternate_urls=hreflang_alternates(args.site_url))

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if result["error"]:
        print(f"GSC query failed: {result['error']}")
        return
    print(f"Cannibalization for {result['property']} "
          f"({result['period']['start']}..{result['period']['end']})")
    print(f"  queries analyzed:     {result['queries_analyzed']}")
    print(f"  cannibalized queries: {result['summary']['cannibalized_queries']}")
    b = result["branded"]
    if b.get("checked"):
        print(f"  top query:            '{b['query']}' -> {b['owner_page']} "
              f"(pos {b['position']}, homepage={b['owns_homepage']})")
    for c in result["cannibalized"][:10]:
        print(f"\n  '{c['query']}' — {c['page_count']} URLs, spread {c['spread']}")
        for p in c["pages"][:3]:
            print(f"      pos {p['position']:<5} {p['impressions']:>5} impr  {p['page'][:70]}")


if __name__ == "__main__":
    main()
