#!/usr/bin/env python3
"""Read measurements taken from a rendered page.

Like `cwv_metrics.py`, this script measures nothing: it reads a JSON file produced
by a real browser — in Claude Code, the chrome-devtools MCP running one
`evaluate_script` against the loaded page. The registry then decides from numbers
instead of from a judgement.

Five checklist items were moved to the LLM queue in August 2026 because the scripts
they claimed to use had never looked at what they asked about (see
`tools/audit_assertions.py`). A model reading HTML is an honest answer for them, but
it is a weaker one than it looks: font size, link styling, hit areas and overlays
are all *computed* values. They depend on stylesheets, media queries and scripts
that HTML alone does not settle, and a model that says "the body text looks fine"
has not measured anything. These are measurable, so they are measured.

Expected shape — every metric optional, and absent rather than zero when it was
not measured:

    {
      "url": "https://example.com/",
      "viewport": {"width": 375, "height": 812},
      "source": "chrome-devtools MCP evaluate_script, 2026-08-03",
      "text_nodes_below_12px": 0,
      "links_indistinct": 2,
      "overlays_covering_content": 0,
      "tap_targets_below_48px": 3
    }

`SKILL.md` carries the snippet that produces it.

**Tap targets and mobile interstitials are only reported from a mobile render.**
A desktop trace says nothing about either, and passing them from one would be a
fabricated verdict about a viewport nobody looked at — so those keys are dropped
unless the recorded viewport is narrow enough, and the items then report NO_DATA.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# basis: convention — 480px, a common CSS breakpoint. The exact number matters less than
#  refusing to answer tap-target and mobile-interstitial questions from a desktop render
#  at all
MOBILE_MAX_WIDTH = 480

# Metrics that describe the page at any viewport.
GENERAL_METRICS = ("text_nodes_below_12px", "links_indistinct",
                   "overlays_covering_content")
# Metrics that mean nothing unless the render was a phone.
MOBILE_METRICS = ("tap_targets_below_48px", "mobile_overlays_covering_content")


def read(path: str) -> dict:
    """Parse the measurement file. Raises ValueError with something actionable."""
    if not os.path.exists(path):
        raise ValueError(f"no such file: {path}")
    with open(path, encoding="utf-8") as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} is not JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must hold a JSON object, found {type(raw).__name__}")

    viewport = raw.get("viewport") if isinstance(raw.get("viewport"), dict) else {}
    width = viewport.get("width")
    if isinstance(width, bool) or not isinstance(width, (int, float)):
        raise ValueError("viewport.width is required and must be a number — without "
                         "it there is no way to know whether the mobile metrics "
                         "describe a phone or a desktop window")
    is_mobile = width <= MOBILE_MAX_WIDTH

    out = {
        "url": raw.get("url"),
        "source": raw.get("source") or "unspecified",
        "viewport": {"width": width, "height": viewport.get("height")},
        "viewport_class": "mobile" if is_mobile else "desktop",
        "measured": [],
        "missing": [],
    }

    for key in GENERAL_METRICS + MOBILE_METRICS:
        value = raw.get(key)
        # `mobile_overlays_covering_content` is derived rather than supplied: the
        # measurement is the same one, what changes is whether the viewport makes
        # it an answer about phones.
        if key == "mobile_overlays_covering_content" and value is None:
            value = raw.get("overlays_covering_content")
        if value is None:
            out["missing"].append(key)
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a count, found {value!r}")
        if value < 0:
            raise ValueError(f"{key} is negative ({value})")
        if key in MOBILE_METRICS and not is_mobile:
            # Dropped, not zeroed. A desktop render cannot answer a question about
            # tap targets, and reporting 0 would be a verdict about a viewport
            # nobody looked at.
            out["missing"].append(f"{key} (needs a mobile render; this one was "
                                  f"{int(width)}px wide)")
            continue
        out[key] = value
        out["measured"].append(key)

    if not out["measured"]:
        raise ValueError(
            f"{path} carries none of {', '.join(GENERAL_METRICS + MOBILE_METRICS)}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Report measurements from a rendered page",
                                 epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="JSON file written from a browser measurement")
    ap.add_argument("--json", "-j", action="store_true")
    a = ap.parse_args()

    try:
        result = read(a.path)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    if a.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"Rendered page measurements for {result['url'] or 'unknown URL'}")
    print(f"  source:   {result['source']}")
    print(f"  viewport: {result['viewport']['width']}px ({result['viewport_class']})")
    for key in result["measured"]:
        print(f"  {key}: {result[key]}")
    for key in result["missing"]:
        print(f"  {key}: not measured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
