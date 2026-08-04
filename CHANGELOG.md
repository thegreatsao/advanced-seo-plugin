# Changelog

`registry_version` in `checklist.json` tracks the audit contract — which items
exist and what each one asserts. It changes whenever the checklist changes, which
is not the same event as the plugin changing. This file tracks the plugin: the
runner, the report, the scripts and the run modes around that contract.

Versions are `MAJOR.MINOR.PATCH` before 1.0, where the minor is bumped for
anything that changes what a run produces — including a change that makes the
output *more* honest. A verdict that used to be `PASS` and is now `NO_DATA` is a
breaking change for whoever read the old number, and saying so is the point.

## 0.14.0 — 4 August 2026

Registry unchanged (`1c4b3697cc1f`, 214 items). Tests 525 → 549, in two new files.

The last two items of the plan: decide the HTML parser, and get the live path in front
of the site shapes it had never seen. Both were "needs measuring", and the measuring
found a third thing — a platform bug that had been silently killing this suite's own
audits depending on which test module ran first.

### Changed — the parser is a decision now, and it is recorded

`seo_common.parse_html` chose its parser with `"lxml" if "lxml" in sys.modules else
"html.parser"`, which does not ask whether lxml is *installed* — only whether something
imported it first. So one machine could parse the same page two ways, and
`parse_html.py` held a second copy of the test, so two checks inside a single audit
could disagree about a document. For a tool whose whole claim is that two runs of one
site agree, the substrate cannot be chosen by import order.

**It is lxml, when it can be imported**, and `SEO_HTML_PARSER` overrides it. The run
records which parser produced its verdicts, next to the Public Suffix List snapshot and
for the same reason; the report says so when it is not the default.

**The evidence is a committed corpus, not a crawl** — `tests/test_parser.py`, fifteen
document shapes chosen for what real generators emit: unclosed `<p>` and `<li>`,
300-deep `<div>` nesting, an inline `<svg>` with its own `<title>`, `<template>` and
`<noscript>`, a `<div>` inside `<head>`, `<picture>`, a bare fragment, duplicate
attributes. A crawl was the other option and was rejected on this project's own
precedent: the Public Suffix List is bundled as a dated snapshot rather than fetched,
because a run must answer the same offline and next month, and the evidence behind a
*decision* deserves that no less than the evidence behind a verdict. What a corpus
cannot do is contain a divergence nobody thought of — so the override exists, which is
what makes being wrong here recoverable.

**What the measurement found.** Every field the registry reads is identical under both
parsers across all fifteen shapes. The divergence is structural, and it reaches two call
sites: `picture_sources()`, which already walks up to any ancestor because libxml2 nests
the `<img>` inside the first `<source>`, and `answer_block_scanner.py`, which finds an
answer with `find_next_sibling()`. On markup with an unclosed `<p>` that script scores
**10 under lxml and 32 under html.parser**, and GO-144 reads that score — and neither
reading is right. That is now its own KNOWN-ISSUES entry rather than a parser problem:
the parser is deliberate, so the score is at least reproducible; a sibling walk is still
the wrong instrument for markup a browser repairs.

### Added — the four site shapes, live

`tests/test_shapes.py` puts the runner in front of what KNOWN-ISSUES item 3 listed as
tested-with-fixtures-and-never-live. Two of the four had already gone wrong in exactly
that gap: the discarded final URL (0.4.0) and the page guard's first draft calling a
90-word article an interstitial (0.4.0).

- **A cross-host redirect** — two origins and a real 301. The destination is audited,
  the requested URL is recorded, the sample follows the destination host, and a
  *same-host* hop deliberately keeps the requested URL so `redirect_checker.py` still
  sees the hop it exists to report.
- **A bot-protection challenge** — a Cloudflare fingerprint served with a 200. Refused
  with no score; `--no-page-guard` scores it and says so on every surface; and an
  article *about* Cloudflare, short enough to look like a challenge, is audited anyway.
- **A sixty-page site** — where `--sample` has to choose. The picks span the sitemap
  rather than clustering at its start, the far end is reachable, and the worst page
  supplies both the verdict and the measurement.
- **TLS** — the harness generates a certificate with `openssl` and hands it to the child
  through `REQUESTS_CA_BUNDLE`, so `verify=True` stays on. The HTTPS and HSTS items get
  their first verdicts from a real handshake instead of a stub, and the test skips
  rather than lying if `openssl` is absent.

The fifth shape — a Search Console property with real history — stays unexercised, and
stays written down. It needs a property Google recognises and a key that can read it,
and stubbing the API while claiming live coverage would be worse than the gap.

### Fixed — a script the operating system killed reported as a script that failed

Found while getting the above to pass: `tests/test_shapes.py` was green on its own and
its audits died under `discover`, with signal 11 and no output, depending only on which
module ran first. The crash report named it:

    fork → _pthread_atfork_child_handlers → nw_settings_child_has_forked
         → nw_path_release_globals → NEFlowDirectorDestroy → os_log → SIGSEGV

Apple's Network.framework registers a `pthread_atfork` child handler that dereferences
freed state, so on macOS **any** `fork()` after that framework has been initialised
segfaults the child before it execs. `checklist_runner.run_script` forks 55 evidence
scripts, after the runner has done its own fetching — precisely the shape that trips it,
and the symptom would be a run reporting 55 broken scripts.

`run_script` and the test harness now start children through `posix_spawn`, which does
not fork. And a signal death is classified as `signal` with the signal named, rather
than as `crash` with the message "exit code -11" — the same distinction 0.4.0 drew
between a timeout and a crash, for the same reason: it sends the reader to open a script
that never ran a line wrong.

## 0.13.0 — 4 August 2026

**Registry unchanged** (`1c4b3697cc1f`, 214 items). Tests 520 → 525. Calibration —
KNOWN-ISSUES §2, the largest remaining gap, and the one nothing automatic can close.

**A test can show that a threshold fires; it cannot show the threshold is right.** Four
layers of tests prove a named field answers a named question, that a check can tell two
sites apart, that nothing is decided about a site which answered nothing. None of them
argues with the numbers, and a site audited at the wrong threshold gets a confident
verdict about the wrong question. That stays true. What this closes is the
**invisibility** — a number whose basis nobody stated is a number nobody can argue with.

### Added — `tools/audit_thresholds.py`

Finds every number a verdict depends on and requires each to say what it rests on, in a
form a machine can check:

    # basis: standard | measured | convention | inherited — <why>

The kinds are the point. `standard` is an external published authority, named, so a
reader can go and check it. `measured` is the only one that is evidence rather than
judgement. `convention` is a judgement made here, stated as one — a round number
because a line had to be somewhere, which invites the argument instead of hiding from
it. `inherited` arrived with the borrowed code and has not been examined: not an excuse,
a to-do with a name.

Finding the thresholds at all took three passes, and the misses are worth recording. An
ordering comparison is a threshold; an equality is an **identity** — `inventory_version
!= INVENTORY_VERSION` asks which format a file is, and no calibration improves that. An
HTTP status code is likewise not a limit, which is what took the inline count from 138
to 77. And the first version only looked at bare names inside `Compare` nodes, so it
reported **Google's Core Web Vitals bands as absent** while they decided six items:
`cwv_metrics.THRESHOLDS` is read as `limits = THRESHOLDS[metric]` and compared as
`value <= limits["good"]`, and following a value through a local needs dataflow the AST
does not give away. Numeric lookup tables now count as thresholds if they are subscripted
at all.

### The inventory

| Basis | Count |
|---|---|
| `standard` | 4 |
| `measured` | **0** |
| `convention` | 18 |
| `inherited` | 14 |

**Zero `measured` is the finding.** Not one threshold in this tree was arrived at by
measurement: every number is somebody else's standard, a judgement made here, or an
inheritance. §2 has carried that as a suspicion since it was written; it is a figure now.

`inherited` is assigned from evidence rather than memory — a constant counts as inherited
when `git show <initial commit>` finds it already present — and the list includes the
ones that matter most. **`SEVERITY_WEIGHT` (critical 10, high 6, medium 3, low 1) decides
the SEO Score itself**, and nobody here has asked whether a critical item is worth ten
low ones or three, while the score has been reported to two significant figures
throughout. `EFFORT_COST` divides it to rank what to do first, so the ratio between two
unexamined tables is doing real work that neither was measured for.
`THIN_CONTENT_THRESHOLDS`'s 300 words is one of the five numbers §2 used to name, and its
provenance is what §2 suspected: conventional in SEO writing, with no source anybody here
can point at.

