#!/usr/bin/env python3
"""Find sitemap URLs that are not reachable from an internal crawl.

Reads the shared crawl inventory (`site_crawl.py`); crawls one for itself when not
given one, so the CLI still works alone.

**Reachable means linked-to.** The shared crawl seeds from the sitemap as well as
from the entry URL, so "we managed to fetch it" would make every sitemap URL
reachable by construction and this whole check vacuous. A page is reachable here when
some other crawled page links to it, which is the question GO-137 asks.
"""

from __future__ import annotations

import argparse

import site_crawl
from seo_common import normalize_url, print_json_or_text

try:
    from lib.safe_http import robots_allows
except ImportError:
    from scripts.lib.safe_http import robots_allows


def reachable_from_inventory(inventory: dict) -> dict:
    """The pages some other page links to, plus the entry."""
    pages = inventory.get("pages") or {}
    inbound = site_crawl.inbound_map(inventory)
    entry = inventory.get("entry") or ""
    reachable, errors = {}, []
    for key, row in sorted(pages.items()):
        if key != entry and not inbound.get(key):
            continue
        reachable[key] = {
            "url": key,
            "status": row.get("status"),
            "final_url": row.get("final_url"),
            "depth": row.get("depth"),
            "in_sitemap": bool(row.get("in_sitemap")),
        }
        if row.get("status") != 200 or not row.get("html"):
            errors.append({"url": key, "status": row.get("status"),
                           "error": row.get("error")})
    return {"pages": reachable, "errors": errors,
            # Kept out of `reachable` **and** out of the orphan arithmetic below.
            # Orphans are `sitemap - reachable`, so letting a page we chose not to
            # fetch drop out of `reachable` would manufacture a site defect from
            # our own politeness — and GO-137 fails on a single orphan. Reported
            # separately: a sitemap listing a robots-blocked URL is a real finding,
            # just not this one.
            "robots_skipped": sorted(inventory.get("robots_blocked") or ())}


def find_orphan_pages(site_url: str, sitemap_urls: list[str] | None = None,
                      depth: int = 2, max_pages: int = 100, timeout: int = 15,
                      inventory: dict | None = None,
                      inventory_path: str = "") -> dict:
    site_url = normalize_url(site_url)
    if inventory is None:
        inventory = site_crawl.inventory_for(
            site_url, inventory_path, depth=depth, max_pages=max_pages,
            timeout=timeout, sitemap_urls=sitemap_urls, signatures=False)
    sitemap = inventory.get("sitemap") or {"sitemaps_checked": [], "urls": [],
                                           "errors": []}
    crawl = reachable_from_inventory(inventory)
    sitemap_set = set(sitemap["urls"])
    reachable_set = set(crawl["pages"])
    robots_set = set(crawl.get("robots_skipped") or ())

    # The crawl can only record a refusal for a URL it actually tried, and it tries
    # what the site links to. A sitemap URL that nothing links to is never attempted,
    # so a disallowed one arrived here with no refusal attached and was reported as
    # an orphan — the very failure the subtraction below exists to prevent, reaching
    # the same place by a different road. And it is the ordinary case, not an edge
    # one: a page is usually unlinked *because* it is blocked.
    #
    # So the sitemap side is checked against robots.txt directly. The answers are
    # cached per origin, so this costs one fetch of /robots.txt, not one per URL.
    for url in sorted(sitemap_set - reachable_set - robots_set):
        try:
            if not robots_allows(url)[0]:
                robots_set.add(url)
        except Exception:  # noqa: BLE001 — an unreadable robots.txt allows
            pass

    # Subtracting `robots_set` is the whole point: a page robots.txt told us not to
    # fetch is not unreachable, we just did not look. Counting it as an orphan would
    # turn our own restraint into the site's failure.
    orphan_urls = sorted(sitemap_set - reachable_set - robots_set)
    discovered_not_in_sitemap = sorted(reachable_set - sitemap_set)
    sitemap_blocked_by_robots = sorted(sitemap_set & robots_set)
    issues = []
    if orphan_urls:
        issues.append({"severity": "warning", "type": "sitemap_orphans", "count": len(orphan_urls), "message": "Sitemap URLs were not reached by crawl"})
    if discovered_not_in_sitemap:
        issues.append({"severity": "info", "type": "crawl_only_pages", "count": len(discovered_not_in_sitemap), "message": "Crawled URLs are not present in sitemap"})
    if sitemap_blocked_by_robots:
        # A finding in its own right, and a sharper one than "orphan": the site is
        # asking search engines to index URLs it also forbids them to fetch.
        issues.append({"severity": "warning", "type": "sitemap_robots_conflict",
                       "count": len(sitemap_blocked_by_robots),
                       "message": "Sitemap lists URLs that robots.txt disallows"})

    return {
        "site": site_url,
        # Zero orphans out of zero pages is not a well-linked site. GO-137 reads
        # `summary.orphan_pages`, and against a host that refused every connection
        # the arithmetic gave `sitemap(∅) - reachable(∅)` = no orphans = PASS. This
        # script was the one crawler with no entry in the test suite's run list, and
        # the dead-origin sweep took its script list from that list — so the item
        # that reports "no orphans" about nothing was the one the sweep could not see.
        "fetch_error": inventory.get("fetch_error"),
        "summary": {
            "sitemaps_checked": len(sitemap["sitemaps_checked"]),
            "sitemap_urls": len(sitemap_set),
            "reachable_pages": len(reachable_set),
            "orphan_pages": len(orphan_urls),
            "discovered_not_in_sitemap": len(discovered_not_in_sitemap),
            "robots_skipped": len(robots_set),
            "sitemap_urls_blocked_by_robots": len(sitemap_blocked_by_robots),
        },
        "sitemaps_checked": sitemap["sitemaps_checked"],
        "orphan_pages": orphan_urls,
        "discovered_not_in_sitemap": discovered_not_in_sitemap,
        "robots_skipped": sorted(robots_set),
        "sitemap_urls_blocked_by_robots": sitemap_blocked_by_robots,
        "reachable_pages": list(crawl["pages"].values()),
        "issues": issues,
        "errors": {"sitemap": sitemap["errors"], "crawl": crawl["errors"]},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Find sitemap URLs not reachable from an internal crawl")
    parser.add_argument("site", help="Website URL")
    parser.add_argument("--inventory", default="",
                        help="crawl inventory from site_crawl.py; crawled here when "
                             "not supplied")
    parser.add_argument("--sitemap", action="append", help="Explicit sitemap URL; can be repeated")
    parser.add_argument("--depth", type=int, default=2, help="Internal crawl depth (default: 2)")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum crawl pages (default: 100)")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    args = parser.parse_args()

    result = find_orphan_pages(args.site, sitemap_urls=args.sitemap, depth=args.depth,
                               max_pages=args.max_pages, timeout=args.timeout,
                               inventory_path=args.inventory)
    lines = [
        f"Orphan page check for {result['site']}",
        (
            f"Sitemap URLs: {result['summary']['sitemap_urls']}  "
            f"Reachable pages: {result['summary']['reachable_pages']}  "
            f"Orphans: {result['summary']['orphan_pages']}"
        ),
    ]
    lines.extend(f"Orphan: {url}" for url in result["orphan_pages"][:25])
    print_json_or_text(result, args.json, lines)


if __name__ == "__main__":
    main()
