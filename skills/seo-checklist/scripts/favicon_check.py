#!/usr/bin/env python3
"""Fetch a page's declared favicon and measure whether it can display at 48 px."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET

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

try:
    from seo_common import favicon_href, html_parser, issue
except ImportError:
    from scripts.seo_common import favicon_href, html_parser, issue


# basis: standard — Google Search requires favicon dimensions that are a multiple of 48px; this check enforces only that documented 48px floor, on the shorter side.
MIN_FAVICON_SIDE_PX = 48
MAX_ICON_BYTES = 2_000_000


def _positive_dimensions(width: int, height: int) -> tuple[int, int] | None:
    return (width, height) if width > 0 and height > 0 else None


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if (data[:8] != b"\x89PNG\r\n\x1a\n" or data[8:12] != b"\x00\x00\x00\x0d"
            or data[12:16] != b"IHDR" or len(data[:33]) != 33):
        return None
    return _positive_dimensions(*struct.unpack(">II", data[16:24]))


def _ico_dimensions(data: bytes) -> tuple[int, int] | None:
    if data[:4] != b"\x00\x00\x01\x00" or len(data[4:6]) != 2:
        return None
    count = int.from_bytes(data[4:6], "little")
    if count < 1 or len(data) < 6 + count * 16:
        return None
    sizes = []
    for offset in range(6, 6 + count * 16, 16):
        width = data[offset] or 256
        height = data[offset + 1] or 256
        sizes.append((width, height))
    # An ICO is a menu of representations. Clients choose the largest suitable one,
    # so judging only its first (often 16px) entry would reject a usable icon.
    return max(sizes, key=lambda size: (min(size), size[0] * size[1]))


def _gif_dimensions(data: bytes) -> tuple[int, int] | None:
    if data[:6] not in (b"GIF87a", b"GIF89a") or len(data[6:10]) != 4:
        return None
    return _positive_dimensions(*struct.unpack("<HH", data[6:10]))


JPEG_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if data[:2] != b"\xff\xd8":
        return None
    cursor = 2
    while cursor < len(data):
        while cursor < len(data) and data[cursor] != 0xFF:
            cursor += 1
        while cursor < len(data) and data[cursor] == 0xFF:
            cursor += 1
        if cursor >= len(data):
            return None
        marker = data[cursor]
        cursor += 1
        if marker in (0x01, 0xD8, 0xD9) or marker in range(0xD0, 0xD8):
            continue
        if cursor + 2 > len(data):
            return None
        segment_length = int.from_bytes(data[cursor:cursor + 2], "big")
        if segment_length < 2 or cursor + segment_length > len(data):
            return None
        if marker in JPEG_SOF_MARKERS:
            if len(data[cursor:cursor + 7]) != 7:
                return None
            height = int.from_bytes(data[cursor + 3:cursor + 5], "big")
            width = int.from_bytes(data[cursor + 5:cursor + 7], "big")
            return _positive_dimensions(width, height)
        cursor += segment_length
    return None


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    cursor = 12
    while cursor + 8 <= len(data):
        kind = data[cursor:cursor + 4]
        size = int.from_bytes(data[cursor + 4:cursor + 8], "little")
        payload = cursor + 8
        if payload + size > len(data):
            return None
        if kind == b"VP8X" and len(data[payload:payload + 10]) == 10:
            width = 1 + int.from_bytes(data[payload + 4:payload + 7], "little")
            height = 1 + int.from_bytes(data[payload + 7:payload + 10], "little")
            return _positive_dimensions(width, height)
        if (kind == b"VP8L" and len(data[payload:payload + 5]) == 5
                and data[payload] == 0x2F):
            b1, b2, b3, b4 = data[payload + 1:payload + 5]
            width = 1 + b1 + ((b2 & 0x3F) << 8)
            height = 1 + (b2 >> 6) + (b3 << 2) + ((b4 & 0x0F) << 10)
            return _positive_dimensions(width, height)
        if (kind == b"VP8 " and len(data[payload:payload + 10]) == 10
                and data[payload + 3:payload + 6] == b"\x9d\x01\x2a"):
            width = int.from_bytes(data[payload + 6:payload + 8], "little") & 0x3FFF
            height = int.from_bytes(data[payload + 8:payload + 10], "little") & 0x3FFF
            return _positive_dimensions(width, height)
        cursor = payload + size + (size % 2)
    return None


def _svg_dimensions(root) -> tuple[int, int] | None:
    def pixels(value: str | None) -> int | None:
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:px)?\s*", value or "", re.I)
        if not match:
            return None
        number = float(match.group(1))
        return round(number) if number > 0 else None

    width, height = pixels(root.get("width")), pixels(root.get("height"))
    if width and height:
        return width, height
    view_box = re.split(r"[\s,]+", (root.get("viewBox") or "").strip())
    if len(view_box) == 4:
        try:
            return _positive_dimensions(round(float(view_box[2])), round(float(view_box[3])))
        except ValueError:
            pass
    return None


def image_header(data: bytes) -> tuple[str, int | None, int | None] | None:
    """Return a recognised image format and its intrinsic dimensions."""
    probes = (
        ("png", _png_dimensions),
        ("ico", _ico_dimensions),
        ("gif", _gif_dimensions),
        ("jpeg", _jpeg_dimensions),
        ("webp", _webp_dimensions),
    )
    for name, probe in probes:
        dimensions = probe(data)
        if dimensions:
            return name, dimensions[0], dimensions[1]
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, ValueError):
        return None
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        return None
    dimensions = _svg_dimensions(root)
    return ("svg", dimensions[0], dimensions[1]) if dimensions else ("svg", None, None)


def check(url: str, timeout: int = 15) -> dict:
    result = {
        "url": url,
        "favicon": {
            "declared": None,
            "href": None,
            "url": None,
            "status": None,
            "content_type": None,
            "format": None,
            "width": None,
            "height": None,
            "min_side_px": None,
        },
        "issues": [],
        "fetch_error": None,
    }
    favicon = result["favicon"]
    try:
        page = safe_get(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — an unread page is evidence, not a crash
        reason = f"Page could not be fetched: {str(exc)[:200]}"
        result["fetch_error"] = reason
        favicon["reason"] = reason
        return result
    if page.status_code >= 400:
        reason = f"Page could not be fetched: HTTP {page.status_code}"
        result["fetch_error"] = reason
        favicon["reason"] = reason
        return result

    soup = BeautifulSoup(page.text, html_parser())
    declared = favicon_href(soup)
    resolved = favicon_href(soup, page.url)
    favicon.update({"declared": bool(resolved), "href": declared, "url": resolved})
    if not resolved:
        reason = "No favicon is declared on the page"
        favicon.update({"displays_at_48px": False, "reason": reason})
        result["issues"].append(issue("low", reason, page.url))
        return result

    try:
        response = safe_get(resolved, timeout=timeout, max_response_bytes=MAX_ICON_BYTES)
        favicon["status"] = response.status_code
        favicon["content_type"] = response.headers.get("Content-Type")
    except Exception as exc:  # noqa: BLE001 — a declared but unreachable icon is a defect
        reason = f"Declared favicon is unreachable: {str(exc)[:160]}"
        favicon.update({"displays_at_48px": False, "reason": reason})
        result["issues"].append(issue("low", reason, resolved))
        return result
    if response.status_code >= 400:
        reason = f"Declared favicon is unreachable: HTTP {response.status_code}"
        favicon.update({"displays_at_48px": False, "reason": reason})
        result["issues"].append(issue("low", reason, resolved))
        return result

    measured = image_header(response.content)
    if measured is None:
        favicon["reason"] = "Favicon format is not recognised; dimensions could not be measured"
        return result
    format_name, width, height = measured
    favicon.update({"format": format_name, "width": width, "height": height})
    if format_name == "svg":
        # SVG is vector: once fetched and recognised it can render at 48px regardless
        # of its intrinsic width, height or viewBox.
        favicon.update({
            "displays_at_48px": True,
            "reason": "Favicon is a resolvable SVG and can render at 48x48",
        })
        return result

    min_side = min(width, height)
    displays = min_side >= MIN_FAVICON_SIDE_PX
    reason = (f"Favicon measures {width}x{height}; shorter side {min_side}px "
              f"{'meets' if displays else 'is below'} the {MIN_FAVICON_SIDE_PX}px floor")
    favicon.update({"min_side_px": min_side, "displays_at_48px": displays,
                    "reason": reason})
    if not displays:
        result["issues"].append(issue("low", reason, resolved))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether a favicon can display at 48px")
    parser.add_argument("url", help="Page URL to check")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    result = check(args.url, args.timeout)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(result["favicon"].get("reason", "No favicon result"))
    for finding in result["issues"]:
        print(f"[{finding['severity']}] {finding['message']}")


if __name__ == "__main__":
    main()
