#!/usr/bin/env python3
"""Audit image weight, responsive image usage, and likely LCP image risk.

An image is judged by everything the browser could choose for it, not by the
`<img>` tag alone. The distinction is the whole of MB-096 and MB-097: the way
this is supposed to be done is a `<picture>` that offers avif or webp through
`<source>` and keeps a png in the `<img>` for browsers that cannot take either,
so reading only the `<img>` sees the fallback, misses the modern format, and
fails the site precisely for following the recommendation.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from seo_common import fetch_url, likely_lcp_candidate, load_source, parse_html


MODERN_FORMATS = {"avif", "webp"}
RASTER_FORMATS = {"jpg", "jpeg", "png", "gif"}
# A `<source>` declares its format twice over, in `type` and in its URLs, and the
# two disagree often enough to be worth reading both: `type` is what the browser
# actually dispatches on, and a CDN URL with no extension has nothing else.
MODERN_MIME = {f"image/{fmt}" for fmt in MODERN_FORMATS}

# basis: inherited — 250KB, present at import from Agentic-SEO-Skill. One of the five
#  numbers KNOWN-ISSUES §2 names, and until 0.13.0 it was not even a constant: an inline
#  `> 250_000` in the middle of a loop, which is why no inventory of thresholds could
#  find it. A number nothing can name is a number nobody can argue with
LARGE_IMAGE_BYTES = 250_000


def _extension(src: str) -> str:
    return os.path.splitext(urlparse(src).path)[1].lower().lstrip(".")


def _modern_sources(sources: list[dict]) -> list[str]:
    """The `<source>` formats in this `<picture>` that count as modern."""
    found = []
    for source in sources or []:
        if source.get("type") in MODERN_MIME:
            found.append(source["type"].split("/", 1)[1])
            continue
        for url in source.get("urls") or []:
            ext = _extension(url)
            if ext in MODERN_FORMATS:
                found.append(ext)
                break
    return found


def _local_size(src: str, html_source: str) -> int | None:
    if src.startswith(("http://", "https://", "data:")):
        return None
    base = Path(html_source).resolve().parent if Path(html_source).exists() else Path.cwd()
    candidate = (base / src.lstrip("/")).resolve()
    try:
        if candidate.is_file():
            return candidate.stat().st_size
    except OSError:
        return None
    return None


def audit(source: str, fetch_images: bool = False, timeout: int = 15) -> dict:
    html, url, fetched = load_source(source, timeout=timeout)
    parsed = parse_html(html, url)
    images = []
    issues = []

    for index, img in enumerate(parsed["images"]):
        src = img.get("src") or ""
        ext = _extension(src)
        sources = img.get("picture_sources") or []
        modern_sources = _modern_sources(sources)
        likely_lcp = likely_lcp_candidate(img, index)
        row = {
            "src": src,
            "format": ext,
            "width": img.get("width"),
            "height": img.get("height"),
            "loading": img.get("loading"),
            "fetchpriority": img.get("fetchpriority"),
            "srcset": bool(img.get("srcset")),
            "sizes": bool(img.get("sizes")),
            # Kept apart from `srcset` and `format` rather than folded into them.
            # "This img declares a srcset" and "a sibling source does" are different
            # facts about the markup, and a reader handed a fix list needs to know
            # which one is true before editing anything.
            "picture_source_count": len(sources),
            "picture_srcset": any(s.get("srcset") for s in sources),
            "picture_modern_formats": modern_sources,
            "likely_lcp_candidate": likely_lcp,
            "status": None,
            "content_length": _local_size(src, source),
            "content_type": None,
        }
        # What the browser can actually end up with, which is what both items are
        # about. The `img` is the fallback in a `<picture>`, not the answer.
        row["responsive"] = row["srcset"] or row["picture_srcset"]
        row["modern_format"] = ext in MODERN_FORMATS or bool(modern_sources)
        if fetch_images and src.startswith(("http://", "https://")):
            head = fetch_url(src, method="HEAD", timeout=timeout)
            row["status"] = head.get("status")
            headers = head.get("headers", {})
            length = headers.get("content-length")
            row["content_length"] = int(length) if length and length.isdigit() else None
            row["content_type"] = headers.get("content-type")

        if likely_lcp and row["loading"] == "lazy":
            issues.append({"severity": "warning", "message": "Likely LCP image is lazy-loaded", "url": src})
        if likely_lcp and row["fetchpriority"] != "high":
            issues.append({"severity": "info", "message": "Likely LCP image lacks fetchpriority=high", "url": src})
        if ext in RASTER_FORMATS and not modern_sources:
            issues.append({"severity": "info", "message": "Consider AVIF/WebP for raster image", "url": src, "evidence": ext})
        if not row["responsive"]:
            issues.append({"severity": "info", "message": "Image has no srcset", "url": src})
        if row["srcset"] and not row["sizes"]:
            issues.append({"severity": "info", "message": "Responsive image has srcset but no sizes", "url": src})
        if row["content_length"] and row["content_length"] > LARGE_IMAGE_BYTES:
            issues.append({"severity": "warning", "message": "Large image transfer size", "url": src, "evidence": f"{row['content_length']} bytes"})
        images.append(row)

    known_bytes = sum(row["content_length"] or 0 for row in images)
    # A structured count for "Fix Broken Images", emitted only when statuses were
    # actually collected. Reporting 0 broken because nothing was fetched is the
    # difference between "no broken images" and "we did not look": the key is
    # absent instead, which the checklist runner reads as NO_DATA.
    checked = [row for row in images if isinstance(row.get("status"), int)]
    broken = [row for row in checked if row["status"] >= 400]
    out = {
        "url": url or source,
        "image_count": len(images),
        "images_status_checked": len(checked),
        "known_image_bytes": known_bytes if fetch_images or any(row["content_length"] for row in images) else None,
        # The same two counts restricted to the `<img>` tag, which is what these
        # used to mean. Kept because they are the honest way to say "the fallback
        # is a png and that is fine": dropping them would leave no way to tell a
        # `<picture>` serving webp from an `<img src="x.webp">`.
        "modern_format_on_img_count": sum(1 for row in images
                                          if row["format"] in MODERN_FORMATS),
        "srcset_on_img_count": sum(1 for row in images if row["srcset"]),
        "picture_count": sum(1 for row in images if row["picture_source_count"]),
        "issues": issues,
        "images": images,
        "fetch_error": fetched.get("error"),
    }
    # An image-free page is not a page serving unresponsive, legacy-format images.
    # Omit these verdict inputs so a sampled page with nothing to optimize is
    # undecided and pages that actually contain images decide the site-level item.
    if images:
        out["modern_format_count"] = sum(1 for row in images
                                          if row["modern_format"])
        out["responsive_count"] = sum(1 for row in images if row["responsive"])
    # Present only when statuses exist. Emitting 0 — or None, which an equality
    # assertion reads as a failure rather than as silence — would turn "we did not
    # look" into a verdict either way. An absent key is NO_DATA by design.
    if checked:
        out["broken_image_count"] = len(broken)
        # `row["src"]`, not `row["url"]` — the row has no "url" key, so this raised
        # KeyError and killed the whole script. It could only fire on a page that
        # actually had a broken image, which is the one page MD-187 exists for: any
        # site with no broken images ran fine and reported 0, so the crash stayed
        # invisible until a fixture was built with a 404 image in it.
        out["broken_images"] = [row["src"] for row in broken]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit image weight and responsive-image performance")
    parser.add_argument("source", help="URL or local HTML file")
    parser.add_argument("--fetch-images", action="store_true", help="HEAD remote images for status and byte size")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true")
    args = parser.parse_args()

    result = audit(args.source, args.fetch_images, args.timeout)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Images: {result['image_count']}; responsive: "
              f"{result.get('responsive_count', 'n/a')}; "
              f"issues: {len(result['issues'])}")


if __name__ == "__main__":
    main()
