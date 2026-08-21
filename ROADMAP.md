# Roadmap to 1.0

`KNOWN-ISSUES.md` says what is wrong. This says where it stops.

A version number that does not mean anything is a number nobody can argue with, so
1.0 is defined here as a claim that can be checked:

> **Every item in the registry either carries a verdict or a stated structural reason
> it cannot; every number a verdict rests on is either measured or declared unmeasured;
> and the document says what the code does.**

That definition has not changed since 0.15.0 and does not need to. What follows is
where the tree stands against each of its three clauses, measured rather than
estimated, with the command that prints each number — **so that this file can be
checked instead of believed.**

**This file was itself the counter-example.** Until 0.87.1 it planned releases 0.16
through 0.20 as though they were ahead; they shipped sixty-seven releases ago. A
roadmap describing a tree that no longer exists is the third clause failing about the
second document in the repository, and it went unnoticed because nothing reads a
roadmap on a schedule.

---

## Where the tree stands, 0.87.1

One live run against `tests/fixtures/good` served on loopback, `--sample 3`, no Search
Console key, no supplied artifacts:

```
SEO Score 92/100 — over 99 decided items, 51% of the weight in scope
  decided            99
  waiting on you     55   (38 unanswered LLM items, 17 missing inputs)
  needs a person     34
  undecided          27
  not applicable      2
                   ---- 217 items in the registry
```

Every item is in exactly one row and the rows add up to the registry. That partition is
the shape 0.16 introduced and it is stable; what moves now is the size of each row.

### Clause 1 — a verdict, or a stated reason there is none

`tests/census.json` records what every item answered across the five trees this
repository can serve, and it is the closest thing to an answer for this clause:

```
.venv/Scripts/python.exe tests/verdict_census.py --check tests/census.json | tail -3
```

| | count | what it means |
|---|---|---|
| answered somewhere, never FAIL | 25 | a rule that cannot fail, or a case the corpus does not have |
| answered somewhere, never PASS | **2** | the mirror; it was 8 before 0.87.0 |
| never answered anywhere | 30 | mostly honest — Search Console, PageSpeed and Safe Browsing cannot answer offline |

The second row is where the last release went, and the two survivors are named:
`AR-158`, whose visible-breadcrumb half no fixture carries, and `GEO-006`, whose script
reads the JSON-LD graph with no boundary at all. The first and third rows are the work
left: each entry has to become either an answer or a written structural reason, and the
honest form of that reason is a corpus page or a named limitation, not a shrug.

Beside it, the reachability audit asks the same question of the assertions rather than
of the items:

```
.venv/Scripts/python.exe skills/seo-checklist/tools/audit_reachability.py
```

145 script-backed assertions; **2 proved unable to report FAIL, 143 not claimed either
way.** That 143 is the honest measure of how much of the registry any tool here speaks
about at all, and it is the number that should fall.

### Clause 2 — every number measured or declared unmeasured

```
.venv/Scripts/python.exe skills/seo-checklist/tools/audit_thresholds.py --check | head -7
```

136 numbers a verdict depends on:

| basis | count | |
|---|---:|---|
| standard | 11 | an external published authority, named |
| measured | 11 | calibrated, and the text says against what |
| convention | 47 | a judgement made here, and it says so |
| **inherited** | **67** | arrived with borrowed code and has not been examined |
| no basis | 0 | the gate that keeps this at zero |

**`inherited` at 67 of 136 is the largest single gap between this tree and 1.0.** The
clause is already half satisfied — nothing is unnamed, and that took a gate — but half
the numbers a verdict rests on are still numbers nobody here decided. The two
calibrations so far show what closing one costs: `serp-length.json` and
`css-minification.json` each took a corpus, a method and a stated limitation.

One class of number is outside the scan by construction: a floor written into the
registry is not a module-level constant, so `audit_thresholds` never sees it. 0.87.0
moved five and wrote each derivation beside it in `build_checklist.py` because nothing
would have demanded one. **A gate that cannot see a class of numbers is a gate with a
hole in it**, and closing that hole belongs to this clause.

### Clause 3 — the document says what the code does

This is the clause with no gate at all, and 0.87.1 is what it looks like when it fails.
Four documents had drifted, none of them caught by a test:

* this roadmap, planning shipped releases;
* `KNOWN-ISSUES.md`'s header, dated 0.80.0 and counting 41 entries where there were 42;
* the polarity entry inside it, saying *74 of 215 — 34.4%* while its own probe printed
  76 of 217;
* the repository description on GitHub, offering a 215-check registry.

The 0.15.0 ask still stands and is still unbuilt: **a test should tie the checkable
claims in `SKILL.md`, `README.md` and this file to observable behaviour** — every
version number, every count of items or scripts or strings, every named threshold, and
every claim of the form "X is N". Anything a build can verify, a build should verify.

Two mechanisms already exist and can be copied rather than invented. `i18n_digest.py`
binds each translation to a digest of the English it was written against, so drift is a
failing build rather than a discovery. `tests/known_issues.py` re-runs each ledger
entry's own measurement and fails when the tree stops answering what the entry says.
Prose that states a number wants the same treatment: the number, where it comes from,
and a check that they still agree.

---

## What 1.0 requires, in the order the numbers should move

1. **`inherited` 67 → 0**, by calibration or by an honest relabel to `convention` with
   the judgement written out. The count prints on every CI run, so progress is visible
   without anybody reporting it.
2. **The 143 unclaimed assertions**, reduced by extending the detectors
   `audit_reachability.py` already has rather than by asserting reachability in prose.
3. **The census's 25 and 30**, each turned into an answer or a named structural reason.
   The `MD-184` class showed the shape: a rule that cannot fail is a registry defect, a
   case the corpus does not have is a corpus gap, and the two are told apart by
   construction rather than by argument.
4. **A gate for clause 3**, because the other two clauses have one and this one does
   not — which is exactly why it was the clause that failed.

Then the registry is declared stable and the cadence becomes external: the Public
Suffix List snapshot, Google's documented crawler list, the Core Web Vitals bands,
schema requirements. The tool changes when the web changes.

---

## Deliberately not built

**More checks.** 217 is already past what a client reads. Item 218 adds a line to a
document that gets skimmed. The three releases before this one added no items and
removed none; they made the ones already there mean what they say.

**A link index or competitor data.** That is a data business, not a plugin. The refusal
to emit a toxicity score without a link index is the correct call and stays.

**Public distribution as a goal.** It should fall out of the above or not happen. Its
cost is not code — it is a standing obligation to triage other people's sites against a
tree of this size with one maintainer, at this project's own observed rate of roughly
one defect per three tests written.
