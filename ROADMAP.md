# Roadmap to 1.0

`KNOWN-ISSUES.md` says what is wrong. This says where it stops.

A version number that does not mean anything is a number nobody can argue with, so
1.0 is defined here as a claim that can be checked:

> **Every item in the registry either carries a verdict or a stated structural reason
> it cannot; every number a verdict rests on is either measured or declared unmeasured;
> and the document says what the code does.**

Four releases reach it. Nothing below adds a check to the registry — 0.20 repairs one.

**Shipped:** 0.16 replaced the coverage percentage with the score's weight share
and a partition of the registry. 0.17 gave the two groups that could only sit at
zero a way to be answered.

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

*Shipped in 0.17.* The queue skeleton, `--manual-answers`, `decided_by` and the
disclosure line are in; dispatching the lens agents is a skill-level change and is
described below rather than done.

**Close the model group.** 36 items — 17% of the registry, 116 points of weight — sit
at `LLM_PENDING` because answering them means running four agents by hand, saving JSON
by hand, and merging by hand. The runner should dispatch the lens agents and merge
their answers itself — except it cannot: the runner is a Python CLI that launches
subprocesses and has no model. The dispatch belongs in `SKILL.md`, which tells Claude
to run the four lens agents in parallel; the runner's part is making the round trip
one command, which is what the per-lens skeleton did. No new check; the largest
single coverage gain available anywhere in this plan.

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

## 0.18 — the two tables that produce the headline number

**Shipped, and the result was neither of the two outcomes predicted below.** The spread
is 0.2 to 14.6 points depending on the run, so the table is neither decoration nor
uniformly decisive: it matters in proportion to how far the per-severity pass rates
spread, and therefore most on the sites where severity actually discriminates. That
does not close the question, it sharpens it — the next step is outcome data, and
`tools/audit_score_sensitivity.py` is what will measure whether any calibration helped.
`EFFORT_COST` is closed: divide by effort, and stop arguing about which numbers.

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

## 0.19 — a series, and a report somebody can read

**Shipped.** The trend reads every stored run rather than one, `open_since` says how
many consecutive audits each open item has survived, and the Russian report is Russian
throughout — 214 titles and 214 recommendations, checked against the registry by a
test. What remains for 1.0 is the doc-code parity test.

**History as a series, not a pair.** `.seo-runs/` has stored every run since 0.1.0;
`--diff` compares against one. The question a site owner asks is whether six months of
work moved anything, and the data to answer it is already on disk.

**`item_titles` and `item_fixes` in Russian.** 214 titles and 214 recommendations. Pure
grind, no design, and the one thing that blocks handing a report to a reader who does
not work in English. The report's own 100 strings have been translated since 0.15.0.

---

## 0.20 — the registry says one thing and asserts another

**Open, and it is a class rather than a bug.** One live audit of a Lithuanian café on
5 August 2026 produced five registry defects. That is the yield of a single real site
after four releases of test-writing, which is the argument for this release existing:
the fixture pair and the two sweeps had all passed. Full diagnosis of each in
`KNOWN-ISSUES.md` §6.

| | What it says | What it asserts |
|---|---|---|
| CI-019 `high` | noindex `/search`, `/cart`, `/checkout`, `/login` | robots.txt allows those paths — never fetched, so a 404 counts |
| CN-053 `medium` | do not hide content in iframes | `raw.word_count >= 300` — it counts words |
| CI-017 / TE-181 | validate HTML, twice | identical script, arguments and assertion |
| CI-016 / MD-186 `high` | alt text, twice | identical script, arguments and assertion |
| TE-179 `low` | review domain reputation | `whois.age_days >= 90` — a new domain, unfixable |
| GO-134 `high` | resolve Search Console issues | `opportunities` through a severity gate — good news as a failure |

Four repairs, in this order. The first two are audits and will find more than the list
above; the last two are decisions.

**1. Explain the sweep — done, and the answer is about the fixture.**
`tests/fixtures/good/robots.txt` disallows exactly `/search`, `/cart`, `/checkout` and
`/login`, under a comment naming CI-019 as the reason. The sweep is not blind; it is
looking at the one site where the item is meaningful.

The general form is the part to keep: **a fixture built to pass the registry cannot catch
an item that accuses every real site.** The sweep's guarantee holds for the site the
registry was written against and says nothing about the ones it was not, and no amount of
sweeping fixes that — only a second fixture built without consulting the registry would,
which is not written and is not scheduled here.

**2. Audit the triple across all 214.** For every item: does the assertion measure what
the title names, and does the fix text describe the work that would satisfy the
assertion? CI-019 and CN-053 are two answers of "no" found by accident in one run, and
nothing looked for a third. This is mechanical and belongs in `tools/` beside
`audit_assertions.py` and `audit_thresholds.py`. The precedent is exact: naming the
thresholds moved `inherited` from 14 to 75, because the old count was low only while most
of them had nowhere to carry a label. §2 has recorded "a check and its own advice
disagree" as an inventory finding since 0.15.0, and named `article_seo.py` — these are
the first two caught deciding a real site.

**Written, and the count was wrong by a factor of five.** The same tool asks the cheap
structural question — no two items may share a script, arguments and assertion — and
**eleven groups do**, not the two a single audit happened to fail on. Three mix
severities, so the weight a defect carries depends on which twin the reader looks at. The
duplication arrives honestly, since the Plerdy source lists one requirement under two of
its own headings and `plerdy_ref` is load-bearing, so the fix is not deleting an id:
either one id decides and its twin mirrors the verdict without contributing weight, or
they merge and the mapping records that two source numbers point at one check. **What
must stop is one defect carrying double weight in the headline number and two rows in
`--fixes`.**

