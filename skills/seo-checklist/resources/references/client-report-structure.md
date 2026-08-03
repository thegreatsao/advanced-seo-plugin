<!--
Bundled reference. Adapted from the `competitive-report-structure` skill in
Everything Claude Code (https://github.com/affaan-m/ECC), MIT licensed,
Copyright (c) 2026 Affaan Mustafa. Copied in rather than referenced so the audit
does not depend on a separate plugin being installed. See CREDITS.md.
-->

# Client-facing report structure

`CHECKLIST-REPORT.md` is complete and correct, and it is also a list of statuses.
That is the right shape for someone fixing the site and the wrong shape for
someone deciding whether to fund the work. This is how to restructure the same
findings for a client or a decision meeting.

**It changes presentation only.** No status, no score, no coverage number moves
because a report was reshaped. If reformatting appears to improve the result,
something has gone wrong.

Run it after the LLM queue is answered and, where competitors matter, after
[competitor-research.md](../playbooks/competitor-research.md) — this expects
findings to exist, it does not produce them.

## Sections

### 1. Executive summary
Three to five takeaways, decision-first, in plain language: where the site is
strong, where it is exposed, and the top two or three moves. Written so someone
who reads only this knows what to do. **No methodology here** — that belongs in
the appendix.

State both numbers in the first paragraph. A score without its coverage is the
single easiest way to mislead a client, and the omission usually flatters.

### 2. What was checked, and what was not
The coverage story, before any findings. How many items applied under this
profile and mode, how many were decided, and what the undecided ones were waiting
on — credentials, a crawl, a human, an API that does not exist.

Clients read silence as approval. Say plainly that `NO_DATA` is not a pass.

### 3. Priority actions
The ranked fix list from the report: severity against effort, highest first, with
the low-effort block called out separately. Each row states the evidence, not
just the rule. "Title is 61 characters on 1 of 5 sampled pages" travels; "title
too long" does not.

### 4. Findings by theme
Group the failures into four or five themes — indexing, content, speed, trust —
rather than the fifteen registry categories. Categories are a filing system; a
client needs a story.

### 5. Competitive position
Only when competitor research was actually run. Tiered set, what they do better,
what the site owns. Name URLs.

Skip this section entirely when CO-191 came back `N/A`. An empty competitive
section is honest; a speculative one is the part a client will quote back later.

### 6. What needs a decision
The items that are `MANUAL` because they need budget, access or a business
choice — Business Profile ownership, link outreach, translation quality. These
are not failures of the site; they are unmade decisions. Present them as such.

### 7. Appendix
Registry version, profile, mode, sampled URLs, run date, the full item table, and
which checks could not run. This is what makes the report auditable six months
later when someone asks whether a thing was ever checked.

## Presentation

- Lead with the two metrics, never one, and never a blended composite.
- Tables scannable; raw evidence pushed to the appendix.
- One claim per row, with the evidence that produced it.
- Percentages always carry their denominator.

## Anti-patterns

- **Opening with methodology.** The summary opens with the most important
  finding.
- **A single number.** Collapsing score and coverage produces something that
  sounds more confident than the audit was.
- **Quietly dropping `NO_DATA`.** Undecided items must appear; hiding them turns
  a thin audit into a clean bill of health.
- **A competitive section without a search.** See CO-191 — `N/A` is the answer.
- **Restructuring before the LLM queue is answered.** Thirty pending items is a
  third of what a client is paying attention to.
- **Reformatting that changes a verdict.** If it does, the bug is upstream.
