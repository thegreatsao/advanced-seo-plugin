# LLM judgement queue — copy

Page under audit: http://127.0.0.1:8000/

Assigned agent: `seo-llm-copy`. Read the body text: prose quality, originality, intent match.

18 checklist items need a judgement no script can make. Read the actual page content, then rule on each one. Do not guess from the URL or from this file alone — if the page does not give you enough to decide, answer `N/A` and say why.

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

## Meta & Structured Data

### MS-024 (medium)

**Place Primary Keyword Early in the Title**

What good looks like: Lead the title with the main topic

### MS-025 (medium)

**Make Titles Accurately Describe the Content**

What good looks like: The title must accurately describe the page content and intent

## Content

### CN-043 (high)

**Avoid Scraped/Plagiarized Content**

What good looks like: Remove scraped or lightly-rewritten third-party content

### CN-050 (high)

**Follow Google Search Essentials (Quality/Spam Policies)**

What good looks like: Follow Google Search Essentials - quality and spam policies

### CN-067 (high)

**Publish People-First Content (AI-Assisted Is Fine)**

What good looks like: Publish people-first content; AI assistance is fine when the result helps a human

### CN-042 (medium)

**Address External Duplicates/Syndication**

What good looks like: Review external duplicates and syndication, agree on a canonical to the source

### CN-046 (medium)

**Review Copy Quality and Content Classification**

What good looks like: Review copy quality and content classification

### CN-047 (medium)

**Check Grammar and Spelling**

What good looks like: Check grammar and spelling

### CN-049 (medium)

**Target Topics and Queries (Not Just Keywords)**

What good looks like: Target topics and queries, not isolated keywords

### CN-037 (low)

**Differentiate Primary vs. Supplementary Content**

What good looks like: Separate primary from supplementary content visually and semantically

### CN-058 (low)

**Avoid Content Flagged by SafeSearch**

What good looks like: Check whether the content risks being flagged by SafeSearch

### CN-064 (low)

**Use Clear Calls to Action**

What good looks like: Use clear, explicit calls to action

## Keyword Analysis

### KW-072 (high)

**Use the Primary Topic in the Title**

What good looks like: Put the primary topic in the title

### KW-073 (high)

**Include the Primary Keyword in the H1**

What good looks like: Include the primary keyword in the H1

### KW-074 (medium)

**Include the Primary Keyword (or Close Variant) in an H2**

What good looks like: Include the primary keyword or a close variant in an H2

### KW-075 (medium)

**Include the Primary Keyword in the Meta Description (for CTR)**

What good looks like: Include the primary keyword in the meta description - it affects CTR

### KW-077 (medium)

**Include the Primary Keyword in the Opening Paragraph**

What good looks like: Include the primary keyword in the opening paragraph

## Images / Video

### MD-188 (low)

**Use Original, Contextual Images (Limit Stock)**

What good looks like: Use original contextual images, limit stock photography