### Fixed — a threshold nothing could find

MB-095's 250 KB was an inline `> 250_000` in the middle of a loop rather than a constant,
which is why no inventory of thresholds could see it — and it is one of the five numbers
§2 explicitly named. It is `LARGE_IMAGE_BYTES` now, with its provenance recorded. **77
comparisons against a bare number remain**; CI holds that as a ceiling rather than
printing it, for the same reason the request count is a ceiling.

### Tests — 520 → 525

The gate itself: no named threshold is bare, the kinds are the documented four, a basis
states a reason rather than only a label, and the unnamed count has not grown. Plus one
that pairs the two copies of Google's CWV bands — `cwv_metrics` reads a local trace and
`pagespeed` reads CrUX, each holding its own copy, and two copies of one standard drift.

**Its first version compared nothing and passed**, because it used lowercase keys against
a table keyed `LCP`/`CLS`. It asserts the number of comparisons it made now. `tbt_ms` and
`INP` are deliberately not paired: TBT is a lab stand-in measured from a page load, and
asserting the two match would be asserting that two different measurements are one.

## 0.12.0 — 4 August 2026

**Registry unchanged** (`1c4b3697cc1f`, 214 items). Tests 508 → 520. Phase 4 of the plan:
two things the audit already knew and did not hand over.

### Added — the report says what changed since the previous audit

`.seo-runs/` has stored every run since 0.2.0. The comparison against the previous one was
computed only when somebody passed `--diff`, printed to a terminal, and gone when the
terminal closed — so a report a client received could not say whether the last round of
fixes worked, from data already on disk. A checklist is a thing people re-run.

It is computed whenever a previous run exists now, and both renderers carry a **Since the
previous audit** section: score and coverage movement, then the items that changed.
`--diff` still decides whether it is printed to the terminal, which is what it was always
for.

**Three buckets, not two.** A change is `improved`, `regressed`, or **`evidence`** — and
the third is the reason this is not just "what changed". `PASS` → `NO_DATA` is not the site
getting worse; it is the run losing the ability to tell, usually a third-party service that
was down or a supplied file that stopped being supplied. Filing that under regressions
would tell a client their site broke when the measurement broke, and the reverse would take
credit for a fix nobody made.

**The baseline is named rather than implied.** The artifact carries `compared_with`: the
other run's timestamp, registry version, mode, profile and scores. "Since the previous run"
is not a date, and a comparison whose other half is anonymous cannot be checked by the
person being shown it. The existing scope warning — a different registry version, mode or
profile — is rendered with it, because a score that moved because the checklist changed is
not a site that moved.

### Added — `--fixes`, the actionable items where a tracker can read them

`checklist-results.json` is the full audit log: every item, decided or not, with the raw
measurement. Getting the actionable part into a tracker meant parsing the report or
filtering the log by hand. `--fixes PATH` writes id, status, severity, effort, priority,
category, title, what to do and evidence — CSV or JSON, chosen by the suffix — ordered the
way the report's "What to do first" orders them, so the two agree.

`FAIL`, `WARN` and `MANUAL` only. `NO_DATA` is not a fix; it is usually work for whoever
runs the audit rather than whoever owns the site. `LLM_PENDING` is a question still waiting
for an answer. Either one would fill somebody's sprint with the auditor's own unfinished
business.

Two details that are decisions rather than defaults. The column is **`audited_url`, not
`url`**: most items record no page — a page-level check over a sample reports the worst
page's verdict without carrying its address, and a site-level check has no single page to
name — so a column called `url` would be read as "fix this page". And the CSV is written
with a UTF-8 BOM and CRLF, because the overwhelmingly likely destination is somebody's
spreadsheet and Excel reads a plain UTF-8 CSV as Latin-1, turning every non-ASCII character
in an item title into mojibake.

### Tests — 508 → 520

Six for the history section: no baseline means no section (an empty "since last time"
heading implies there was a last time), the baseline is named, a fix and a regression are
told apart and the good news does not come after the bad, **losing the evidence is not
reported as a regression**, a changed registry is said out loud, and both renderers carry
it. Six for the fix list: only the actionable statuses, the report's ordering, the status
travelling with the row, the column named for what it is, CSV and JSON holding the same
rows, and a BOM so a non-ASCII title survives a spreadsheet.

## 0.11.0 — 4 August 2026

**Registry `18b1b372a6ed` → `1c4b3697cc1f`** (214 items, unchanged in number; one item
moved from manual to script). Tests 493 → 508. Sources now 144 script / 36 llm / 31
manual / 3 gsc.

**Server logs.** The registry has exactly one item that no request could ever answer,
and it was `manual` for that reason: CI-018, "Analyze Logs & Manage Crawl Budget". Every
other check asks the site what it **offers**; this is the one that says what crawlers
**did**, and the fact is in the past, so no amount of fetching reaches it.

### Added — `server_log_audit.py` and `--server-log`

Same artifact pattern as `cwv_metrics.py` and `rendered_audit.py`: the operator supplies
the file, the script reads it, the registry decides. It measures nothing and fetches
nothing. Combined Log Format, Common Log Format and JSON lines, `.gz` read directly
because a log worth analysing has usually been rotated.

It reports what the crawl cost and where it went: requests per search crawler and per AI
crawler, counted apart because **an AI crawler pulling 10,000 pages is not Google's crawl
budget** and one number for both would carry two claims; the status classes those
requests got; the URLs that returned nothing indexable; and the parameters multiplying one
page into dozens.

Composed with the shared crawl (`--inventory`), it answers two questions neither half can:
**sitemap URLs no crawler ever requested**, and **URLs crawlers request that the site
offers nowhere**. Both are subtractions between what the log saw and what the crawl found.

What it refuses to do is the part worth reading:

- **A log with no User-Agent field reports `error`, not zero crawlers.** Common Log Format
  records none, so every question here is unanswerable from it — and "no crawler visited"
  and "this file cannot say which crawlers visited" are opposite findings. Printing the
  second as the first is the single failure this whole tool is arranged against.
- **`304` is not waste.** A conditional request answered "not modified" is the cheapest
  exchange there is; counting it against the site would penalise exactly what
  `cache_compression_checker.py` asks for two items away.
- **Never-crawled findings need a window of at least seven days**, and are `null` rather
  than `[]` below that, because an empty list reads as "we looked and found none". A
  one-day log would otherwise report every URL on the site as never crawled.
- **Percentages need at least 50 search-bot requests.** Three requests and one 404 is not
  "33% waste"; `summary.rates_meaningful` is a field so a rule can read it, and the
  percentages are absent rather than computed from nothing.
- **The User-Agent is a claim, not proof.** Confirming Googlebot needs a reverse DNS
  lookup this script does not make, so `bot_identity` says so in the output — a fixed
  sentence rather than a comment in the source. Distinct IPs per crawler are reported as
  data. See KNOWN-ISSUES for what that leaves unanswered.

Every threshold behind a severity is a constant at the top of the file with its
justification beside it, and each says plainly that it is a **convention, not a
measurement** — nothing here is calibrated against a corpus of real sites, because none
was available. §2 of KNOWN-ISSUES.md is about exactly this, and a new script was the wrong
place to add another unexplained number.

### Fixed — a robots-refused URL reported as a page nobody crawled

Two defects of the same shape, both found while writing this.

`server_log_audit.py` read `sitemap.robots_blocked` for something that lives at the top
level of the inventory. A wrong key does not raise: it reads as an empty set, the
subtraction quietly does nothing, and the tool reports **its own politeness as the site's
defect** — `/private/secret.html` is disallowed in the good fixture's `robots.txt`, and it
came out as a sitemap URL no crawler had visited. That is the 0.4.0 orphan-pages bug,
written a second time in a new script.

So the key names now live where they are written: `site_crawl.sitemap_urls()` and
`site_crawl.robots_refused()`, used by all three readers (`link_profile.py`,
`orphan_pages_from_sitemap.py`, `server_log_audit.py`). A shared accessor can only be
misspelled in every caller at once, which is a failure somebody notices.

And `applebot-extended` contains `applebot`, so substring matching counted a **robots.txt
token no client ever sends** as Apple's search crawler, and therefore as search crawl
budget. `Google-Extended` escapes it only by not containing `googlebot`. The robots-only
tokens are now checked first and land in `other`, where they are visible and decide
nothing. A test pins it.

