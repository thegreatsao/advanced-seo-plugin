# Roadmap to 1.0

`KNOWN-ISSUES.md` says what is wrong. This says where it stops.

A version number that does not mean anything is a number nobody can argue with, so
1.0 is defined here as a claim that can be checked:

> **Every item in the registry either carries a verdict or a stated structural reason
> it cannot; every number a verdict rests on is either measured or declared unmeasured;
> and the document says what the code does.**

Three releases reach it. Nothing below adds a check to the registry.

---

## Where the numbers actually are

Measured, not estimated — one live run against `tests/fixtures/good` served on
loopback, `--sample 3`, no Search Console key, no supplied artifacts:

```
SEO Score 69/100   Coverage 50% (106/214)
PASS 72   WARN 3   FAIL 31   NO_DATA 38   LLM_PENDING 36   MANUAL 34
```

That single 50% is three unrelated facts added together:

| Answered by | Items | Decided | What its zero means |
|---|---|---|---|
| a script, measured | 144 | 106 | the tool's own reach |
| a model reading the page | 36 | **0** | the operator has not run the queue |
| a person | 34 | **0** | the audit was never going to answer these |

Adding them produces a number whose movement cannot be attributed. Coverage falling
from 62% to 50% between two audits reads as the site becoming harder to measure, when
it may only mean nobody answered `LLM-QUEUE.md` this time. **This is the failure this
project was built to prevent — merging Score with Coverage — repeated one level
down**, and it has been in every report since 0.1.0.

The weighting makes it sharper than the counts do. Under `SEVERITY_WEIGHT` the
registry carries 890 points: 658 machine, 116 model, 116 human. The two groups
sitting at zero are **26% of the weight the score is computed over**. A run reporting
69/100 is reporting a figure derived from three quarters of the registry, and says so
nowhere.

### What the 38 undecided machine items are

Also measured, from the same run, and this is the more actionable split:

| Cause | Items | Whose problem |
|---|---|---|
| no external service can reach a loopback host | 21 | the fixture's, not a real site's |
| a supplied input was not supplied | 13 | the operator's — `--rendered-json` 5, `--links-csv` 3, `--cwv-json` 3, `--server-log` 1, `INDEXNOW_KEY` 1 |
| a field the assertion reads was absent | 4 | genuinely undecidable from what the site served |

Only the last row is the tool failing to decide. On a public site with every optional
input supplied the machine group reaches **140 of 144**. Reporting all three as one
`NO_DATA` count tells the person running the audit nothing about which of them is
their own unfinished work.

---

## 0.16 — coverage stops being a percentage and becomes a partition

**Shipped: the reporting half.** The composite is gone, the score carries its weight
share, the partition is printed in both renderers and in Russian, `NEEDS_INPUT` is a
status with its own section, and a test asserts the buckets sum to the registry.
Registry unchanged; 13 items moved `NO_DATA` → `NEEDS_INPUT` and no verdict moved at
all. **Still open in this release:** dispatching the lens agents, `--manual-answers`,
and `decided_by`.

There is no compatibility constraint here. `.seo-runs/` does not exist, no run has
ever been archived, and the plugin has no users outside this repository. So the
question is what the right design is, not what the cheapest migration is.

**Delete the composite `Coverage %`.** It is the average of three quantities that
measure different things — how far the tool reaches, how much work the operator has
done, and how much of the registry was never the audit's job. A number that moves for
three unrelated reasons cannot be attributed by the person reading it, which is the
whole objection this project raises to a single SEO score.

**The score carries its own weight share instead**, because that is the claim a reader
actually needs to check:

```
SEO Score 69/100 — over 106 items, 55% of the weight in scope
```

489 of 890 points. `96/100 at 19%` reads wrong on sight, which is the founding
requirement and is what `Coverage` was reaching for and missing.

**Under it, a partition of all 214 by whose action moves it.** Not percentages —
buckets that sum to the registry, so no item can hide in a denominator:

| Bucket | Items | Who moves it |
|---|---|---|
| decided | 106 | — the score is computed over these |
| waiting on you | 49 | the operator: 36 unanswered queue items, 13 missing input files |
| needs a person | 34 | a human, in the Search Console UI or by looking |
| undecided | 25 | nobody: the site served no such field, or a service was unreachable |
| not applicable | 0 | out of scope for this mode or profile |

`106 + 49 + 34 + 25 + 0 = 214`, and a test asserts exactly that.

The undecided bucket does **not** separate the 21 items no external service could
reach from the 4 the site served no field for, and that is deliberate: neither is
anybody's to-do, telling them apart would need a status per cause, and the 21 exist
only because this measurement was taken against loopback. On a public site that
bucket is 4. The causes are already in each item's stated reason.