**And one of the eleven is not a scoring artifact at all.** `SE-117` *Force HTTPS
Sitewide* and `SE-118` *Valid TLS Certificate* are both `critical` and both assert
`https == True` — two requirements sharing one assertion, so **SE-118 cannot fail
independently on any site** and a certificate that expired yesterday passes it. That is
the one item here that needs new evidence rather than a decision: `notAfter`, the chain,
the hostname match. Until it has them, this registry has never verified a certificate
while reporting that it does. **Do this one first** — it is the only `critical` among the
findings that is currently checking nothing.

The vocabulary half of the tool is a heuristic and is reported as one: 46 of 214 items
share no words between what they claim and what they assert. Four carry a written ruling;
**42 are unreviewed and are the remaining work of this step.** The tool is not wired into
CI yet, deliberately — it exits 1 today, and a required check that is red by default is a
check nobody reads.

**3. Then CI-019 itself, which needs two repairs.** ✅ **Done in 0.21.0.** `allowed_urls`
must not count a URL that 404s — a path robots.txt permits and the server does not serve
is a name nobody used, and checking costs four conditional requests on a check that
currently makes one. Then the mechanism: the title and fix say `noindex`, the assertion
tests robots.txt, and the remediation that passes the check (`Disallow:`) is the one that
stops Google seeing the `noindex` at all. **Decide which check this item is** and make
all three agree.

> Both repairs turned out to be one. `--probe` fetches each permitted path and the
> assertion reads `indexable_urls` — the path exists, a crawler may have it, nothing
> keeps it out of the index — which accepts either mechanism and so needs no choice
> between them. The decision that did have to be made went the other way from how it is
> framed above: the title was not what was wrong. It is inherited wording from
> `plerdy-titles.json`, a record of someone else's checklist, and `noindex` described the
> goal correctly all along. Only the assertion was wrong.
>
> Two findings came out of it, both larger than the item. After the repair CI-019 passed
> on *both* fixtures, because neither had a system page at all — it had looked like a
> working test for two releases while testing nothing. And the first probe read `noindex`
> off a `<meta name="robots">` quoted inside the new fixture's own comment block, among
> the things the page deliberately lacks, so the page built to fail passed. Fourth
> appearance of one mistake here: 0.5.0's keyword items, 0.19.1's port number, and the
> soft-404 guard that carries the warning in writing.

**4. Decide what an item is allowed to report.** ✅ **Answered in 0.21.0, and the answer
is no new status.** Two items report something that is not a defect of the site, and the
question underneath them is the same:

- `TE-179` fails a domain for being 58 days old. There is no work that closes it; it
  closes itself in a month. **An item that cannot be acted on does not belong in a
  prioritised list** — either it becomes informational, or the threshold means something
  other than what it says.
- `GO-134` renders "position 4.0 with 115 impressions" as a `high` failure, because
  `opportunities` is read through a severity gate. This is independent of §2's objection
  that those thresholds are folklore: even a perfectly calibrated opportunity is still
  not a defect, and printing one as the top item tells a client to fix their best result.

Both need something the registry does not have — a way for a report to say *worth
knowing* without the item entering the score or the fix list. That is a design decision
rather than a repair, which is why it is last.

> **The second horn was the right one, for TE-179 at least: the threshold meant
> something other than what it says.** Age is neither history nor reputation, and
> `domain_safety_check.py` already reports reputation — age was a proxy reached for
> because the real signal needs a key. It now asserts `safe_browsing.threats`: a clean
> domain passes at any age, a listed one fails at any age, and with no
> `GOOGLE_SAFE_BROWSING_KEY` the field is absent, which is `NO_DATA` — "we could not
> look", which this vocabulary has always been able to say.
>
> `GO-134` fails the premise rather than the test. Each entry in `opportunities[]`
> carries its own `finding` and `fix`, so the work is real and doable; what is wrong is
> the name and the weight, and both are inherited. Left open rather than quietly
> rewritten — see §2 on thresholds nobody measured.
>
> So the bucket has no occupants. A new status would have cost the runner, the report,
> the HTML, the CSV, both translations, the score partition, the diff buckets and the
> every-status-reaches-every-surface test, in order to make two miscategorised
> assertions comfortable. **What was missing was not a status. It was a correct
> assertion.** If a genuine case turns up later — a true fact, worth printing, that no
> action closes and no better assertion captures — this decision should be reopened on
> that item's evidence, not on the two above.

**No registry additions.** 214 stays 214, and may become fewer if the duplicate pairs
merge. Everything here repairs, removes or reclassifies what is already there.

> **Closed in 0.22.0, and 214 is still 214.** The eight synonym pairs did not merge;
> they carry weight once, through a `scores_with` pointer decided by hand. A merge
> would have deleted a source number a reader may look up, and the harm was never that
> two rows existed — it was that one defect scored twice and, where the twins disagreed
> on severity, that its weight depended on which row you read.
>
> The other two of the ten were not duplicates at all: MS-027/MS-028 and MS-029/CN-041
> were two requirements sharing one assertion because the second had never been written.
> Those were repaired, not paired. CN-053 was reclassified — it counted words under a
> title about iframes — and so was MS-027, since *compelling* is not a thing an
> assertion decides.
>
> The 42 unreviewed vocabulary misses are 0: fourteen were the heuristic's own fault
> and the remaining 28 carry written rulings. Four of those rulings are new defects,
> left open on purpose rather than repaired in the pass that found them — CI-002,
> IN-127, and the Core Web Vitals group, where **five** items exist and three measure
> something other than Core Web Vitals. That last one is a redesign of a group, not
> four edits.
>
> Both audit tools now run in CI, which they could not before: a required check that is
> red by default is a check nobody reads.

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
