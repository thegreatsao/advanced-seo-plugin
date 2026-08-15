#!/usr/bin/env python3
"""Inventory images for SEO, accessibility, and performance signals."""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse

from seo_common import (fetch_url, likely_lcp_candidate, load_html,
                        parse_html)


def inventory(source: str, fetch_images: bool = False, timeout: int = 15) -> dict:
    html, url, fetched = load_html(source, timeout=timeout)
    parsed = parse_html(html, url)
    rows = []
    issues = []
    skipped_no_src = 0
    for idx, img in enumerate(parsed["images"]):
        src = (img.get("src") or "").strip()
        if not src:
            skipped_no_src += 1
            continue
        ext = os.path.splitext(urlparse(src).path)[1].lower().lstrip(".")
        alt = img.get("alt")
        row = {
            "src": src,
            "alt": alt,
            "has_alt": alt is not None,
            "empty_alt": alt == "",
            "width": img.get("width"),
            "height": img.get("height"),
            "is_responsive_fill": bool(img.get("is_responsive_fill")),
            "loading": img.get("loading"),
            "srcset": bool(img.get("srcset")),
            "sizes": bool(img.get("sizes")),
            "format": ext,
            "likely_lcp_candidate": likely_lcp_candidate(img, idx),
            "native_source": bool(img.get("native_source")),
            "deferred_source": bool(img.get("deferred_source")),
            "discoverable": bool(img.get("native_source")),
        }
        if not row["has_alt"]:
            issues.append({"severity": "warning", "message": "Image missing alt text", "url": src})
        if not row["is_responsive_fill"] and (not row["width"] or not row["height"]):
            issues.append({"severity": "info", "message": "Image missing explicit dimensions", "url": src})
        if row["likely_lcp_candidate"] and row["loading"] == "lazy":
            issues.append({"severity": "warning", "message": "Likely LCP image is lazy-loaded", "url": src})
        if fetch_images and src.startswith("http"):
            head = fetch_url(src, method="HEAD", timeout=timeout)
            row["status"] = head.get("status")
            row["content_length"] = head.get("headers", {}).get("content-length")
            row["content_type"] = head.get("headers", {}).get("content-type")
        rows.append(row)
    # Native `loading=lazy` with an ordinary `src` remains discoverable; only a
    # JS-deferred source with no native alternative answers CN-054 adversely. LCP
    # performance is graded separately by image_weight_audit.py for MD-185, so this
    # inventory does not retain a second, unread count for it.
    undiscoverable_lazy = sum(1 for r in rows
                              if r["deferred_source"] and not r["discoverable"])
    missing_alt = sum(1 for r in rows if not r["has_alt"])
    empty_alt = sum(1 for r in rows if r["empty_alt"])
    out = {"url": url or source,
           "empty_alt": empty_alt, "skipped_no_src": skipped_no_src,
           "summary": {"images": len(rows),
                       "empty_alt": empty_alt, "skipped_no_src": skipped_no_src},
           "issues": issues, "images": rows, "fetch_error": fetched.get("error")}
    # A page with no images is not a page whose images are missing, unlabelled or
    # undiscoverable. These three are the only fields the registry reads as a verdict
    # — MD-184 asserts `count gte 1`, CI-016 and MD-186 assert `missing_alt eq 0`,
    # CN-054 asserts `summary.lazy_lcp_candidates eq 0` — and emitted as 0 they turn
    # "there was nothing here to judge" into a verdict: a FAIL for the first and a
    # free PASS for the other three. An absent key is NO_DATA, so a sampled page with
    # no images stays undecided and the pages that have images decide the item.
    #
    # `image_weight_audit.py:152` already does exactly this with `responsive_count`
    # and `modern_format_count`, and the two scripts disagreeing on the same two
    # fixture pages is how this was found: MD-189 was declared FAIL, came back PASS,
    # and its neighbour MD-184 failed the exemplary fixture. The descriptive counts
    # above stay at 0 — `summary.images` is a fact about the page, not a verdict.
    if rows:
        out["count"] = len(rows)
        out["missing_alt"] = missing_alt
        out["summary"]["lazy_lcp_candidates"] = undiscoverable_lazy
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory images on a page")
    parser.add_argument("source", help="URL or local HTML file")
    parser.add_argument("--fetch-images", action="store_true")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true")
    args = parser.parse_args()
    result = inventory(args.source, args.fetch_images, args.timeout)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        lines = [f"{'missing-alt' if not r['has_alt'] else 'empty-alt' if r['empty_alt'] else 'ok'}\t{r['src']}"
                 for r in result["images"]]
        lines.append(f"empty-alt-count\t{result['empty_alt']}")
        lines.append(f"skipped-no-src\t{result['skipped_no_src']}")
        print("\n".join(lines))


if __name__ == "__main__":
    main()
