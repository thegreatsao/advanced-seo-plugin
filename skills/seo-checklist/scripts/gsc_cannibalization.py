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
        pages = _group_locale_pages(eligible, alternate_urls or [])
        positions = [p["position"] for p in pages if p["position"]]
        out.append({
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
        })
    out.sort(key=lambda c: (-c["impressions"], -c["spread"]))
    return out


def find_cannibalization(rows: list, alternate_urls: list[str] | None = None) -> list:
    """Return query spreads that still contain at least two logical pages."""
    return [row for row in find_query_spreads(rows, alternate_urls)
            if row["page_count"] >= MIN_PAGES]


def _brand_form(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in decomposed
                   if char.isalnum() and not unicodedata.combining(char))


def is_branded_query(query: str, brand_query: str) -> bool:
    """Match case, diacritic and spacing variants, including longer brand queries."""
    query_form, brand_form = _brand_form(query), _brand_form(brand_query)
    if not query_form or not brand_form:
        return False
    if brand_form in query_form:
        return True
    brand_words = [_brand_form(word) for word in str(brand_query).split()]
    brand_words = [word for word in brand_words if word]
    if len(brand_words) >= 2 and "".join(brand_words[:2]) in query_form:
        return True
    # The inferred brand often includes a location suffix. Preserve a substantial
    # shorter form such as "acme valley" / "acmevalley" as the same brand.
    return query_form in brand_form and len(query_form) >= max(5, len(brand_form) // 2)


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
    result["cannibalized"] = [
        spread for spread in spreads
        if spread["page_count"] >= MIN_PAGES
        and not (owns_brand
                 and is_branded_query(spread["query"], brand.get("query", "")))
    ][:25]
    result["contested"] = [
        spread for spread in result["cannibalized"]
        if spread["positions_compared"] >= MIN_PAGES
        and spread["spread"] <= CONTESTED_POSITION_BAND
    ]
    result["summary"] = {
        "cannibalized_queries": len(result["cannibalized"]),
        "contested_queries": len(result["contested"]),
    }

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
