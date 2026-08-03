#!/usr/bin/env python3
"""
Detect Google Analytics 4 / Tag Manager installation and duplicate tagging.

Duplicate GA4 configuration is the failure this catches: the same measurement
ID configured twice (often once hardcoded and once via GTM) double-counts every
pageview, which silently corrupts every downstream traffic decision.

Usage:
    python ga4_tag_checker.py https://example.com
    python ga4_tag_checker.py https://example.com --json
"""

import argparse
import json
import re
import sys
from collections import Counter

try:
    import requests  # noqa: F401  (kept for the shared dependency error contract)
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    from lib.safe_http import safe_get
except ImportError:
    from scripts.lib.safe_http import safe_get

# gtag('config', 'G-XXXX') and the gtag.js loader query string both carry the ID.
RE_CONFIG = re.compile(r"""gtag\s*\(\s*['"]config['"]\s*,\s*['"](G-[A-Z0-9]+)['"]""", re.I)
RE_GTAG_SRC = re.compile(r"gtag/js\?id=(G-[A-Z0-9]+)", re.I)
RE_GTM = re.compile(r"(GTM-[A-Z0-9]+)", re.I)
RE_UA = re.compile(r"(UA-\d{4,}-\d+)")
RE_GTAG_LOADER = re.compile(r"gtag/js\?id=", re.I)
RE_GTM_LOADER = re.compile(r"gtm\.js\?id=|googletagmanager\.com/gtm\.js", re.I)


def check(url: str, timeout: int = 15) -> dict:
    result = {
        "url": url,
        "measurement_ids": [],
        "gtm_containers": [],
        "ua_legacy": [],
        "duplicates": [],
        "loaders": {"gtag_js": 0, "gtm_js": 0},
        "issues": [],
        "fetch_error": None,
    }
    try:
        html = safe_get(url, timeout=timeout).text
    except Exception as exc:
        result["fetch_error"] = str(exc)[:200]
        return result

    config_ids = [m.upper() for m in RE_CONFIG.findall(html)]
    src_ids = [m.upper() for m in RE_GTAG_SRC.findall(html)]
    containers = [m.upper() for m in RE_GTM.findall(html)]
    ua_ids = RE_UA.findall(html)

    result["measurement_ids"] = sorted(set(config_ids) | set(src_ids))
    result["gtm_containers"] = sorted(set(containers))
    result["ua_legacy"] = sorted(set(ua_ids))
    result["loaders"] = {
        "gtag_js": len(RE_GTAG_LOADER.findall(html)),
        "gtm_js": len(RE_GTM_LOADER.findall(html)),
    }

    # A measurement ID configured more than once double-counts pageviews.
    for gid, n in Counter(config_ids).items():
        if n > 1:
            result["duplicates"].append({"id": gid, "count": n, "kind": "gtag_config"})
    for cid, n in Counter(containers).items():
        if n > 2:  # GTM ships a <script> plus a <noscript> iframe by design.
            result["duplicates"].append({"id": cid, "count": n, "kind": "gtm_container"})

    if not result["measurement_ids"] and not result["gtm_containers"]:
        result["issues"].append({
            "severity": "medium",
            "message": "No GA4 measurement ID or GTM container found on the page",
            "url": url,
        })
    for d in result["duplicates"]:
        result["issues"].append({
            "severity": "high",
            "message": f"{d['id']} appears {d['count']}x ({d['kind']}) — pageviews will "
                       f"be double-counted",
            "url": url,
        })
    if len(result["measurement_ids"]) > 1:
        result["issues"].append({
            "severity": "low",
            "message": f"Multiple GA4 properties on one page: "
                       f"{', '.join(result['measurement_ids'])} — intentional only if you "
                       f"deliberately run parallel properties",
            "url": url,
        })
    if result["ua_legacy"]:
        result["issues"].append({
            "severity": "medium",
            "message": f"Legacy Universal Analytics tag(s) still present: "
                       f"{', '.join(result['ua_legacy'])} — UA stopped processing data "
                       f"in July 2023",
            "url": url,
        })
    if result["loaders"]["gtag_js"] > 1:
        result["issues"].append({
            "severity": "medium",
            "message": f"gtag.js loaded {result['loaders']['gtag_js']}x",
            "url": url,
        })
    return result


def main():
    parser = argparse.ArgumentParser(description="Check GA4 / GTM tagging for duplicates")
    parser.add_argument("url", help="URL to check")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    result = check(args.url, args.timeout)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if result["fetch_error"]:
        print(f"Could not fetch page: {result['fetch_error']}")
        return
    print(f"Analytics tagging for {result['url']}")
    print(f"  GA4 measurement IDs: {', '.join(result['measurement_ids']) or 'none'}")
    print(f"  GTM containers:      {', '.join(result['gtm_containers']) or 'none'}")
    if result["ua_legacy"]:
        print(f"  Legacy UA:           {', '.join(result['ua_legacy'])}")
    print(f"  Duplicates:          {len(result['duplicates'])}")
    for i in result["issues"]:
        print(f"  [{i['severity']}] {i['message']}")


if __name__ == "__main__":
    main()
