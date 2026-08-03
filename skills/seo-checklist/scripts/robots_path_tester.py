#!/usr/bin/env python3
"""Test URL paths against robots.txt for multiple crawlers."""

from __future__ import annotations

import argparse
import json

from seo_common import fetch_robots, normalize_url, robots_allowed


DEFAULT_AGENTS = ["Googlebot", "Bingbot", "GPTBot", "ChatGPT-User", "ClaudeBot", "PerplexityBot", "Google-Extended", "Applebot-Extended", "CCBot"]


def test_paths(site: str, paths: list[str], agents: list[str], timeout: int = 15) -> dict:
    robots = fetch_robots(site, timeout=timeout)
    rows = []
    for path in paths:
        url = normalize_url(path, site)
        decisions = {}
        for agent in agents:
            allowed, rule = robots_allowed(robots.get("parsed"), url, agent)
            decisions[agent] = {"allowed": allowed, "rule": rule}
        rows.append({"url": url, "decisions": decisions,
                     "allowed_for": sorted(a for a, d in decisions.items() if d["allowed"])})
    # The paths these tests exist to keep out of the index, flattened into one
    # list. A checklist assertion can then say "this must be empty" instead of
    # matching text across a nested structure — where "allowed" and "true" never
    # land in the same string, so the pattern never fired and every site passed.
    reachable = sorted({row["url"] for row in rows if row["allowed_for"]})
    unreachable_robots = robots["fetch"].get("status") not in (200, 404)
    out = {"site": normalize_url(site), "robots_url": robots["url"],
           "robots_status": robots["fetch"].get("status"), "rows": rows}
    # No robots.txt answer means no verdict: a 500 or a timeout says nothing about
    # what is allowed, and an empty list would read as "nothing is exposed".
    if not unreachable_robots:
        out["allowed_urls"] = reachable
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Test paths against robots.txt")
    parser.add_argument("site")
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--agent", action="append", help="Crawler user-agent; repeatable")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true")
    args = parser.parse_args()
    result = test_paths(args.site, args.paths, args.agent or DEFAULT_AGENTS, args.timeout)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for row in result["rows"]:
            print(row["url"])
            for agent, decision in row["decisions"].items():
                print(f"  {agent}: {'allowed' if decision['allowed'] else 'blocked'} ({decision['rule']})")


if __name__ == "__main__":
    main()
