#!/usr/bin/env python3
"""
Validate a page against the W3C Nu HTML Checker.

Uses the free public validator.w3.org/nu endpoint — no API key. Invalid markup
degrades rendering, accessibility and parsing, which is why Plerdy's checklist
raises it in three separate places.

Usage:
    python html_validator.py https://example.com
    python html_validator.py https://example.com --json
"""

import argparse
import json
import sys
import time
from urllib.parse import urlencode

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    from lib.safe_http import default_headers, pace, retry_after_seconds
except ImportError:
    from scripts.lib.safe_http import default_headers, pace, retry_after_seconds

NU_ENDPOINT = "https://validator.w3.org/nu/"
# basis: inherited — 40, present at import. A cap on how much of Nu's answer is carried
#  forward, not a verdict: a page with more than 40 validation errors is already failing
#  the item
MAX_MESSAGES = 40


def validate(url: str, timeout: int = 45) -> dict:
    result = {
        "url": url,
        # Empty until the validator answers. `{"errors": None}` is not silence:
        # `eq: 0` reads a None as a failing value, so an outage or a 429 from a free
        # service reported "your HTML has validation errors" — CI-017 and TE-181,
        # invented out of the validator being busy. An absent key is NO_DATA.
        "summary": {},
        "messages": [],
        "issues": [],
        "error": None,
    }
    query = urlencode({"doc": url, "out": "json"})
    # This is the one script that calls requests directly rather than through
    # safe_request, because it addresses a fixed third-party endpoint rather than
    # the audited site. It still has to be paced: the W3C validator is a free
    # service and this asks it to fetch a page on our behalf.
    try:
        pace("validator.w3.org")
        resp = requests.get(f"{NU_ENDPOINT}?{query}",
                            headers=default_headers({"Accept": "application/json"}),
                            timeout=timeout)
        wait = retry_after_seconds(resp)
        if 0 < wait <= 30:
            time.sleep(wait)
            pace("validator.w3.org")
            resp = requests.get(f"{NU_ENDPOINT}?{query}",
                                headers=default_headers({"Accept": "application/json"}),
                                timeout=timeout)
    except requests.RequestException as exc:
        result["error"] = f"validator unreachable: {exc}"
        return result

    if resp.status_code != 200:
        result["error"] = f"validator returned HTTP {resp.status_code}"
        return result

    try:
        payload = resp.json()
    except ValueError:
        result["error"] = "validator returned non-JSON output"
        return result

    messages = payload.get("messages", [])
    # Nu answered, about nothing. `non-document-error` is how it reports that *it*
    # could not fetch or decode the URL — a 403 aimed at its user agent, a timeout, a
    # TLS problem, a host it cannot reach. None of those is a document error, so
    # `errors` came out 0 and CI-017 and TE-181 reported "your HTML validates" about a
    # page the validator never saw. The same shape as the outage guarded against
    # above, one step further in: the service answered, and the answer was not about
    # the page.
    blocked = [m for m in messages if m.get("type") == "non-document-error"]
    if blocked and len(blocked) == len(messages):
        detail = (blocked[0].get("message") or blocked[0].get("subType")
                  or "no detail given")
        result["error"] = f"validator could not read the page: {detail[:160]}"
        return result

    counts = {"error": 0, "warning": 0, "info": 0}
    for m in messages:
        kind = m.get("type", "info")
        # Nu reports fatal parse failures as type=error subType=fatal.
        bucket = "error" if kind == "error" else ("warning" if kind == "warning" else "info")
        counts[bucket] += 1
        if len(result["messages"]) < MAX_MESSAGES:
            result["messages"].append({
                "type": kind,
                "subType": m.get("subType", ""),
                "message": m.get("message", "")[:300],
                "line": m.get("lastLine"),
                "extract": (m.get("extract") or "").strip()[:160],
            })

    result["summary"] = {"errors": counts["error"], "warnings": counts["warning"],
                         "info": counts["info"]}

    if counts["error"]:
        first = next((m for m in result["messages"] if m["type"] == "error"), {})
        result["issues"].append({
            "severity": "medium",
            "message": f"{counts['error']} HTML validation error(s); first: "
                       f"{first.get('message', '')[:160]}",
            "url": url,
        })
    if counts["warning"] > 10:
        result["issues"].append({
            "severity": "low",
            "message": f"{counts['warning']} HTML validation warnings",
            "url": url,
        })
    return result


def main():
    parser = argparse.ArgumentParser(description="Validate HTML via the W3C Nu checker")
    parser.add_argument("url", help="URL to validate")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    result = validate(args.url, args.timeout)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if result["error"]:
        print(f"Could not validate: {result['error']}")
        return
    s = result["summary"]
    print(f"W3C validation for {result['url']}")
    print(f"  errors:   {s['errors']}")
    print(f"  warnings: {s['warnings']}")
    for m in result["messages"][:15]:
        line = f" (line {m['line']})" if m["line"] else ""
        print(f"  [{m['type']}]{line} {m['message'][:120]}")


if __name__ == "__main__":
    main()
