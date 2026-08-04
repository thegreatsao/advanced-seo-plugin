#!/usr/bin/env python3
"""
Ask Search Console what Google actually knows about one URL.

The Search Analytics API reports how a page performs; this one reports what
Google decided about it — whether it is indexed, which canonical Google picked,
whether robots.txt allowed the crawl, when the crawl last happened.

The canonical answer is the reason this exists. A page can declare
`rel=canonical` to itself and still have Google pick a different URL, and
nothing in the page's own HTML reveals that. Only Search Console does.

Auth is the same service account gsc_checker.py uses. Quota is 2000 inspections
per property per day.

Note: the API's mobile-usability field was withdrawn in December 2023, so
mobile signals are still UI-only — see MB-099 in the checklist registry.

Usage:
    python gsc_url_inspection.py https://example.com/page \\
        --property sc-domain:example.com --credentials key.json --json
"""

import argparse
import json
import os
import socket
import sys
import time

# The API client leaves socket reads unbounded, which under a parallel checklist
# run turned one 7-second call into a 13-minute hang. Bound it, and retry once —
# a single stalled socket should cost seconds, not the whole audit.
SOCKET_TIMEOUT = 30
# basis: inherited — present at import. An operational retry count, not a verdict
RETRIES = 2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from gsc_checker import build_service
except ImportError:
    print("Error: gsc_checker.py must be importable from the same directory")
    sys.exit(1)

# coverageState strings that mean the URL is in the index. Google returns prose
# here rather than an enum, so match on substrings and treat anything
# unrecognised as undecided rather than as a failure.
INDEXED_MARKERS = ("submitted and indexed", "indexed, not submitted")
NOT_INDEXED_MARKERS = ("excluded", "not found", "blocked", "redirect",
                       "duplicate", "crawled - currently not indexed",
                       "discovered - currently not indexed", "soft 404")


def classify_coverage(state: str):
    """True / False / None for indexed. None means the wording was not
    recognised — an unfamiliar coverage string must not be read as an answer."""
    low = (state or "").lower()
    if any(m in low for m in INDEXED_MARKERS):
        return True
    if any(m in low for m in NOT_INDEXED_MARKERS):
        return False
    return None


def inspect(service, inspected_url: str, site_url: str, lang: str) -> dict:
    body = {
        "inspectionUrl": inspected_url,
        "siteUrl": site_url,
        "languageCode": lang,
    }
    resp = service.urlInspection().index().inspect(body=body).execute()
    return resp.get("inspectionResult", {})


