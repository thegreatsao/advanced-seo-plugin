#!/usr/bin/env python3
"""Compare robots.txt and llms.txt signals for AI crawlers."""

from __future__ import annotations

import argparse
import json

from seo_common import fetch_robots, fetch_url, normalize_url, origin, robots_allowed


# OpenAI splits its fetching across four tokens and blocking one does not block the
# others: `GPTBot` trains, `OAI-SearchBot` and `ChatGPT-User` answer, and `OAI-AdsBot`
# fetches the landing page of a ChatGPT ad. The last one is here because the failure it
# causes is not an SEO one — a site that disallows it has its ads **rejected at review**,
# which no other check in this registry would surface.
AI_CRAWLERS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "OAI-AdsBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "Applebot-Extended", "CCBot", "Bytespider", "Amazonbot"]


def matrix(site: str, paths: list[str] | None = None, timeout: int = 15) -> dict:
    base = origin(site)
    paths = paths or ["/", "/llms.txt", "/sitemap.xml"]
    robots = fetch_robots(base, timeout=timeout)
    llms = fetch_url(base + "/llms.txt", timeout=timeout, max_bytes=500_000)
    rows = []
    for crawler in AI_CRAWLERS:
        decisions = {}
        allowed_all = True
        for path in paths:
            url = normalize_url(path, base)
            allowed, rule = robots_allowed(robots.get("parsed"), url, crawler)
            decisions[path] = {"allowed": allowed, "rule": rule}
            allowed_all = allowed_all and allowed
        rows.append({
            "crawler": crawler,
            "policy": "allowed" if allowed_all else "restricted",
            "paths": decisions,
            "llms_txt_available": llms.get("status") == 200,
            "alignment": "documented" if llms.get("status") == 200 and allowed_all else "robots_only" if not allowed_all else "allowed_without_llms_txt",
        })
    # `fetch_error` so the runner can tell "this site allows GPTBot" from "nobody
    # answered". Without it a refused connection produced a full policy matrix built
    # entirely out of absent robots.txt rules, and GEO-003 graded it.
    return {"site": base, "robots_url": robots["url"],
            "robots_status": robots["fetch"].get("status"),
            "llms_txt_url": base + "/llms.txt", "llms_txt_status": llms.get("status"),
            "fetch_error": robots["fetch"].get("error") or llms.get("error"),
            "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build AI crawler policy matrix")
    parser.add_argument("site")
    parser.add_argument("--path", action="append", help="Path to test; repeatable")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--json", "-j", action="store_true")
    args = parser.parse_args()
    result = matrix(args.site, args.path, args.timeout)
    print(json.dumps(result, indent=2) if args.json else "\n".join(f"{r['crawler']}\t{r['policy']}\t{r['alignment']}" for r in result["rows"]))


if __name__ == "__main__":
    main()