**`NO_DATA` splits, because the partition must come from statuses and not from
prose.** It currently means four different things at once — an external service was
unreachable, an input file was not supplied, the site served no such field, the script
died. Producing the table above today requires substring-matching the evidence text,
which is the kind of thing that breaks silently and is exactly what this repository
keeps finding. Add `NEEDS_INPUT` as a status of its own; the report then reads
statuses, and "you did not pass `--cwv-json`" stops printing as "the audit could not
tell".

**Close the model group.** 36 items — 17% of the registry, 116 points of weight — sit
at `LLM_PENDING` because answering them means running four agents by hand, saving JSON
by hand, and merging by hand. The runner should dispatch the lens agents and merge
their answers itself. No new check; the largest single coverage gain available
anywhere in this plan.

**Give the human group a way to answer.** `--llm-answers` exists and merges only
`LLM_PENDING`; `--manual-answers` should mirror it exactly and merge only `MANUAL`.
The mechanism is already half-built and stranded: `CHECKLIST.html` persists the
`MANUAL` checkboxes in `localStorage`, so a person's answers exist in a browser and
never return to the artifact. Export them.

With that, every bucket except the two nobody controls can be emptied, and the
84% ceiling — 180 of 214, the most the audit can decide on its own — stops being a
ceiling at all.

**The hazard this opens, and its guard.** A human who can answer 34 items can type
`PASS` 34 times and raise the score. This is the same hazard as a profile narrowing
scope, and it gets the same treatment: every item records `decided_by` —
`measured` / `model` / `claimed` — the artifact carries it, and the report prints the
three coverages so a reader can see how much of the verdict is somebody's word. The
adversary agent's rule is the precedent: a second reading may withdraw confidence and
never grant it.

---

## 0.17 — the two tables that produce the headline number

`measured` is 0 across 113 thresholds. Do not attack 113. Attack two:

```
SEVERITY_WEIGHT = {"critical": 10, "high": 6, "medium": 3, "low": 1}   # inherited
EFFORT_COST     = {"low": 1, "medium": 2, "high": 4}                   # inherited
```

The first decides the SEO Score. The second divides it to order the fix list. Both
arrived with borrowed code and neither has been examined here, and their own basis
lines say so.

**The first step is not calibration, it is a sensitivity analysis** — a day's work
that closes the question in either direction. Re-score an existing set of runs under
10/6/3/1, 8/5/3/1 and 4/3/2/1 and measure how far the headline moves:

- moves ±2 points → the table does not matter, that gets written down, and the
  question is closed without pretending to have measured anything;
- moves ±15 points → the score is an artifact of an unexamined table, and it must
  either be calibrated against outcome data or stop being printed as the headline.

Either result is the first honest entry in the `measured` column. Only the second
result justifies the expensive follow-on: correlating scores against Search Console
performance on real properties.

---

## 0.18 — a series, and a report somebody can read

**History as a series, not a pair.** `.seo-runs/` has stored every run since 0.1.0;
`--diff` compares against one. The question a site owner asks is whether six months of
work moved anything, and the data to answer it is already on disk.

**`item_titles` and `item_fixes` in Russian.** 214 titles and 214 recommendations. Pure
grind, no design, and the one thing that blocks handing a report to a reader who does
not work in English. The report's own 100 strings have been translated since 0.15.0.

---

## 1.0 — the document and the code say the same thing

Every invariant in this tree is tied to a test except the 3,850 lines of prose that
describe them, and the prose has started to drift. As of 0.15.0 four places still tell
the reader that `answer_block_scanner.py` scores 10 under `lxml` and 32 under
`html.parser` and that neither reading is right — `SKILL.md`, `seo_common.py`,
`checklist_runner.py` and the scanner's own docstring. Measured on exactly that markup
after the 0.15.0 rewrite, both parsers return 42. `SKILL.md` is the agent's
instruction file, so this is not cosmetic: it instructs a model to hedge a verdict
that is now sound.

A test should tie the checkable claims in `SKILL.md` and `README.md` to observable
behaviour — every version number, every count of items or scripts or strings, every
named threshold, and every claim of the form "X is N". Anything a build can verify, a
build should verify.

Then the registry is declared stable and the cadence becomes external: the Public
Suffix List snapshot, Google's documented crawler list, the Core Web Vitals bands,
schema requirements. The tool changes when the web changes.

---

## Deliberately not built

**More checks.** 214 is already past what a client reads. Item 215 adds a line to a
document that gets skimmed.

**A link index or competitor data.** That is a data business, not a plugin. The
refusal to emit a toxicity score without a link index is the correct call and stays.

**Public distribution as a goal.** It should fall out of the above or not happen. Its
cost is not code — it is a standing obligation to triage other people's sites against
a 19,000-line tree with one maintainer, at this project's own observed rate of roughly
one defect per three tests written.