### Changed — a missing input now says which flag supplies it

`missing input 'cwv_json'` names an internal key rather than the argument that fills it,
so an item reported NO_DATA for want of a file read as a limitation of the tool instead of
something a reader could fix with one flag. Three of those have been in reports since
0.6.0; the fourth is why they were noticed. `HOW_TO_SUPPLY` maps each operator-supplied
key to the flag, and only those — `html` and `inventory_json` are produced by the run
itself, so advice there would be advice to do something impossible.

### Tests — 493 → 508

Twelve for the log reader, and the ones that matter are the refusals: a log with no
User-Agent leaves `summary` and `bots` empty rather than zeroed, a rotated log gives
byte-identical answers to the plain one, `304`s appear and waste stays at zero, coverage
findings are `null` without an inventory, and a robots-only token is not counted as a real
crawler. Three more assert the direction: the good fixture's log produces no finding, the
broken one produces two `high`, and the AI crawler stays out of the crawl-budget number.

**The contract pair now supplies the log**, the way 0.6.0 started supplying the browser
artifacts — the good site's is a crawl that got what it asked for, 304s and all, and the
broken site's is a crawl budget going nowhere. Without both, CI-018 would pass by never
being asked.

Two existing tests changed scope rather than gaining an exemption. `NothingIsUndecided­
AboutASiteThatAnswered` asserts something about sites that answered, so it now covers the
runs that address a site — derived from the argv templates, not listed — and a second test
asserts the same guarantee for the log runs that *can* be read. And the artifact-item test
used to require every supplied file to describe one page, which held only while they all
did; `links_csv` is a site-wide export answering a page-level question and `server_log` is
a site-wide file answering a site-wide one, so "not page-describing" and "not page-level"
are now distinguished instead of collapsed.

## 0.10.1 — 4 August 2026

**Registry unchanged** (`18b1b372a6ed`, 214 items). Tests 492 → 493. `v0.10.0`'s CI failed and this is why; the tag
is left where it is rather than moved, because a release marker pointing at a red build
is a fact about the release and hiding it is the failure this project's changelog exists
to avoid.

### Fixed — robots.txt fetched once per process instead of once per run

Its disk cache has a 30-minute TTL and always had, but no lock: 45 evidence scripts
start inside the same second, all miss a file nobody has written yet, and all fetch.
`_fetch_robots` cannot go through `safe_request` — that would recurse through
`robots_allows` — so it now takes the same lock the response cache takes, with the same
read-again-after-locking and the same fall back to fetching if the wait runs out.

**This was found by the new CI assertion on the first run, not by the local
measurement**, which is the argument for asserting the count rather than printing it: the
duplicate depended on process scheduling, so it appeared five times on a GitHub runner
and once on a developer machine. The answer was correct either way and only the request
count was wrong, which is exactly the class of defect nothing finds later.

Two fetches of `/robots.txt` remain and are two different things: the policy the crawler
obeys, and the document `robots_checker.py` audits. Different consumers with different
failure semantics — the policy fetch fails open, the audit fetch reports — so they are
not merged, and the CI comment says so where it would otherwise look like a bug.

With it, the `--sample 3` fixture audit settles at **21 requests for 17 distinct
`(method, path)` pairs** — the number in 0.10.0's entry below, and the number CI now
measures. As tagged, `v0.10.0` made 24.

## 0.10.0 — 4 August 2026

**Registry unchanged** (`18b1b372a6ed`, 214 items). Tests 473 → 492. Nothing about what
is asserted changed; one evidence string did, and it is named below.

**One fetch per URL.** The other half of issue 1 in KNOWN-ISSUES.md. One audit of the
seven-page fixture, `--sample 3`, counted at the server: **201 requests → 21**, for 17
distinct `(method, path)` pairs. All 214 verdicts identical with the cache on and off.

### Added — the run-scoped response cache

`lib/safe_http.py` gained a response cache, which is where it belongs: all four of this
tree's HTTP seams converge on `safe_request`. `SEO_HTTP_CACHE` names a directory, the
runner creates one per run and deletes it when the run ends, and without the variable
nothing is cached at all — a script run by hand behaves exactly as it did in 0.9.0, and
no directory survives to answer a later audit.

**Requests were the smaller half of what this fixes.** Thirty-six evidence scripts each
need the page they are judging and each is its own process, so one document was fetched
37 times — and 37 fetches are 37 *different* documents the moment a page is not static.
Items could disagree about a page with every one of them right about what it read. That
is the failure the shared crawl removed for the site in 0.9.0; this removes it for the
page. `http_cache` is in the JSON artifact so a reader comparing verdicts that disagree
can tell which kind of run produced them.

What is never answered from disk, each because a stored answer would differ from a live
one:

- **A request that failed.** A timeout, a refused connection, a redirect loop and a
  `robots.txt` refusal are not answers. One transient failure must not become every
  item's failure — `NO_DATA` on 106 items is not more honest for being consistent. Any
  status code *is* an answer, 404 and 503 included; asking a server that just said 503
  thirty-six more times is the opposite of what the pacing is for.
- **A `POST`.** `indexnow_checker.py` submits URLs; replaying that from disk would
  report something that did not happen.
- **A body nobody read** (`stream=True`), and any request carrying a `session`, whose
  cookie jar a replayed response would not update.

The key is what could change the answer — method, URL, request headers,
`allow_redirects` — and nothing that could not. `timeout` is excluded because it decides
whether an answer arrives, never what it says. `max_response_bytes` is excluded because
a complete body satisfies any cap large enough to hold it, which is what lets callers
asking for 500KB, 1.5MB, 2MB and 5MB of one page share one entry; a cap *smaller* than
the stored body is a miss, and the request goes out and fails exactly as before, because
trimming the body to fit would be inventing a document.

`robots.txt` is not avoidable through the cache: the gate runs before the lookup, and a
stored redirect chain is re-checked hop by hop on the way out. Without that, any site
that redirects could opt out of the rule by being fetched twice — once by something that
does not consult `robots.txt`, then from disk by something that does.

Single-flight, per key, through a lock file. The runner starts eight workers together;
without it they miss together and eight processes fetch the page the cache exists to
fetch once. Waiting is bounded by the caller's own timeout and running out falls back to
fetching: a cache must not be able to turn one slow server into a hung audit. The lock
is taken *and then the entry is read again* — without that second read, a process whose
read missed while the writer was still fetching, and whose lock then succeeded because
the writer had just released, went and fetched a page already on disk. It cost one
duplicate GET in one measured run out of two.

### Fixed — two spellings of one request

Neither of these was findable before requests became countable, and both had been
fetching pages twice for as long as the code existed.

- **`Accept`.** `seo_common.fetch_url` sent its own, differing from `default_headers()`
  by one media type (`text/xml;q=0.9`). Both were reasonable; together they made every
  audited page two requests, because a different `Accept` is a different request and has
  to be. `DEFAULT_HEADERS` now carries the union and `fetch_url` overrides nothing, so
  no caller advertises less than it did. A test refuses a second spelling.
- **The trailing slash.** `lib/safe_http.normalize_url` left an empty path empty, while
  `seo_common.normalize_url` has always made it `/`. They are not two requests: every
  HTTP client puts `/` on the wire for an empty path. The disagreement fetched the
  site's own home page twice — once as the entry URL, once as a sampled one. A test
  requires the two normalisers to agree.

### Changed — one measurement instead of three

`elapsed` travels with a cached response rather than being zeroed, because
`broken_links.py`, `redirect_checker.py` and `lcp_subparts.py` report response time from
it and a zero would be a fabricated performance number. So **TECH-003's TTFB is now the
run's single fetch of the page** rather than `lcp_subparts.py`'s own request: on the
fixture it moved from 1ms to 3ms, the only one of 214 evidence strings that changed at
all. Deliberate — one measurement everything shares beats three scripts reporting three
TTFBs for one page. `--no-http-cache` restores the old behaviour.

### Added — `--no-http-cache`

Every script fetches for itself. Slower, more requests, and the page-level items may
then be reporting on different copies of a page that changed mid-audit — use it to find
out whether the cache is what a surprising result is about, or to time a single request
in isolation.

### Tests — 473 → 492