def analyze(inspected_url: str, site_url: str, credentials: str, lang: str) -> dict:
    result = {
        "inspected_url": inspected_url,
        "property": site_url,
        "verdict": None,
        "coverage_state": None,
        "indexing_state": None,
        "robots_txt_state": None,
        "page_fetch_state": None,
        "last_crawl_time": None,
        "crawled_as": None,
        "google_canonical": None,
        "user_canonical": None,
        # Deliberately not pre-seeded with None. The comparison below already says
        # the right thing — "a page that declares no canonical has nothing to
        # disagree with Google about, so the comparison is absent rather than
        # passing" — but None is not absent: `truthy` reads it as a *failing value*,
        # so CI-010 reported "Google chose a different canonical" both for a page
        # with no canonical at all and for a run where the API never answered.
        "indexed": None,
        "sitemaps": [],
        "referring_urls": 0,
        "rich_results_verdict": None,
        "issues": [],
        "error": None,
    }
    socket.setdefaulttimeout(SOCKET_TIMEOUT)
    inspection = None
    for attempt in range(RETRIES):
        try:
            service = build_service(credentials)
            inspection = inspect(service, inspected_url, site_url, lang)
            result["error"] = None
            break
        except Exception as exc:
            result["error"] = str(exc)[:300]
            if attempt + 1 < RETRIES:
                time.sleep(2)
    if inspection is None:
        # `issues` goes too. An empty list satisfies `none_severity`, which is how
        # GO-135 reported "no indexing problems" for a property the API never
        # answered about — the same fabrication as a None read as a failure, pointing
        # the other way. Absent is the only honest shape for "we did not look".
        result.pop("issues", None)
        return result

    idx = inspection.get("indexStatusResult", {})
    result.update(
        verdict=idx.get("verdict"),
        coverage_state=idx.get("coverageState"),
        indexing_state=idx.get("indexingState"),
        robots_txt_state=idx.get("robotsTxtState"),
        page_fetch_state=idx.get("pageFetchState"),
        last_crawl_time=idx.get("lastCrawlTime"),
        crawled_as=idx.get("crawledAs"),
        google_canonical=idx.get("googleCanonical"),
        user_canonical=idx.get("userCanonical"),
        sitemaps=idx.get("sitemap", []),
        referring_urls=len(idx.get("referringUrls", [])),
    )
    rich = inspection.get("richResultsResult", {})
    result["rich_results_verdict"] = rich.get("verdict")

    result["indexed"] = classify_coverage(result["coverage_state"])

    # A page that declares no canonical has nothing to disagree with Google
    # about, so the comparison is absent rather than passing.
    gc, uc = result["google_canonical"], result["user_canonical"]
    if gc and uc:
        result["canonical_match"] = gc.rstrip("/") == uc.rstrip("/")

    if result.get("canonical_match") is False:
        result["issues"].append({
            "severity": "high",
            "message": f"Google chose {gc} as canonical, the page declares {uc} — "
                       f"signals for this URL consolidate elsewhere",
        })
    if result["indexed"] is False:
        result["issues"].append({
            "severity": "critical",
            "message": f"not indexed: {result['coverage_state']}",
        })
    if (result["robots_txt_state"] or "").upper() == "DISALLOWED":
        result["issues"].append({
            "severity": "critical",
            "message": "robots.txt disallows this URL",
        })
    if (result["indexing_state"] or "").upper() in ("BLOCKED_BY_META_TAG",
                                                    "BLOCKED_BY_HTTP_HEADER",
                                                    "BLOCKED_BY_ROBOTS_TXT"):
        result["issues"].append({
            "severity": "critical",
            "message": f"indexing blocked: {result['indexing_state']}",
        })
    if (result["page_fetch_state"] or "").upper() not in ("SUCCESSFUL", ""):
        result["issues"].append({
            "severity": "high",
            "message": f"Google could not fetch the page cleanly: "
                       f"{result['page_fetch_state']}",
        })
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Inspect one URL through the Search Console URL Inspection API")
    parser.add_argument("url", help="the URL to inspect (must belong to --property)")
    parser.add_argument("--property", default="",
                        help="GSC property (default: sc-domain:<host of url>)")
    parser.add_argument("--credentials", default="",
                        help="Service account JSON (or GSC_CREDENTIALS_PATH / GV_SA_KEY)")
    parser.add_argument("--language", default="en-US")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    creds = (args.credentials or os.environ.get("GSC_CREDENTIALS_PATH")
             or os.environ.get("GV_SA_KEY")
             or os.path.expanduser("~/.config/gcloud/gsc-service-account.json"))

    site = args.property
    if not site:
        from urllib.parse import urlparse
        host = urlparse(args.url).netloc
        site = f"sc-domain:{host[4:] if host.startswith('www.') else host}"

    result = analyze(args.url, site, creds, args.language)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if result["error"]:
        print(f"URL inspection failed: {result['error']}")
        return
    print(f"URL inspection: {result['inspected_url']}")
    print(f"  property:      {result['property']}")
    print(f"  verdict:       {result['verdict']}")
    print(f"  coverage:      {result['coverage_state']}")
    print(f"  indexed:       {result['indexed']}")
    print(f"  robots.txt:    {result['robots_txt_state']}")
    print(f"  indexing:      {result['indexing_state']}")
    print(f"  fetch:         {result['page_fetch_state']}")
    print(f"  last crawl:    {result['last_crawl_time']}")
    print(f"  Google canon:  {result['google_canonical']}")
    print(f"  page canon:    {result['user_canonical']}")
    print(f"  canon match:   {result['canonical_match']}")
    for i in result["issues"]:
        print(f"  [{i['severity']}] {i['message']}")


if __name__ == "__main__":
    main()
