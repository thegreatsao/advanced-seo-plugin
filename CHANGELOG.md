# Changelog

`registry_version` in `checklist.json` tracks the audit contract — which items
exist and what each one asserts. It changes whenever the checklist changes, which
is not the same event as the plugin changing. This file tracks the plugin: the
runner, the report, the scripts and the run modes around that contract.

Versions are `MAJOR.MINOR.PATCH` before 1.0, where the minor is bumped for
anything that changes what a run produces — including a change that makes the
output *more* honest. A verdict that used to be `PASS` and is now `NO_DATA` is a
breaking change for whoever read the old number, and saying so is the point.

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
