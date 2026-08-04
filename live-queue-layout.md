# LLM judgement queue — layout

Page under audit: http://127.0.0.1:8000/

Assigned agent: `seo-llm-layout`. Read the rendered page furniture: ads, pop-ups, navigation, menus.

12 checklist items need a judgement no script can make. Read the actual page content, then rule on each one. Do not guess from the URL or from this file alone — if the page does not give you enough to decide, answer `N/A` and say why.

For each item answer with one of:

- `PASS` — the page clearly satisfies it
- `FAIL` — the page clearly violates it (say exactly where)
- `WARN` — partially satisfied
- `N/A` — not applicable to this page, or undecidable from the content

Save the verdicts as JSON and merge them back:

```json
{ "CN-047": { "status": "PASS", "evidence": "no spelling or grammar errors in body copy" },
  "CN-060": { "status": "N/A",  "evidence": "cloaking cannot be judged from a single render" } }
```

```bash
python3 checklist_report.py checklist-results.json --llm-answers answers.json
```

Then have a second reader go through the same items independently and merge that with `--llm-review review.json`. Where the two agree the verdict says so; where they disagree the item returns to `NO_DATA` carrying both readings, because two careful readings that conflict mean the page did not settle it. The reviewer cannot overwrite a verdict — see `resources/agents/seo-llm-adversary.md`.

---

## Content

### CN-060 (critical)

**Do Not Cloak**

What good looks like: Do not serve different content to crawlers and users (cloaking)

### CN-059 (high)

**Avoid Hidden Text Meant to Manipulate**

What good looks like: Remove hidden text added to manipulate rankings

### CN-061 (high)

**Avoid Doorway Pages**

What good looks like: Remove doorway pages - query-targeted pages with no standalone value

### CN-052 (medium)

**Limit Heavy Above-the-Fold Ads**

What good looks like: Limit heavy advertising above the fold

### CN-055 (medium)

**Make Infinite Scroll Crawlable (Paginated URLs)**

What good looks like: Make infinite scroll crawlable via paginated URLs

### CN-062 (medium)

**Avoid Excessive Ad Density**

What good looks like: Reduce ad density

### CN-063 (medium)

**Do Not Overuse Pop-Ups**

What good looks like: Do not overuse pop-ups

## Mobile

### MB-101 (low)

**Make Mobile Navigation Thumb-Friendly**

What good looks like: Keep mobile navigation within thumb reach

## Website Architecture

### AR-161 (medium)

**Design Clear Menus (Header & Mobile)**

What good looks like: Clear header and mobile menus

### AR-157 (low)

**Use Tag Pages Strategically**

What good looks like: Use tag pages deliberately rather than generating duplicates

### AR-159 (low)

**Simplify Primary Navigation**

What good looks like: Simplify primary navigation

### AR-160 (low)

**Optimize Footer Navigation**

What good looks like: Optimize footer navigation

