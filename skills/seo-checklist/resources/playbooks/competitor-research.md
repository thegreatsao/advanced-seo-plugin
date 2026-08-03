<!--
Bundled playbook. Adapted from the `deep-research` skill in Everything Claude
Code (https://github.com/affaan-m/ECC), MIT licensed, Copyright (c) 2026 Affaan
Mustafa. Copied in rather than referenced so the audit does not depend on a
separate plugin being installed. See CREDITS.md for the full notice.
-->

# Competitor research playbook

Answers the checklist items no crawler can: **CO-191** (who the real competitors
are), **CO-192…195** (benchmarks, their keywords, their positions), and
**BL-088** (topically relevant sites worth earning links from).

## The one rule

**No search, no verdict.** If you did not actually look at a result set, CO-191
is `N/A` with "no search was run" as the evidence. A competitor list assembled
from memory is fabrication with a confident tone, and it is worse than an honest
blank: it looks like a finding, so nobody goes back to check it.

## What you need

At least one search tool. In order of preference:

1. **firecrawl MCP** — `firecrawl_search`, `firecrawl_scrape`
2. **exa MCP** — `web_search_exa`, `web_search_advanced_exa`, `crawling_exa`
3. **WebSearch / WebFetch** — the built-in tools, if neither MCP is configured

The MCP servers give better coverage and full-page reads; the built-ins are
enough to answer CO-191 honestly. **If none of the three is available, stop and
report `N/A`** — do not fall back to recall.

## Workflow

### 1. Fix the query set

Start from the page's own subject, not the site's marketing. Take the primary
query from the title, the H1 and the highest-click Search Console query if GSC is
configured. Two or three queries, not ten.

### 2. Search each query

```
firecrawl_search(query: "<query>", limit: 8)
web_search_exa(query: "<query>", numResults: 8)
```

Use two keyword variations per query. Record the URLs that actually rank, in
order. That ordered list *is* the answer to CO-191 — everything below is
elaboration.

### 3. Tier what you found

- **Direct** — competes for the same query with the same intent
- **Adjacent** — ranks for the query but serves a different need
- **Aspirational** — the site the client wishes it looked like

A directory, a marketplace listing, or a review aggregator outranking the page is
a **Direct** competitor even though nobody would call it a rival company. This is
the most common mistake in this block: naming business rivals instead of search
rivals.

### 4. Read the top three in full

```
firecrawl_scrape(url: "<url>")
crawling_exa(url: "<url>", tokensNum: 5000)
```

Search snippets are not enough to judge why a page outranks another. Read the
whole thing: depth, structure, freshness, evidence, schema.

### 5. Record, with sources

For each competitor: URL, tier, what it does better, what it does worse. Every
claim carries the URL it came from. Anything you inferred rather than saw is
labelled as inference.

## Answering the items

| Item | What satisfies it |
|---|---|
| CO-191 | 3–5 named URLs that actually ranked, with the query they ranked for |
| CO-192 | the tiered table with per-competitor strengths and weaknesses |
| CO-193 | each competitor's visible target keywords, taken from their pages |
| CO-194 | positions observed in the result set, dated |
| CO-195 | the union of ranking keywords across the set |
| BL-088 | sites topically adjacent to the page that link out at all |

CO-193…195 degrade honestly: without rank-tracking data you can report what you
observed on the day, dated, and say it is a single observation rather than a
trend. Do not present one snapshot as a tracked position.

## Anti-patterns

- **Naming business rivals instead of search rivals.** The SERP decides who you
  compete with, not the industry.
- **One query.** A page ranks for a cluster; a single query gives a distorted set.
- **Snippet-only judgement.** You cannot tell why a page wins from 160 characters.
- **Undated positions.** A position without a date is not evidence a month later.
- **Filling gaps from memory** when a search fails. Report the gap.
