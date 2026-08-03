# Known issues

What is wrong with this plugin as of **0.2.0**, ranked by consequence, with the
evidence for each. Nothing here is a suspicion: every entry was measured against
the tree on 3 August 2026.

This file exists because the audit's one promise — that "we could not check this"
never reads as a verdict — applies to the plugin's own description of itself. A
defect known and unwritten is the same failure one level up.

Two ways to read the list. **Users:** items 1–4 change how you should read a
report. **Contributors:** items 5–9 are where the work is.

---

## 1. The site is crawled five times over, and nothing is shared

Five scripts each run their own independent crawl, with their own page budget, and
throw the result away:

| Script | Pages |
|---|---|
| `orphan_pages_from_sitemap.py` | 100 |
| `duplicate_content.py` | 50 |
| `link_profile.py` | 50 |
| `internal_links.py` | 50 |
| `anchor_text_audit.py` | 25 |

That is **~275 fetches of the same pages per audit**, plus 36 more scripts each
re-fetching the entry URL, with no shared HTTP cache anywhere. At the default
4 rps/host that is over a minute of pure pacing, and the audited site absorbs five
crawls where one would do.

The fix is the pattern this plugin already uses for `cwv_metrics.py` and
`rendered_audit.py`: crawl once into an inventory artifact (URL, status, title,
description, canonical, content hash, inbound links, depth) and have every
site-wide check read it. That also produces the thing the report cannot currently
give anyone — **a list of which URLs are broken**, rather than a verdict about the
site.

Not a small change: one new crawler plus five scripts rewritten to read a table.

## 2. `--sample N` is not a sample

`discover_urls()` takes the **first N URLs in sitemap document order**. Sitemaps
are typically ordered by section or by date, so the first N are systematically one
corner of the site — the newest posts, or a single category.

The report then says *"on 5 of 5 pages checked"*, which reads as a sample and is
not one. Two sites with identical page counts can produce sets of completely
different representativeness, and nothing in the output distinguishes them.

A deterministic stride over the full sitemap (or a seed derived from the domain)
would keep the reproducibility the whole tool is built on and remove the bias. One
function.

**Until then:** read `--sample` as "N pages from the top of the sitemap", not as
evidence about the site as a whole.

## 3. The report shows two different scales without saying so

`seo_score` is weighted by severity. The per-category score is an unweighted pass
rate, `(pass + 0.5 · warn) / decided`. Measured on one run:

| Category | Shown in the bars | Weighted |
|---|---|---|
| Content | 25 | **42** |
| Meta & Structured Data | 71 | **82** |

So a reader comparing "Content: 25" against "SEO Score: 65" is comparing two
formulas. Worse, the report **orders the category bars by the unweighted number**,
so the "look here first" layer and the severity-ranked fix list below it can
disagree about what matters most.

## 4. The plugin's own crawlers ignore `robots.txt`

No script consults `robots.txt` before crawling — nothing imports
`urllib.robotparser` or calls `can_fetch`. The plugin *checks whether* a site's
`robots.txt` blocks Google (`robots_checker.py`, `robots_path_tester.py`) while not
consulting it for its own requests.

Request pacing was added in 0.2.0 as the one safeguard that protects a third party
rather than the audit's own honesty. This is the other half of that concern, and
`urllib.robotparser` is in the standard library.

Related: **`broken_links.py` has no upper bound.** It checks every link it finds,
10 workers, no cap. A page with 300 links means 300 requests.

## 5. 45 of the 55 evidence scripts have no unit test

229 tests defend the *frame* — registry, runner, report — and do not touch the
*evidence*. Every verdict is the output of an untested script interpreted by a
well-tested interpreter.

Three bugs in the borrowed scripts have been found so far, all by accident rather
than by a test (`article_seo.py` crashing on `@graph` JSON-LD, `safe_http.py`
exiting at import, `validate_skill_inventory.py`'s regex that never matched). How
many remain is unknown, which is the point.

Seven of the untested scripts were written here: `gsc_links_csv.py`,
`gsc_cannibalization.py`, `gsc_url_inspection.py`, `ga4_tag_checker.py`,
`css_minify_check.py`, `domain_safety_check.py`, `html_validator.py`.

Start with the scripts whose output decides a `critical` item. HTML fixtures, no
network.

## 6. There is no integration layer, and the SSRF guard prevents building one

`assert_safe_url()` rejects loopback and private addresses with no escape hatch, so
you cannot point an audit at a fixture site on `127.0.0.1`. The live path —
fetching, crawling, pacing, redirect handling — can therefore only be exercised
against a real third-party site.

That is not theoretical. In 0.2.0 the new rate limiter crashed 36 of 56 scripts,
and every test passed, because a single process writing to a fresh slot file never
appends twice. Only a live run against somebody else's site could show it.

It also blocks a legitimate use: **auditing a staging site before launch**, which
is when an audit is worth most.

Suggested shape: `--allow-private`, off by default, announced in the output when
used, and a CI job that serves a fixture site and runs the full live path against
it.

## 7. The deliverable has no history

`.seo-runs/` stores every run, and the runner prints a diff against the previous
one — to the terminal, for one previous run, gone when the terminal closes. The
report a client receives cannot say whether anything improved. A checklist is a
thing people re-run; the data exists and does not reach the file.

## 8. There is no machine-readable fix list

`checklist-results.json` is the full audit log, not a task list. Getting the
actionable items into a tracker means parsing the report or filtering the log by
hand. A CSV or JSON of just the fixes (id, severity, effort, URL, what to do) would
be a few lines.

## 9. Smaller, but they will bite

- **`tools/probe_shapes.py` holds its job list by hand.** The tool used to verify
  script output shapes is not itself tied to the registry, so it can drift from the
  thing it verifies and nothing notices.
- **No `pyproject.toml` and no declared Python floor.** The code needs 3.10+
  (`str | None`, `dict[int, str]`); CI tests 3.11 and 3.13; nothing states it.
- **No linter in CI.** `ruff` is listed in `requirements.txt` as a development
  dependency and never runs.
- **The page guard is fingerprint-based**, so an interstitial from a vendor it does
  not recognise still gets through. Deliberate: an unknown interstitial and a
  client-rendered shell are indistinguishable from the HTML, and the second is a
  real finding, so the run warns with the visible word count instead of refusing to
  score.
- **Client-facing reports are English-only.** `--lang ru` translates the report's
  own wording and all 16 category explanations; `item_titles` and `item_fixes` are
  empty, so item titles and recommendations come out in the registry's English. The
  report says which layers are untranslated on stderr.

---

## Not defects

Recorded here because they get mistaken for defects:

- **10 of the 15 backlink items are `MANUAL`.** Judging link quality needs a link
  index this plugin does not have. A fabricated toxicity score is worse than
  silence.
- **31% of the registry is not machine-decided** (35 `llm`, 32 `manual`). The
  distribution is what matters: **1 of 19 `critical` items** is not
  machine-decided, against 59% of the `low` ones. The un-automatable residue sits
  where it costs least.
- **Coverage below 100% on a real run.** That is the metric working. An audit that
  reported 100% coverage would be hiding the questions it could not answer.
