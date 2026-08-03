# Known issues

What is wrong with this plugin as of **0.4.0**, ranked by consequence, with the
evidence for each. Nothing here is a suspicion: every entry was measured against
the tree.

This file exists because the audit's one promise — that "we could not check this"
never reads as a verdict — applies to the plugin's own description of itself. A
defect known and unwritten is the same failure one level up.

**Fixed in 0.4.0**, below the line: the SSRF guard having no escape hatch (and with
it, the absence of any live-path test), an address being given a registrable domain,
external-API checks crashing instead of reporting `NO_DATA` on a private host, a
robots-disallowed sitemap URL counted as an orphan, and the report never saying when
it was describing something other than the public site.

**Fixed in 0.3.0**: `--sample` taking the first N sitemap URLs, the report's two
incompatible scales, the crawlers ignoring `robots.txt`, and `broken_links.py`
having no cap.

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

As of 0.4.0 they are at least *executed* end to end: CI serves
`tests/fixtures/site/` and fails if any of them crashes. That is a smoke test, not
coverage — it proves each script runs and returns usable output against one small
site, and says nothing about whether its verdict is right.

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

## 3. The live path is exercised against one shape of site

Fixed in 0.4.0 in the sense that it can now be exercised at all — but CI audits a
static six-page fixture served by `http.server`. Four things that only happen in the
wild are still tested with fixtures and never live: a cross-host redirect, a real
bot-protection challenge, a site large enough for `--sample` to matter, and a Search
Console property with enough history for the cannibalization items.

The fixture is also HTTP, so nothing exercises TLS, HSTS, or a certificate problem —
`security_headers.py` and the HTTPS items get their verdicts from offline tests only.

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

## Fixed in 0.4.0

Every one of these except the first was found *by* the first, within an hour of it
existing. That is the argument for the feature, and it is the fourth session running
in which looking at output beat reading code.

- **The SSRF guard had no escape hatch**, so no fixture site could be served locally
  and the live path could only ever be exercised against a real third-party site.
  That is how 0.2.0's rate limiter crashed 36 of 56 scripts with every test passing.
  `--allow-private` is off by default and deliberately narrower than "not public":
  loopback, RFC 1918, ULA and CGNAT only, with **link-local still blocked** because
  cloud instance metadata answers at 169.254.169.254 and the URLs a crawl follows
  come from the site. CI now serves `tests/fixtures/site/` and fails if any evidence
  script crashes.
- **An address was given a registrable domain.** `127.0.0.1` became `0.1`, the run
  built `sc-domain:0.1`, and both Search Console scripts crashed. On a public IP it
  would have been quieter and worse: a valid-looking property nobody owns answers
  with nothing, and nothing reads as a site with no search traffic — the same failure
  as the pre-0.2.0 `something.github.io` → `github.io` bug, through a new door.
- **External-API checks crashed on a private host** instead of reporting `NO_DATA`.
  PageSpeed measures from Google's network and a Search Console property cannot exist
  for an address on a LAN; neither is a defect in the site or the tool, and "script
  failed" sends the reader to open a script that works. `NO_DATA`, not `N/A`: the
  items apply, so coverage drops — which is the honest thing for a staging audit.
- **A robots-disallowed sitemap URL was counted as an orphan.** 0.3.0 subtracted the
  refusals the crawl recorded, and a crawl only tries what the site links to, so a
  disallowed URL that nothing links to arrived with no refusal attached. That is the
  ordinary case: a page is usually unlinked *because* it is blocked. The claim in the
  0.3.0 notes below was therefore true only for linked URLs.
- **The report never said when it was not describing the public site.** A
  `--no-page-guard` run produced a clean-looking deliverable that never mentioned it
  had scored a Cloudflare interstitial. The runner recorded and printed it; the file
  handed to a client did not. Now three facts — private host, scored interstitial,
  content-free entry page — appear above the summary on every surface.

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

That held only for URLs the crawl actually tried, which is the half of the problem
0.3.0 could see. See the 0.4.0 list above for the other half.

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