Nineteen new tests, all offline on loopback. The ones that matter are not the hit-rate
ones: a failure is never stored, a `POST` goes out every time, a stream is not stored, a
cached hit still refuses a path `robots.txt` forbids, a torn entry is a miss rather than
half a page, a smaller byte cap refetches rather than truncating, a restored response
matches the fetched one field by field including `elapsed`, **eight separate processes
asking at once make one request**, and the runner's cache directory does not outlive the
run. Two more pin the duplication fixes above so they cannot come back by being locally
sensible somewhere.

CI now empties the fixture server's log before the audit — so the printed count is the
audit's own rather than including the readiness probes — and asserts three things about
it: at most 40 requests, the entry URL fetched exactly once as a `GET`, and no URL
requested more than twice. The one legitimate pair is `HEAD` with redirects on and off,
which are two different questions.

## 0.9.0 — 4 August 2026

**Registry `f949859fabd1` → `18b1b372a6ed`** (214 items, unchanged in number; ten
items' arguments changed, three items' assertions replaced, one item moved from script
to LLM). Tests 462 → 473.

**One crawl instead of six.** This is issue 1 in KNOWN-ISSUES.md, the largest open item
since the file was written, and it pays three ways: the site is walked once,
`robots.txt` is honoured in one place, and the report can finally name the broken URLs
instead of counting them.

### Changed — the shared crawl

`site_crawl.py` crawls once into an inventory — status, redirect chain, title,
description, canonical, noindex (meta *and* `X-Robots-Tag`), word count, content hash,
MinHash signature, every link with its anchor, depth, and how the URL was discovered.
The runner runs it before it builds the plan and hands the file to the ten site-wide
items. Six scripts stopped crawling: `duplicate_content.py`, `link_profile.py`,
`internal_links.py`, `orphan_pages_from_sitemap.py`, `anchor_text_audit.py` and
`broken_links.py`.

Measured on the seven-page fixture, one audited page: **97 → 72 requests**, and the
site's inner pages went from six fetches each to two. CI asserts a ceiling instead of
printing the number, because a number in a green build is a number nobody reads.

What did *not* change is the other half of issue 1, which is now the dominant cost: 37
of those 72 requests are the entry URL, fetched again by each of the 36 single-page
scripts. There is no HTTP cache between them.

Two consequences worth knowing about before you diff a report:

- **`TE-168` is site-wide and internal-only.** It used to check every link on the entry
  page, internal and external, and now checks every internal link on the site.
  External link rot is BL-083's job (`external_link_quality.py`) and is no longer
  counted twice. `scope` in the output says which path produced the answer.
- **The ten site-wide items now describe the same page set.** They had six different
  ideas of what the site was — 25 pages at depth 1 for the anchor audit, 100 from the
  sitemap for the orphan check — so two items could disagree about a site and both be
  right about what they read.

### Added — the report names the URLs

`checklist-results.json` carries a `crawl` block, the inventory is written beside it
(`*-crawl.json`), and both the Markdown and HTML reports list broken and redirecting
URLs with the pages that link to each. A reader's next question after "3 broken links"
was always "which ones?", and the answer was "run the script yourself".

### Fixed — two items that could not fail, and one that had stopped answering

- **AR-149 "Eliminate Internal Redirects" asserted that `internal_links.pages` was
  non-empty** — true of any site that answers at all. Worse, 0.8.0 gave that script a
  `fetch_error` set unconditionally (the emptiness check ran before the field it tested
  was filled), so for one whole release the item was NO_DATA on every site, including
  sites it had crawled perfectly. Its contract-pair exemption read "no internal
  redirects to find without a server that redirects" — true, unrelated to the
  assertion, and it kept both defects invisible. It now reads
  `summary.internal_redirects`, which one crawl can measure.
- **AR-146 "Verify pagination is correct" asserted `pagination` was truthy**, and
  `pagination` is a dict that always holds both keys: `{"prev": None, "next": None}` is
  a non-empty dict, so the item passed every page in existence. It now reads a
  pagination `issues` list — a `rel=next`/`rel=prev` pointing off-host or at the page
  itself.
- **CN-055 had the mirror-image defect** and accused nearly every page audited:
  `pagination.next` truthy means "this page is part of a paginated series", and its
  absence is the normal state of an unpaginated page, not evidence of infinite scroll.
  It is an LLM item now, because nothing here observes scroll behaviour.

### Fixed — twelve more items grading a site that answered nothing

0.8.0's dead-origin sweep took its script list from a table maintained by hand in one
test file. So it could not see `orphan_pages_from_sitemap.py` (the one crawler with no
entry in that table) or the seven scripts tested in a *different* file — which are the
scripts deciding the nineteen `critical` items. The sweep is derived from the registry
now, and it immediately found:

- **`indexability_matrix.py`** — CI-001 "not indexable" and CI-005 "robots.txt allows
  it" as *verdicts* about a host that refused every connection. Three `critical` items.
- **`canonical_checker.py`** — CI-009 (`critical`) "missing canonical" for a page
  nobody could fetch. A page with no canonical and a page nobody read are not the same
  finding.
- **`local_seo_checker.py`** — LO-198 and LO-200 (both `high`) reporting a business
  with no local signals.
- **`orphan_pages_from_sitemap.py`** — GO-137 "no orphan pages", because
  `sitemap(∅) - reachable(∅)` is no orphans and no orphans is a PASS.

The API scripts are deliberately left out of that sweep, and the reason is written into
it: pointing them at a dead host makes the suite call `validator.w3.org` and a WHOIS
server, and this suite is offline.

### Fixed — five checks that accused every correct site

- **`schema_required_props.py` wanted `name`, `position` and `item` on the
  BreadcrumbList itself**, where no correct markup puts them — they belong to each
  `ListItem`. Every site with a working breadcrumb collected three "missing recommended
  property" warnings and AR-158 failed it.
- **The same file's placeholder detector tested `"["` against a JSON dump of the
  property value**, so every property whose value was a list or an object was reported
  as placeholder text. AR-158 failed correct breadcrumbs twice over, by two independent
  routes, in six lines of code.
- **`image_inventory.py` and `image_weight_audit.py` treated the first `<img>` in
  document order as the LCP candidate regardless of size.** CN-054 and MD-185 reported
  a correctly lazy-loaded 64px logo in a `<figure>` halfway down the page as a deferred
  LCP image. One definition now, in `seo_common.likely_lcp_candidate`, and it ignores
  images whose *declared* size is under 100×100.
- **`html_validator.py` read "the validator could not fetch your page" as "your page
  has no errors".** Nu answers 200 with `type: non-document-error` when it is blocked
  by a 403, a timeout or a TLS problem, and none of those messages is a document error
  — so CI-017 and TE-181 said the HTML validated. Same family as the outage 0.8.0
  fixed, one step deeper: the service answered, and the answer was not about the page.

### Added — the sweep that catches a check answering backwards

`test_contract.py` demanded that every script-backed item answer the good fixture and
the broken one *differently*. Difference is not direction: a check that fails the good
site and passes the broken one satisfied that test, and BL-081 had been doing exactly
that for two releases — five navigation links carrying the anchor "home" were
"exact-match anchor overuse", and the broken fixture had no repeated anchors to find.

So no script-backed item may FAIL or WARN on the good fixture without a written reason.
The list of reasons came out at six entries; the first draft had sixteen, copied from
the fixture's own README, and six of those were describing defects that had moved to
the broken fixture two releases earlier. The test found the documentation drift by
refusing to accept an exemption nothing needed.

BL-081's own fix is a distinction its threshold could not express: repetition *across*
pages is a navigation bar, repetition *within* a page is anchor stuffing. Only the
shared crawl makes that measurable — it needs to know what the whole site looks like.

### Fixed — smaller

- **The good fixture had a dead internal link on purpose.** It predates the good/broken
  pair and was invisible while TE-168 checked one page; a site-wide check found it and
  warned about the fixture the pair calls good. Planted defects belong in the broken
  one.
- **`--sample` re-read the sitemap** to find pages the crawl had already found, and
  re-checked `robots.txt` for URLs the crawl had already checked. It reads the inventory
  now — which is also why `--sample 3` on the fixture audits three pages where it used
  to find two.
- **`probe_shapes.py` crawls once and hands the inventory to the ten site-wide items.**
  Without it those ten are unprobeable, and an unprobeable item is how GEO-007 kept
  reading a field nothing emitted for three releases.

## 0.8.0 — 4 August 2026

