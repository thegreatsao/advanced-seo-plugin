# Known issues

What is wrong with this plugin as of **0.3.0**, ranked by consequence, with the
evidence for each. Nothing here is a suspicion: every entry was measured against
the tree.

This file exists because the audit's one promise — that "we could not check this"
never reads as a verdict — applies to the plugin's own description of itself. A
defect known and unwritten is the same failure one level up.

**Fixed in 0.3.0** and kept below the line for the record: `--sample` taking the
first N sitemap URLs, the report's two incompatible scales, the crawlers ignoring
`robots.txt`, and `broken_links.py` having no cap.

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

Note what fixing 1 also fixes: robots.txt is honoured once in the shared crawler
instead of five times, and the request volume stops being a property of how many
scripts happen to want a crawl.

## 2. 45 of the 55 evidence scripts have no unit test

The tests defend the *frame* — registry, runner, report — and barely touch the
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

## 3. There is no integration layer, and the SSRF guard prevents building one

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

## 4. The deliverable has no history

`.seo-runs/` stores every run, and the runner prints a diff against the previous
one — to the terminal, for one previous run, gone when the terminal closes. The
report a client receives cannot say whether anything improved. A checklist is a
thing people re-run; the data exists and does not reach the file.

## 5. There is no machine-readable fix list

`checklist-results.json` is the full audit log, not a task list. Getting the
actionable items into a tracker means parsing the report or filtering the log by
hand. A CSV or JSON of just the fixes (id, severity, effort, URL, what to do) would
be a few lines.

## 6. Smaller, but they will bite

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

## Fixed in 0.3.0

Kept because the reasoning is the useful part, and because a reader who saw the old
warning deserves to find out what happened to it.

- **`--sample N` took the first N sitemap URLs in document order.** Sitemaps are
  ordered by section or by date, so that gathered one corner of the site while the
  report said "5 of 5 pages checked". Now spread by an arithmetic stride across the
  whole list — still reproducible, since the step is not random.
- **The report showed two scales.** The per-category score was an unweighted pass
  rate next to a severity-weighted headline: one category read 25 where its weighted
  score was 42, and the bars were *ordered* by the unweighted number. Both now use
  the same weighting, and each bar carries the worst open severity, because no single
  number can show "one failing critical in an otherwise clean category".
- **The crawlers ignored `robots.txt`.** Now honoured for pages the tool discovers
  itself — followed links, sampled sitemap entries, and any redirect they land on —
  and deliberately *not* for the URL the operator supplies, since a blanket check
  would refuse the 40-odd scripts that fetch it and bury a `critical` finding under a
  collapsed audit. `Crawl-delay` is obeyed when it asks for more patience than
  `--max-rps`, ignored when it would ask for less.
- **`broken_links.py` had no cap.** Now 200 links, internal first, and it reports
  when it truncated.

The subtle part of the robots change: `orphan_pages_from_sitemap.py` computes
orphans as `sitemap − reachable`, so a URL we declined to fetch would have dropped
out of `reachable` and been reported as an orphan — GO-137 fails on one. Refusals
are tracked separately and subtracted, and a sitemap listing robots-blocked URLs is
now its own finding, which is the sharper one anyway.

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
