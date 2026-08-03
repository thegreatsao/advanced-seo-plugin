#!/usr/bin/env python3
"""
Check whether a page's stylesheets are minified.

Minification is judged structurally, not by filename: a file called *.min.css
that still carries comments and one rule per line is not minified, and a hand-
written single-line file is. The heuristic combines newline density, comment
volume and indentation.

Usage:
    python css_minify_check.py https://example.com
    python css_minify_check.py https://example.com --json
"""

import argparse
import json
import re
import sys
from urllib.parse import urljoin

try:
    import requests  # noqa: F401  (kept for the shared dependency error contract)
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4")
    sys.exit(1)

try:
    from lib.safe_http import safe_get
except ImportError:
    from scripts.lib.safe_http import safe_get

MAX_SHEETS = 12
SMALL_FILE_BYTES = 2048  # too small for the ratio to mean anything
RE_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def looks_minified(css: str) -> tuple[bool, float]:
    """Return (minified, bytes_per_line). Minified CSS packs many rules per
    line; source CSS averages well under 100 bytes per line."""
    if not css.strip():
        return True, 0.0
    lines = css.count("\n") + 1
    ratio = len(css) / lines
    comments = sum(len(m) for m in RE_COMMENT.findall(css))
    comment_pct = comments / len(css) if css else 0
    indented = sum(1 for ln in css.split("\n")[:400] if ln[:2] in ("  ", "\t "))
    # Any one signal alone is weak evidence; together they are decisive.
    minified = ratio > 180 and comment_pct < 0.08 and indented < 20
    return minified, round(ratio, 1)


def check(url: str, timeout: int = 15) -> dict:
    result = {
        "url": url,
        "stylesheets": [],
        "checked": 0,
        "unminified_count": 0,
        "wasted_bytes": 0,
        "issues": [],
        "fetch_error": None,
    }
    try:
        html = safe_get(url, timeout=timeout).text
    except Exception as exc:
        result["fetch_error"] = str(exc)[:200]
        return result

    soup = BeautifulSoup(html, "html.parser")
    hrefs = []
    for link in soup.find_all("link"):
        rel = link.get("rel") or []
        rel_text = " ".join(rel if isinstance(rel, list) else [rel]).lower()
        if "stylesheet" not in rel_text:
            continue
        href = link.get("href")
        if href:
            hrefs.append(urljoin(url, href))
    hrefs = list(dict.fromkeys(hrefs))[:MAX_SHEETS]

    for href in hrefs:
        row = {"href": href, "bytes": None, "minified": None, "ratio": None,
               "status": None, "error": None}
        try:
            resp = safe_get(href, timeout=timeout)
            row["status"] = resp.status_code
            css = resp.text
            row["bytes"] = len(css.encode("utf-8", errors="ignore"))
            if row["bytes"] < SMALL_FILE_BYTES:
                # Too small to judge, and too small to matter.
                row["minified"] = True
            else:
                row["minified"], row["ratio"] = looks_minified(css)
                if not row["minified"]:
                    result["unminified_count"] += 1
                    # Minification typically removes 20-30% of source CSS.
                    result["wasted_bytes"] += int(row["bytes"] * 0.25)
            result["checked"] += 1
        except Exception as exc:
            row["error"] = str(exc)[:160]
        result["stylesheets"].append(row)

    if not hrefs:
        result["issues"].append({
            "severity": "low",
            "message": "No external stylesheets found (inline or JS-injected CSS "
                       "is not evaluated here)",
            "url": url,
        })
    for row in result["stylesheets"]:
        if row["minified"] is False:
            result["issues"].append({
                "severity": "low",
                "message": f"Unminified CSS ({row['bytes']} bytes, "
                           f"{row['ratio']} bytes/line): {row['href']}",
                "url": row["href"],
            })
    if result["wasted_bytes"] > 20000:
        result["issues"].append({
            "severity": "medium",
            "message": f"~{result['wasted_bytes'] // 1024} KB recoverable by minifying CSS",
            "url": url,
        })
    return result


def main():
    parser = argparse.ArgumentParser(description="Check whether stylesheets are minified")
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
    print(f"CSS minification for {result['url']}")
    print(f"  stylesheets checked: {result['checked']}")
    print(f"  unminified:          {result['unminified_count']}")
    if result["wasted_bytes"]:
        print(f"  recoverable:         ~{result['wasted_bytes'] // 1024} KB")
    for row in result["stylesheets"]:
        state = "error" if row["error"] else ("min" if row["minified"] else "NOT MIN")
        print(f"  [{state}] {row['href'][:90]}")


if __name__ == "__main__":
    main()