**Registry `6e3cca477308` → `f949859fabd1`** (214 items, unchanged in number; one
item's arguments changed). Tests 357 → 462.

**Every one of the 55 evidence scripts now has a unit test.** The last release left 43
of them untested and called that phase 2; this is phase 2, and it went the way the
previous two did — the tests found defects at about one per three tests, and the
biggest of them was not in a script at all.

### Fixed — 62 items graded a site that answered nothing

The one test worth writing first, and it was written last: every URL-taking script
pointed at a port where nothing is listening, asserting that no item comes back PASS,
FAIL or WARN. Sixty-two did.

A script that fetches nothing exits 0 and returns its defaults — `score: 0`,
`missing_alt: 0`, `issues: []` — and those defaults grade. It is the same failure as
the run that once scored an unresolvable domain 61/100, one layer further in: the
entry-reachability gate catches a site that is dead *before* the audit starts, and
nothing caught a site that stops answering *during* one. Rate limiting, a WAF tripping
after N requests, a deploy mid-audit.

- The runner now treats a payload that says it read nothing as NO_DATA for every item
  reading it, with the reason. One place, covering every script — a `fetch_error` or
  an `error` (singular: the plural forms are per-URL and one refused page out of fifty
  must not discard the other forty-nine verdicts).
- Twelve scripts recorded no failure at all, so the runner could not tell. They do
  now, and two of the twelve needed more than a missing key: `anchor_text_audit.py`
  and `topical_cluster_mapper.py` counted the unreadable seed as a crawled page, so
  "zero overused anchors across one page" and "score 100 across one page" were
  reports about nothing.
- `url_quality.py` and `faceted_nav_audit.py` are exempt and tested as exempt: they
  judge the URL string and never fetch it, so a verdict about an unreachable host is
  correct.

### Fixed — five more verdicts nothing could have produced

- **GEO-007 "Submit URLs via IndexNow" read `key_valid`, which was never emitted.**
  NO_DATA on every site ever audited, including one hosting its key correctly. The
  same family as MS-031, and it outlived it for a duller reason: the item needs an
  IndexNow key to run, so `probe_shapes.py` had no input for it and the audit that
  compares asserted paths against real output had nothing to compare.
- **GO-132 "Prevent GA4 Tag Duplication" could not see the ordinary duplicate.**
  `duplicates` counted `gtag('config', …)` calls only, and GA4 usually ends up
  installed twice as two copies of the *loader* — a theme plus a plugin, or a
  hand-added tag beside GTM. The script said "gtag.js loaded 2x" in its `issues`
  list; the field the registry read could not.
- **BL-083 could not see a dead domain.** Broken meant `status >= 400`, and a host
  that does not resolve produces no status at all — so the ordinary form of external
  link rot was the one form the check missed. A timeout is deliberately still not
  called broken: that is a fact about the run, not the link, and it now has its own
  count.
- **AR-163 "Control Faceted Navigation" could not fail.** A crawl trap is a property
  of a *set* of URLs — five variants sharing a path, or a parameter recurring three
  times — and the registry handed the script the entry URL alone, which supplies one
  of each. `--from-page` audits the page's internal links instead, which is also the
  truer question: a facet becomes a trap when the site links to it.
- **CI-017, TE-181, CI-010, MS-023, KW-070, GO-139 and GO-135 reported site defects
  when a third party was unavailable.** `html_validator.py`,
  `gsc_cannibalization.py` and `gsc_url_inspection.py` pre-seeded their summary
  fields with `None` and their `issues` with `[]`. Neither is silence: `eq` and
  `truthy` read a None as a *failing value*, and `none_severity` reads an empty list
  as "nothing wrong". So a busy W3C validator became "your HTML has errors", and an
  expired token became "Google chose a different canonical" and "you do not rank
  first for your own brand". Absent keys now, which is what NO_DATA is made of.

### Fixed — smaller, found the same way

- **A 404 page was analysed as content.** An error page is HTML, so a site with one
  dead internal link collected a `Critical` thin-content finding telling somebody to
  expand a page that does not exist — and it counted against CN-039. A broken link is
  `broken_links.py`'s finding, made once.
- **`entity_checker.py` computed whether a street address is visible and dropped the
  answer**, so half of "check for visible phone/address" did nothing. Found by the
  linter 0.7.0 turned on.
- **`jaccard_from_minhash` zipped two signatures without `strict`.** A length mismatch
  would have biased similarity *downwards* and dropped duplicate pages under the
  threshold rather than raising.

### Changed

- `tests/harness.py` gained `served()`: a throwaway origin routed from a dict, so a
  test says what the site returns for each path — status, headers and body — without a
  directory on disk. That is what made 43 scripts affordable to test; 33 of them are
  single-fetch scripts that previously needed ten lines of hand-rolled stub each.
- The good fixture is no longer thin. Its longest page was 288 words against a
  300-word threshold, so the site the pair calls "good" tripped a `high` content
  warning — which weakens every claim the pair makes.
- `BL-083` left `SAME_ON_BOTH`. Its stated reason — "backlink items need a link index
  this tool does not have" — was wrong: it reads a count that needs no link index, and
  it answered the same on both fixtures because of the defect above. An exemption
  outliving a defect rather than a limitation is exactly what that list is checked
  for.

## 0.7.0 — 4 August 2026

**Registry `6e3cca477308`, unchanged.** No item changed what it asserts; what
changed is whether eight of them could produce a verdict at all, and whether two
more produced the right one. Tests 325 → 356.

Two threads. The fixture pair now supplies the browser-measured artifacts, so the
eight items that read them are exercised in both directions instead of reporting
NO_DATA on both. And the four defects still open in `KNOWN-ISSUES.md` §6 are fixed —
one of which was a check that failed sites for doing exactly what it recommends.

### Fixed — an artifact could decide items about a page nobody measured

- **A `--cwv-json` or `--rendered-json` file was accepted without asking which page
  it describes.** These are the only inputs an audit cannot verify by re-measuring:
  every other verdict comes from a request this process made. A trace of some other
  page — a staging copy, yesterday's URL, a colleague's file — decided **eight
  items, two of them `high`**, from numbers nobody took here, and the result looked
  exactly like a clean one. A mismatch is now NO_DATA with the reason naming both
  pages, which is a different instruction to the operator than "missing input": one
  says go and measure, the other says the file you made is about somewhere else. A
  file with no `url` is still accepted, and said out loud, because it predates the
  check and is more likely careless than wrong.
- **One measured page became a verdict about every sampled page.** Sampled runs
  inherit the whole run context, so the same trace was read once per URL, returned
  the same numbers each time, and the aggregate reported "4/4 pages" about four
  pages no browser had opened. Artifact-backed items are excluded from sampling and
  keep the primary run's verdict about the page the file is actually about.
- **The report never said a verdict came from a file rather than from a
  measurement.** "LCP 820 ms — PASS" reads identically either way. It now appears in
  the same "what was audited" block as a scored interstitial or a private host, and
  a *rejected* artifact is deliberately not listed there — it decided nothing.

### Fixed — the four open defects in KNOWN-ISSUES §6

- **MB-096 and MB-097 failed sites for following the recommendation.**
  `image_weight_audit.py` read `<img>` attributes only, and the recommended way to
  ship a modern format is a `<picture>` whose `<source>` offers webp or avif and
  whose `<img>` keeps a png fallback for browsers that cannot decode it — so the
  fallback was the only thing ever inspected, and "Use Responsive Images" and
  "Optimize Image Formats" both failed a site already doing it right. Both counts
  now consider what the browser can actually obtain, and the narrower `img`-only
  counts stay in the output, because "the browser gets webp and the fallback is a
  png" is two facts and a fix list must not conflate them.
  - Found while fixing it: **`lxml` mis-nests every `<picture>`.** libxml2 predates
    the element and does not know `<source>` is void, so it makes the `<img>` a
    *child* of the first `<source>`; `html.parser` gives it the `<picture>` as its
    parent, as the spec does. The first version of the fix checked `img.parent`,
    passed its tests, and would have changed nothing in production. Both parsers are
    now pinned by a test, and which one gets used still depends on whether `lxml`
    happens to be in `sys.modules` — recorded in `KNOWN-ISSUES.md`.
- **`tools/probe_shapes.py` held its own list of scripts.** The tool that verifies
  the registry's asserted paths against real output had drifted from the registry in
  both directions at once: it named seven scripts that no longer exist and missed
  three the registry reads — including `cwv_metrics.py` and `rendered_audit.py`,
  whose shapes this release changes. Jobs are now derived from `check.script` and
  `check.args`, deduplicated the way the runner deduplicates, and a job whose input
  is not available is skipped by name instead of probed with a literal
  `{gsc_property}` on the command line.
- **No declared Python floor.** `pyproject.toml` states `>=3.10`, and CI now runs
  3.10 — a floor nothing exercises is a guess. It is a real floor: three scripts
  annotate with PEP 604 unions without `from __future__ import annotations`, so on
  3.9 they raise `TypeError` at import, before any check runs and with nothing in
  the message about SEO. A test ties the CI matrix, `requires-python` and ruff's
  `target-version` together, and measures the claim against the tree's own syntax.
- **`ruff` was a listed development dependency that never ran.** It runs in CI now,
  and running it found two half-implemented checks: `entity_checker.py` computed
  whether a street address is visible on the page and then dropped it, so half of
  "check for visible phone/address" did nothing and only the phone was ever
  reported; `hreflang_checker.py` computed an `xhtml:link` flag it never returned.
  76 findings in total, 74 of them cosmetic, and the two that were not are the same
  family as everything else in this file — code that looks like it decides something
  and does not.

### Fixed — the report overstated its own translation coverage

- **`untranslated()` declared the report's own wording complete.** It was not: 6 of
  51 strings had no Russian, and they were the entire "what was audited" block —
  the highest-stakes prose in the document. `t()` falls back to English silently, so
  nothing showed. The count is now derived from the source rather than asserted, so
  a string added without a translation is reported the day it is added. The six are
  still English, deliberately: this release makes the claim honest, not the
  translation complete.

### Changed

- The fixture pair gained `tests/fixtures/artifacts/`, and the good site's image
  markup is now a real `<picture>` rather than the shape the old check could see.
  Those files carry hand-written numbers, and every one says so in its own `source`
  field — a test fails if that stops being true.
- `checklist-results.json` gained `artifacts`: which measured-elsewhere files a run
  was handed, what page each claims to describe, and whether that is the page
  audited.

## 0.6.0 — 3 August 2026

**Registry `8a66be60b820` → `6e3cca477308`** (214 items, unchanged in number).
Tests 304 → 325, and the new ones are a different kind: the whole registry is now
run against two served fixture sites — one satisfying as much of it as a static site
can, one engineered to fail — and **every script-backed item has to answer them
differently or say in writing why it cannot.**

That test is the point of this release. A check can only be verified by disagreeing
with something, and thirty-three assertions in this tool's history reported the same
verdict on every site ever audited. Each was found by accident, one family at a
time. Comparing a good site with a bad one catches the next family without anybody
having to name it first — and it caught four immediately.

### Fixed — two items that failed on every clean site

- **GO-136 "Provide clean XML sitemaps" and GO-138 "Remove invalid URLs from
  sitemaps" could not pass.** Sitemap discovery always probes `/sitemap.xml`,
  `/sitemap_index.xml` and `/sitemap-index.xml`, and every probe that came back 404
  was reported as an `error`. Those three names are alternatives, not a set, so a
  site with exactly one sitemap collected two errors — which failed GO-136 on
  severity and GO-138 on the literal "404" in the message. **Every audit this tool
  has produced carried both.** A probed name that is absent is now not an issue at
  all; a sitemap that robots.txt *declares* and that fails to load still is, and "no
  sitemap found anywhere" is its own error so the fix cannot swallow the real case.
- **The non-HTTPS sitemap warning is skipped for private hosts.** A staging site on
  `http://` is not making an SEO mistake. For anything publicly routable it stands.

### Fixed — three checks that could not fail

- **GO-138, again, underneath the first bug.** With the phantom 404 gone the item
  passed everything: the 404/redirect/noindex issues its pattern looks for are only
  emitted when `sitemap_checker` actually requests the URLs it found, and the
  registry never passed `--fetch-urls`. So "remove invalid URLs from sitemaps"
  reported PASS for a sitemap made entirely of dead links. It now fetches up to 25
  of them. One fabricated FAIL was hiding one impossible PASS.
- **CN-040 "Publish an up-to-date privacy policy" asserted the wrong field.** It read
  `signals.policy_links`, which `eeat_signal_checker` populates from *editorial*
  policy — fact-checking, corrections, ethics. A site with a proper privacy policy
  failed unless it also published editorial standards; a site with an ethics page and
  no privacy policy passed. There is a `signals.privacy_links` now, and the item
  reads it.
- **`duplicate_content` reported the home page as its own duplicate.**
  `extract_internal_links` stripped the trailing slash unconditionally, so
  `http://example.com/` became `http://example.com` — a second URL for the same
  document. The seed kept its slash, both were crawled, both returned identical
  bytes, and the exact-hash comparison called it **Critical** duplicate content. Any
  site with a `href="/"` link in its navigation, which is every site, got that
  finding. The root keeps its slash now; everything deeper loses it.

### Fixed — a crash

- **`image_weight_audit.py --fetch-images` died with `KeyError: 'url'`** on any page
  with a broken image. The row key is `src`. It could only fire on a page MD-187
  ("fix broken images") exists for, so a site with no broken images ran fine and
  reported 0 — the crash was invisible until a fixture was built with a 404 image in
  it.

### Changed

- The fixture pair is served by `tests/harness.py` on two origins, because
  `robots.txt`, the sitemap and `llms.txt` live at the root of an origin: one
  document root cannot be both present and absent. Each site's outbound links point
  at the other origin, which is external by host and still on loopback — a real
  `https://` link in a fixture would make `broken_links.py` take the suite online,
  and the previous fixture's links to `example.com` did exactly that.
- The good fixture stopped carrying deliberate defects. An orphan page and a
  robots-disallowed sitemap entry lived in it, which meant CI-008, AR-162, GO-137 and
  GO-138 were never observed passing anything. A fixture cannot demonstrate the
  defect and the agreement in the same place.

### Known, and now written down

`image_weight_audit` reads only `<img>` attributes, so a site serving webp through
`<picture><source type="image/webp">` with a png fallback — the recommended pattern —
counts as having no modern format at all. Recorded in `KNOWN-ISSUES.md` rather than
worked around.

## 0.5.0 — 3 August 2026

**Registry `5bf1e36d657f` → `8a66be60b820`** (214 items, unchanged in number).
Tests 270 → 304, of which 34 are the first tests any evidence script has ever had.

Phase 2 was "write tests for the scripts that decide the `critical` items". Seven
scripts decide seventeen of the nineteen. Writing the tests found that **eighteen
items were reporting a verdict nothing could have produced** — five of them
`critical` — and every one had been doing it on every site ever audited.

This is the same failure as the fifteen dead regex assertions in 0.1.0, in two
families the pattern audit could not see. If you have an audit from 0.4.0 or
earlier, these items' verdicts were not measurements.

### Fixed — five critical items that could not fail

- **CI-009 "Serve content at a single canonical URL"** asserted that `issues` held
  nothing at `critical`/`high`. `canonical_checker.py` says `warning` and `error`
  and never those two words, so the rule matched nothing and the item passed — with
  a canonical pointing at another domain, or with no canonical at all. Now a
  `value_map` over the script's own `verdict`: `cross_host` and `missing` fail,
  `unknown` is unmapped and therefore NO_DATA.
- **CI-001 "Ensure URL is indexed"** asserted `rows.0.robots_allowed` — the same
  field, with the same rule, as CI-005 "do not block the URL in robots.txt". So a
  page marked `noindex`, or served `X-Robots-Tag: noindex`, or canonicalised
  elsewhere, passed a critical item about being indexed. `indexability_matrix.py`
  already weighed all of that into `verdict`; nothing read it. Now it does.
- **SP-113 "Meet Core Web Vitals thresholds"** and **SP-107**, **SE-119** compared
  `metrics.*.rating` to `"fast"`. `pagespeed.py` merged two vocabularies into that
  field — CrUX's `FAST/AVERAGE/SLOW` and Lighthouse's `good/needs-improvement/poor`
  — so the rule could only be satisfied by field data, and **CrUX publishes none
  for a low-traffic URL**. A page with a 1.5-second lab LCP was rated `good`, the
  rule wanted `fast`, and a critical item reported FAIL for a fast page. The script
  now speaks one vocabulary (`crux_category` keeps CrUX's own word beside it) and
  the rules `value_map` it, so an unknown band is NO_DATA rather than a verdict.
- **SP-108 "Pass Core Web Vitals (field data)"** asserted that field data *exists*,
  which is not the question in its title and answers it wrongly: it failed every
  site too small for CrUX to sample. `pagespeed.py` now emits `field_cwv.verdict`
  only when there is field data, so its absence is NO_DATA — "nobody measured your
  real users" is not "your real users had a bad time".

### Fixed — thirteen more items, same disease

Ten items asked for `critical`/`high` severities over scripts whose entire
vocabulary is `error`/`warning`/`info`. `checklist_runner` now maps the second onto
the first (`error` → high, `warning` → medium, `info` → low) so a rule author only
has to know the registry's four words, and those items get an explicit `warn` rule:
an error-class finding fails, a warning-class one warns. Affected: GO-136, LO-200,
AR-154, AR-163, MD-185, MD-190, MB-102, SP-110, TE-170, TECH-002.

Two more could not be fixed that way, because **`robots_checker.py` and
`security_headers.py` append plain strings to `issues`** — there is no severity to
read. `security_headers.py` was printing "🔴 Site not using HTTPS" and "🔴 6 security
headers missing" while TE-175 reported PASS. Both now read structured fields:
AR-151 asserts `status == 200` (its verb is *provide* a robots.txt) and TE-175
asserts `headers_missing` has at most three entries — the script's own bar for
"poor security posture". A `none_severity` rule over a list carrying no severity
anywhere is now NO_DATA in the runner too, rather than a silent pass.

And **MS-031 "remove meta keywords"** read `meta_keywords`, a field `parse_html.py`
never emitted, with `missing_is: pass`. The script emits it now.

### Added — so this family cannot come back

`tools/audit_assertions.py` audited patterns only. It now also audits:

- **severity rules** — a `none_severity` asking for a severity its script never
  emits fails the build. Severity literals are read from the AST (`{"severity":
  "High"}` and `issue("warning", …)` look nothing alike), because a regex over the
  source finds every word in the file and clears rules that cannot fire — the
  mistake the first version of this tool made.
- **every asserted path** against the machine-probed
  `resources/references/script-output-shapes.md`. A rule reading a field no probe
  has ever seen fails the build, with a listed exemption per path that exists only
  with a credential the probe did not have.

CI runs it, and a test runs it too. 34 new tests in `tests/test_evidence.py` cover
the seven scripts, each asserting the field the registry actually reads and
verifying the retired rules still misbehave — a test that a bug is a bug is what
stops a fix being quietly reverted.

## 0.4.0 — 3 August 2026

Registry unchanged (`5bf1e36d657f`, 214 items). Tests 248 → 269, and CI runs the
full live path for the first time.

One feature, three bugs it immediately found, and one gap in the report it made
visible. The feature is small; what it unlocks is not — until now the only way to
exercise fetching, crawling, pacing and aggregation was to point the audit at
somebody else's website, and the worst bug in this plugin's history (0.2.0's rate
limiter crashing 36 of 56 scripts) was invisible to every offline test.

### Added

- **`--allow-private`** permits a host on loopback, RFC 1918, ULA or CGNAT
  addresses — a staging site before launch, or a fixture served locally. Off by
  default; the SSRF guard is unchanged for every run that does not pass it. The
  allowed set is enumerated rather than "anything not public": **link-local stays
  blocked even with the flag**, because cloud instance metadata answers at
  169.254.169.254 and the URLs a crawl follows come from the site being audited.
  Reserved, multicast and unspecified ranges stay blocked for the same reason.
  Announced on stderr, in the console summary (even under `--quiet`), in
  `checklist-results.json` as `allow_private`, and in the report.
- **A fixture site and a CI job that audits it.** `tests/fixtures/site/` is six
  pages with a sitemap, a robots.txt and planted defects — an orphan, a sitemap URL
  that robots.txt disallows, a broken link, a duplicated meta description. CI serves
  it and runs the whole path: guard, crawl, sample, pace, aggregate, render. The job
  fails if **any** evidence script crashes, which is the check 0.2.0 did not have.
  It also prints the request count for one audit of a six-page site (167), so the
  fan-out that [KNOWN-ISSUES.md](KNOWN-ISSUES.md) item 1 is about is visible in the
  build log rather than only on somebody else's server.

### Fixed — numbers move

- **An address is no longer given a registrable domain.** `127.0.0.1` came out as
  `0.1`, the run built `sc-domain:0.1`, and both Search Console scripts crashed on
  it. On a public IP it would have been quieter and worse: a valid-looking property
  nobody owns answers with nothing, and nothing reads as a site with no search
  traffic. There is now no default property for an address, and the run says so
  instead of inventing one.
- **Checks that need an outside service are `NO_DATA` on a private host**, with the
  reason, rather than crashing. PageSpeed measures the page from Google's network,
  Safe Browsing looks the URL up, a Search Console property cannot exist for an
  address on a LAN — none of that is a defect in the site or the tool, and "script
  failed" sent the reader to open a script that was working correctly. `NO_DATA` and
  not `N/A`: the items apply to this site, so they stay in the coverage denominator
  and a pre-launch audit honestly reports thinner coverage. An explicit
  `--gsc-property` is still honoured — auditing a staging copy against the live
  site's history is a decision the operator is allowed to make.
- **A sitemap URL that `robots.txt` disallows is no longer counted as an orphan.**
  0.3.0 subtracted refusals the *crawl* recorded, and a crawl only tries what the
  site links to — so a disallowed URL that nothing links to arrived with no refusal
  attached and became an orphan, turning our own politeness into the site's defect.
  That is the ordinary case, not an edge one: a page is usually unlinked *because*
  it is blocked. The sitemap side is now checked against `robots.txt` directly, at
  no extra request cost (the answer is cached per origin). **Expect `GO-137` and
  `AR-162` to move on any site with a `Disallow:` rule and a sitemap.**

### Changed

- **The report says what was audited, above the summary.** Three facts the runner
  has always recorded and printed never reached the file that gets handed to
  somebody: a run allowed off the public internet, an entry page that looked like a
  bot challenge and was scored anyway (`--no-page-guard`), and an entry page with
  almost no visible text. A `--no-page-guard` run therefore produced a clean-looking
  deliverable that never mentioned it had graded a Cloudflare interstitial — the same
  failure as printing a score for a site that was never read, one surface further
  along.

## 0.3.0 — 3 August 2026

Registry unchanged (`5bf1e36d657f`, 214 items). Tests 229 → 248.

Three fixes from the post-0.2.0 review, all of which change numbers a run prints.
None of them was a fabricated verdict; each overstated **how much of a site was
looked at, or how comparable two numbers were.**

### Changed — numbers move

- **`--sample N` now spans the site.** It took the first N URLs in sitemap document
  order, and sitemaps are ordered by section or by date, so it collected one corner
  and the report said "on 5 of 5 pages checked". Picks are now spread by an
  arithmetic stride across the whole list, covering both ends. Still reproducible —
  the step is arithmetic, not random, so an unchanged sitemap yields the same pages
  next month. **Expect different sampled pages, and therefore different verdicts,
  than 0.2.0 reported on the same site.**
- **The per-category scores are weighted by severity**, like the headline SEO Score
  they sit next to. They were an unweighted pass rate: one category read 25 where
  its weighted score was 42, and the report *ordered* its bars by the unweighted
  number, so "look here first" could point past a failing `critical` at five failing
  `low`s. Each bar now also carries the worst open severity, because no single
  number can express "one failing critical in an otherwise clean category".
- **`robots.txt` is honoured for pages the tool discovers itself** — followed links,
  sampled sitemap entries, and any redirect those land on. It is deliberately **not**
  consulted for the URL the operator supplies. A blanket check would refuse the
  40-odd scripts that fetch `{url}`, collapse the audit to `NO_DATA`, and bury the
  finding that matters: "this page is blocked from crawling" is a `critical`
  checklist item, a result rather than a prohibition. `Crawl-delay` is obeyed when it
  asks for more patience than `--max-rps` allows and ignored when it would ask for
  less — a site can tell us to slow down, not to be less careful than we chose.
- **`broken_links.py` checks at most 200 links**, internal first, and reports
  `truncated` when it did. It previously checked every link on the page with no
  bound: 300 links meant 300 requests.

### Fixed

- **A robots refusal could have invented a FAIL.** `orphan_pages_from_sitemap.py`
  computes orphans as `sitemap − reachable`, and GO-137 fails on one, so a URL we
  declined to fetch would have left `reachable` and been reported as an orphan —
  our own politeness rendered as the site's defect. Refusals are tracked separately
  and subtracted, and a sitemap listing robots-blocked URLs is now its own finding,
  which is the sharper one anyway.
- **The robots check uses the bare product token, not the full User-Agent.**
  `RobotFileParser` splits the agent at the first `/` and lowercases it, so passing
  `Mozilla/5.0 (compatible; AgenticSEOSkill/1.0; …)` yields `mozilla` — a site whose
  `robots.txt` names `AgenticSEOSkill` would have been silently ignored while `*`
  rules applied instead. Verified against CPython's `Entry.applies_to`; there is a
  test.
- **robots.txt is cached on disk**, not per process, so 45 evidence scripts in 45
  processes fetch it once between them rather than 45 times.

Every robots failure path is fail-open: an absent, unreachable, unparseable or
5xx `robots.txt` allows the request. RFC 9309 permits treating a server error as a
full disallow, and for an unattended crawler that is right, but this is an audit
the site's own operator asked for. Refusing to look because `robots.txt` returned
503 turns a transient hiccup into an audit of nothing.

## 0.2.0 — 3 August 2026

Registry `7b8c8a3295fd` (211 items) → `5bf1e36d657f` (214 items).
Tests 90 → 229, all offline. First release with CI that has actually executed.

### The theme

Every change below came from running the tool rather than reading it. Nine of
them were verdicts that were fabricated: a number in the report that nobody
looking at the report could tell was invented. The audit's one promise is that
"we could not check this" never reads as pass or fail, and each of these broke it
somewhere specific.

### Changed — a run can now produce different verdicts than 0.1.0 did

- **A page that is not the site is no longer scored.** Bot-protection
  interstitials (Cloudflare, Incapsula, PerimeterX, DataDome, AWS WAF, Sucuri,
  Distil) and soft 404s are detected before grading, and the items that need the
  real page report `NO_DATA` with the reason instead of grading the challenge
  page. 0.1.0 scored a Cloudflare challenge 6 PASS / 10 FAIL. `--no-page-guard`
  restores the old behaviour when the interstitial *is* the thing being audited.
  Detection is by fingerprint, so an unknown vendor still gets through — the
  thin-entry warning surfaces the symptom without deciding, because an unknown
  interstitial and a client-rendered shell are indistinguishable from the HTML
  and the second is a real finding.
- **Cross-host redirects are followed for real.** The final URL is carried into
  the audit instead of being discarded, so a site that redirects to another host
  is audited as that host rather than reported against a URL nobody fetched.
- **Outbound requests are paced.** 4 requests/second/host by default
  (`--max-rps`), enforced across processes with a locked slot file, and
  `Retry-After` is honoured on 429/503. `--workers 8` with `--sample N`
  previously burst against a third party with no pacing at all. Audits are
  slower; this is the only change here that protects somebody other than the
  audit's own honesty.
- **Fifteen assertions that could never fire have been replaced.** Six of 21
  regex-over-prose rules did what they claimed; the other fifteen matched nothing
  in any output and so returned `PASS` unconditionally. Structured assertions
  where the script emits usable data, `llm` or `manual` where it does not.
  `tools/audit_assertions.py` now fails the build if a pattern cannot fire, and
  it also catches a rule matching its own module docstring, its own argparse help
  or its own remediation text — three real cases (CI-013, KW-072, KW-073).
- **Eight items moved from `script` to `llm`** because the scripts they named had
  never looked at what they asked about. Five of those are measurable rather than
  judgeable and became browser-measured instead: `rendered_audit.py` reads type
  size, link distinguishability, overlays and tap-target size from a real render.
  Mobile-only metrics are dropped rather than zeroed when the trace was a desktop
  window. Without the artifact these report `NO_DATA`, so coverage on a plain run
  is lower than 0.1.0 reported — 0.1.0's number was higher and wrong.
- **Search Console items that no API can answer are `MANUAL`**, not `NO_DATA`
  pending a key that would never satisfy them.
- **Timeout is distinguished from crash** from a missing script and from unusable
  output. All four were one silent `NO_DATA` before.
- **The registrable domain comes from the Public Suffix List** (bundled dated
  snapshot, MPL 2.0, `tools/refresh_public_suffix_list.py --check`), so the
  default `sc-domain:` property is right for `example.co.uk` and friends.
- **The report is written for the person paying for it.** Four layers in one
  file: a three-sentence plain summary before any number, category bars with a
  plain-language explanation of what each group of checks protects, fix cards
  carrying the measurement as a sentence, and the full checklist with raw
  evidence folded underneath. The Markdown and HTML structure both changed; a
  consumer parsing 0.1.0's tables will not find them.

### Added

- Three lab Core Web Vitals items (SP-214/215/216) via `cwv_metrics.py`: the
  agent traces with a real browser, the script reads the artifact, the registry
  decides from thresholds. TBT stands in for INP, which cannot be measured from a
  page load, and says so.
- An adversarial second reading of the LLM verdicts (`--llm-review`) that can
  only withdraw confidence: agreement corroborates, disagreement returns the item
  to `NO_DATA` carrying both readings, and the reviewer cannot answer an
  unanswered item or overwrite a verdict.
- `--lang` and a Russian translation of the report chrome and all 16 category
  explanations. Item titles and recommendations are not translated yet, so
  `--lang ru` produces a half-Russian document and now says so on stderr.
  **Client delivery is English-only until those are filled in.**
- CI on Python 3.11 and 3.13: registry gate, assertion gate, `compileall`, the
  Public Suffix snapshot's date, and four end-to-end runs including an
  unreachable site and a challenge page.
- `LICENSE` (MIT), upstream licence text reproduced in `CREDITS.md`, and source
  provenance recorded inside `plerdy-titles.json` itself rather than only
  alongside it.

### Fixed

- The rate limiter crashed 36 of 56 scripts in its first live run. The slot file
  was opened `"a+"`, POSIX append ignores `seek`/`truncate`, timestamps
  concatenated, and the resulting `ValueError` escaped a handler that only caught
  `OSError`. Score read 72/100 at 29% coverage instead of 79/100 at 64%.
- The report printed `SEO Score None/100` when the entry page could not be read.
- History picked the wrong previous run: ISO timestamps were compared against
  filename stamps as strings, so a legacy file always won.
- Two runs in the same second overwrote each other's history entry.
- `broken_image_count: None` graded `eq: 0` as `FAIL`. The key is now absent when
  images were not checked, so the item reports `NO_DATA`.
- `local_seo_checker.py` reported a high-severity `FAIL` on a site with valid
  `Restaurant` schema, because `LocalBusiness` was matched as a string against
  `@type` rather than against its subtypes.
- The fix list ranked by severity alone: `effort` never reached the report, so
  the Effort column printed `?`.
- Page-sampled items showed a passing measurement under a failing verdict — the
  verdict came from the worst page, the number from the entry page.
- `article_seo.py` crashed on JSON-LD in array or `@graph` form; `lib/safe_http.py`
  exited the process at import when `requests` was absent;
  `validate_skill_inventory.py` had a regex that never matched, so the check it
  performed validated nothing.
- Three script counts in `plugin.json`, `CREDITS.md` and the research record
  disagreed with each other and with the tree.

### Known issues found after this release

A full review measured nine defects and gaps, ranked with their evidence in
[KNOWN-ISSUES.md](KNOWN-ISSUES.md). None of them fabricates a verdict — that class
of bug is what this release fixed. They overstate how much of a site was looked at
and how comparable two numbers are, which is the next class down.

Four were fixed in 0.3.0; see that entry. The largest is still open: a single audit
fetches the same pages ~275 times, because five scripts crawl independently and
nothing is cached.

## 0.1.0 — 3 August 2026

First version. 211 items, 90 offline tests, no repository and no CI yet.

Established what the rest of this file defends: a fixed registry generated from
the checklist and content-hashed, declarative assertions rather than per-item
code, SEO Score and Coverage reported separately and never merged, and a status
vocabulary where `NO_DATA` and `MANUAL` stay in the coverage denominator so an
unanswered question cannot be quietly rounded into a good result.
