# LLM judgement queue — market

Page under audit: http://127.0.0.1:8000/

Assigned agent: `seo-llm-market`. Read competitive and geographic positioning.

3 checklist items need a judgement no script can make. Read the actual page content, then rule on each one. Do not guess from the URL or from this file alone — if the page does not give you enough to decide, answer `N/A` and say why.

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

## Competition Analysis

### CO-191 (medium)

**Identify Top 3–5 Competitors**

What good looks like: Identify the top 3-5 competitors in the SERP

## Local SEO

### LO-196 (medium)

**Confirm Local Traffic Need**

What good looks like: Determine whether the site needs local traffic

### LO-197 (medium)

**Use Localized Title Tags**

What good looks like: Localized title tags

