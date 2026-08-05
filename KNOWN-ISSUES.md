# Known issues

What is wrong with this plugin as of **0.19.1**, ranked by consequence, with the
evidence for each. Nothing here is a suspicion: every entry was measured against
the tree.

This file exists because the audit's one promise — that "we could not check this"
never reads as a verdict — applies to the plugin's own description of itself. A
defect known and unwritten is the same failure one level up.

**Measured in 0.18.0, and the answer is uncomfortable.** `measured` is still 0 and that
is the honest count: what `tools/audit_score_sensitivity.py` measured is not the weight
table but the consequence of it being wrong. Re-scored across four real runs from flat
1/1/1/1 to steep 27/9/3/1, the headline moves 0.2, 1.9, 9.3 and **14.6** points. So the
table cannot be written off as decoration, and the driver is not how many items were
decided — it is how far the per-severity pass rates spread, which means the score is
most sensitive to an unexamined number on exactly the sites where severity
discriminates. `EFFORT_COST` came out the other way: dividing by effort changes 2-4 of
the first ten fixes and so earns its place, while the exact ratio does not — 1/2/3 gives
the identical first ten on every run measured.

**Fixed in 0.16.0**: the report's own arithmetic. `Coverage %` added together three
quantities that measure different things — how far the tool reached, how much work the
operator had done, and how much of the checklist was never the audit's job — and then
moved for any of the three without saying which, which is this file's founding
objection applied to the number this file's project reports. It is replaced by the
score's weight share and a partition of the registry that has to add up. `NEEDS_INPUT`
split out of `NO_DATA` on the way, because a partition reconstructed by matching prose
inside an evidence string is a coupling that breaks in silence. Two defects fell out of
the change: the HTML history section had been printing `coverage None%` with no test
over it, and a shared string would not have parsed on the declared 3.10 floor.

**Fixed in 0.15.0**: four of the five open items. The answer-block score no longer
depends on whether a page closes its tags — and the sibling walk that caused it was
hiding a second defect that needed no invalid markup at all. Every number a verdict
rests on now carries a stated basis, which moved `inherited` from 14 to 75 and turned
up two thresholds written twice. `--verify-bots` confirms a crawler by reverse-then-
forward DNS and takes a forged one out of the crawl-budget figures. A supplied
measurement's age is shown and can be bounded. And the Russian report's caveat block —
19 strings, not the six this file claimed — is translated.

**Fixed in 0.14.0**: the HTML parser was chosen by import order, so one machine could
parse a page two ways and two scripts inside one audit could disagree — measured,
decided, recorded in the artifact and overridable. Four of the five site shapes in issue
3 are now exercised live, TLS included. And an evidence script killed by the operating
system no longer reports as a script that failed.

**Fixed in 0.12.0**: issues 4 and 5 — the report says what changed since the previous
audit, and `--fixes` writes the actionable items where a tracker can read them. Both were
data the audit already had and did not hand over.

**Fixed in 0.11.0**: nothing on this list; CI-018 stopped being `manual` and became the
first item answered from a server log. On the way, a robots-refused URL reported as a page
nobody crawled — the 0.4.0 orphan bug written a second time in a new script — and a
robots.txt token counted as a search crawler because of a substring.

**Fixed in 0.10.0**: the rest of issue 1 — a run-scoped response cache means one fetch
per URL, and the fixture audit went from 76 requests to 16 with all 214 verdicts
unchanged. It also made a duplication visible that nothing could count before: two
spellings of one `Accept` header, from the two conventions in this tree, had been
fetching every audited page twice.

**Fixed in 0.9.0**: the crawling half of issue 1 — six independent crawls became one
shared one, and the report finally names the broken URLs instead of counting them. On
the way: twelve more items that graded a site which answered nothing (including three
`critical` ones, invisible to the previous release's sweep because that sweep's script
list was hand-maintained), an item that could not fail and its twin that accused every
site, and five checks that reported a defect in every correct site on the internet.

**Fixed in 0.8.0**: issue 2 below, which was the largest open item after the shared
crawl — every one of the 55 evidence scripts now has a unit test. Writing them found
sixty-two items that graded a site which answered nothing, five more that could not
produce the verdict they claimed, and seven that reported a defect in the site when a
third party was unavailable.

**Fixed in 0.7.0**: the four defects that used to be §6's first four bullets — the
`<picture>` blind spot that failed sites for following the recommendation, a
shape-probing tool that had drifted from the registry it verifies, an undeclared
Python floor, and a linter that never ran — plus an artifact being trusted without
being asked which page it describes.

**Fixed in 0.5.0**, below the line: eighteen items — five of them `critical` —
that were reporting a verdict nothing could have produced, and the two audits that
now stop that family recurring.

**Fixed in 0.4.0**: the SSRF guard having no escape hatch (and with
it, the absence of any live-path test), an address being given a registrable domain,
external-API checks crashing instead of reporting `NO_DATA` on a private host, a
robots-disallowed sitemap URL counted as an orphan, and the report never saying when
it was describing something other than the public site.

**Fixed in 0.3.0**: `--sample` taking the first N sitemap URLs, the report's two
incompatible scales, the crawlers ignoring `robots.txt`, and `broken_links.py`
having no cap.

---

## 1. Closed in 0.10.0 — one fetch per URL

Kept at the top because the shape of it is the useful part, not the fix.

An audit used to ask a seven-page site the same question 37 times. Nothing was written
badly to make that happen: 36 evidence scripts each need the page they are judging,
each runs in its own process, and nothing connected them. It closed in two halves,
because it was two problems wearing one number.

**The site-wide half (0.9.0).** Six scripts walked the same pages independently — 50
pages each for `duplicate_content.py`, `link_profile.py` and `internal_links.py`, 100
for `orphan_pages_from_sitemap.py`, 25 for `anchor_text_audit.py`, and one page's links
for `broken_links.py` — each with its own budget, its own robots handling and its own
idea of what the site was. `site_crawl.py` now writes an inventory and all ten
site-wide items read it.

**The per-page half (0.10.0).** A run-scoped response cache in `lib/safe_http.py`,
where all four of this tree's HTTP seams converge. `SEO_HTTP_CACHE` names a directory;
the runner makes one per run and deletes it afterwards, so a hand-run script caches
nothing and no directory survives to answer a later audit.

Measured against the seven-page fixture, one audit with `--sample 1`, counted at the
server:

| | Requests | The entry URL | The site's inner pages |
|---|---|---|---|
| 0.8.0 | 97 | 37× | 6× each |
| 0.9.0 | 76 | 37× | 2× each |
| 0.10.0 | **16** | **1×** | **1× each** |

Sixteen requests for fifteen distinct `(method, path)` pairs. The one repeat is `HEAD /`
twice, and those are two different questions: `redirect_checker.py` asks with redirects
off because the hop *is* the finding, and the cache/compression check asks with them on.

**Requests were the smaller half of what it cost.** Thirty-seven fetches are
thirty-seven different documents the moment the page is not static — a CMS rotating a
hero image, a deploy landing mid-audit, an A/B test — and items would then disagree
about the page with every one of them right about what it read. That is the same failure
the crawl inventory removed for the site, one level down, and removing it for the page
is the guarantee; the requests are the side effect. `http_cache` is in the artifact so a
reader comparing two verdicts that disagree can tell which kind of run produced them.

The safety argument is in the exclusions, and each one is a way a stored answer would
differ from a live one:

* **Only real responses.** A timeout, a refused connection, a redirect loop and a
  robots.txt refusal are never stored, so one transient failure cannot become every
  item's failure. Any status code *is* an answer, 404 and 503 included.
* **GET and HEAD only.** `indexnow_checker.py` submits URLs; replaying a submission
  from disk would report something that did not happen.
* **The key is what could change the answer** — method, URL, request headers,
  `allow_redirects` — and not what could not. `timeout` is out because it decides
  whether an answer arrives, never what it says. `max_response_bytes` is out because a
  complete body satisfies any cap large enough to hold it, which is what lets callers
  asking for 500KB, 1.5MB, 2MB and 5MB of one page share one entry; a cap *smaller*
  than the stored body is a miss and the request goes out and fails exactly as before,
  because trimming it to fit would be inventing a document.
* **robots.txt is not avoidable through it.** The gate runs before the lookup, and a
  stored redirect chain is re-checked hop by hop on the way out. Otherwise any site
  that redirects could opt out of the rule by being fetched twice.
* **Single-flight.** The runner starts eight workers together; without a lock per key
  they miss together and eight processes fetch the page the cache exists to fetch once.
  Waiting is bounded by the caller's own timeout and running out falls back to
  fetching — a cache must not be able to turn one slow server into a hung audit.

**One consequence to know about.** `elapsed` is restored with the entry rather than
zeroed, because three scripts report response time from it and a zero would be a
fabricated performance number. So TECH-003's TTFB is now the run's single fetch of the
page rather than `lcp_subparts.py`'s own — on the fixture it moved from 1ms to 3ms, the
only one of 214 verdicts whose evidence string changed at all. That is deliberate: one
measurement everything shares beats three scripts reporting three TTFBs for one page.
`--no-http-cache` restores the old behaviour for anyone who wants an isolated timing.

CI asserts a ceiling of 40 requests on the fixture audit at `--sample 3`, and that the
entry URL is fetched once, so a regression fails the build rather than only somebody's
server.

## 2. The tests prove a script's shape, not its thresholds

**Closed in 0.8.0**: all 55 evidence scripts have unit tests, and each asserts *the
field the registry actually reads*, named in the test. The count is not the point —
the yield is. Four releases of writing these found, in order: eighteen assertions that
had never fired, two items that failed sites for serving images the recommended way,
sixty-two items grading a site that refused every connection, and then twelve more of
that family plus five checks that accused every correct site. Roughly one defect per
three tests, and the rate has not fallen off.

Four layers now, each catching what the others cannot:

| Layer | What it proves |
|---|---|
| `test_evidence.py`, `test_evidence_scripts.py`, `test_evidence_apis.py` | a named field answers a named question, in both directions |
| `test_contract.py` — the good/broken pair | a check can tell two whole sites apart, or says in writing why it cannot |
| the dead-origin sweep | nothing is decided about a site that answered nothing |
| the good-site sweep | nothing is decided *against* the site that should pass |

The last two are four lines each and found more than everything above them. Both take
their list of what to cover **from the registry**, which they did not always: 0.8.0's
sweep enumerated a table maintained by hand, so the one crawler nobody had listed and
the seven scripts tested in a different file were exactly the scripts it could not see
— three `critical` items among them. A sweep whose coverage is a list somebody
maintains has the same blind spot as the thing it is checking.

What remains is not coverage but calibration. **A test can show that a threshold
fires; it cannot show the threshold is right.** A site audited at the wrong threshold
gets a confident verdict about the wrong question, which is the failure this suite is
worst at seeing, and nothing automatic can close it — a number's correctness is a
judgement, not an assertion.

**What 0.13.0 opened and 0.15.0 finished is the invisibility.**
`tools/audit_thresholds.py` finds every number a verdict depends on and requires each to
carry a stated basis, checked in CI. 0.13.0 could see 36 of them; 77 more were
comparisons against a bare literal, which cannot carry a basis because there is no name
to hang one on. All of them are named now:

| Basis | 0.13.0 | 0.15.0 | What it means |
|---|---|---|---|
| `standard` | 4 | 6 | an external published authority, named — Google's Core Web Vitals bands, the sitemaps.org URL limit, HSTS preload's one-year `max-age` |
| `measured` | **0** | **0** | calibrated against something, and the text says what against |
| `convention` | 18 | 32 | a judgement made here, stated as one: a round number because a line had to be somewhere |
| `inherited` | 14 | **75** | arrived with the borrowed code and has not been examined |
| unnamed | 77 | **0** | a bare literal, with nowhere to carry a basis at all |

**Two findings, and the second one is why the naming was worth the diff.**

*Zero `measured`.* Not one threshold in this tree was arrived at by measurement; every
number is either somebody else's standard, a judgement, or an inheritance. That was the
suspicion this section carried since it was written, and it is a figure now.

*`inherited` is 75 and not 14.* The unnamed literals were not a random scatter — 59 of
the 77 were already present in the initial commit. So the honest statement is that
**roughly two thirds of the numbers this registry's verdicts rest on arrived with
borrowed code and have never been examined by anybody here**, and the old 14 read that
way only because the other 61 had nowhere to carry a label. An inventory that undercounts
in the flattering direction is the failure this file exists to prevent, and it did it to
itself for two releases.

`inherited` is assigned from evidence rather than memory: a constant counts as inherited
when `git show <initial commit>` finds it already there. The list includes the ones that
matter most. **`SEVERITY_WEIGHT` — critical 10, high 6, medium 3, low 1 — decides the
SEO Score itself**, and nobody here has asked whether a critical item is worth ten low
ones or three; the score has been reported to two significant figures the whole time.
`EFFORT_COST` divides it to rank what to do first, so the ratio between two unexamined
tables is doing real work. `THIN_CONTENT_THRESHOLDS`'s 300 words is one of the numbers
this section used to name, and its provenance turned out to be exactly what was
suspected: conventional in SEO writing, with no source anybody here can point at. The
whole of `gsc_checker.py`'s opportunity rules read as SEO-blog folklore stated in
numbers — "striking distance" is a phrase, not a measurement.

Three things fell out of the naming pass, each of which is the argument for it:

- **Two thresholds were written twice** — 300 words for thin content, and the
  30-second `Retry-After` ceiling. One number in two places is one number that can be
  revised in one of them. Both have one home now.
- **A check and its own advice disagree.** `article_seo.py` accepts a title of 30-65
  characters while the fix text beside it asks for 50-60, and accepts a meta description
  of 100-165 while advising 120-155. Recorded in the basis lines rather than reconciled:
  which pair is right is a calibration, and that pass was an inventory.
- **The audit tool had two blind spots of its own.** It excluded 100, 1000 and 1024 as
  "units rather than limits", and removing them surfaced eleven comparisons of which ten
  were real thresholds. And it counted equality comparisons on the unnamed side while
  counting only ordering comparisons on the named side, so the two halves of one tool
  disagreed about what a threshold is.

A fifth kind, `presentation`, covers the eleven numbers that decide what is *printed* and
never what is decided, and is kept out of the total above — a report listing three
linking pages instead of four is a report making a different choice, not an audit
reaching a different verdict.

0.9.0 is the evidence that this is not theoretical. Sharing one crawl changed *how
many pages* the anchor-text check reads, and BL-081's threshold — five identical
anchors to one target, 80% of the links to it — went from firing on nothing to firing
on every site with a navigation bar. The check had been reporting the good fixture and
passing the broken one for two releases, and the contract pair recorded that as a
difference and called it working. The fix was a distinction the threshold could not
express: repetition *across* pages is a menu, repetition *within* a page is stuffing.

Two narrower gaps, both measured:

- **Three scripts are exercised only through a stub**: the two Search Console readers
  and the W3C validator. Nothing here can prove they read Google's *real* response
  shape, only the shape they were written for. That is the honest limit of an offline
  suite, and the reason `tools/probe_shapes.py` exists.
- **Structural queries are the one place a parser can change a verdict**, and both
  known sites are now handled rather than pinned: `picture_sources()` copes with either
  DOM, and the answer-block scanner was rewritten against document order in 0.15.0. A
  test asserts the two parsers *agree* — which is a stronger guard than the old pair of
  pinned numbers, because it fails on the next query written against sibling position
  rather than only on the two that were. What still has no guard is a structural query
  nobody has written yet, and the standing lesson is that `find_next_sibling()` and
  `recursive=False` are both questions about where the parser thinks an element ends.

## 3. One site shape is still untested live, and it is the one a fixture cannot be

Four of the five shapes item 3 used to list are exercised live as of 0.14.0, in
`tests/test_shapes.py`: a **cross-host redirect** (two origins, a real 301), a **bot
protection challenge** (a Cloudflare fingerprint served with a 200, refused, plus the
mirror case of an article *about* Cloudflare being audited anyway), a **sixty-page site**
where `--sample` has to choose and the stride has to reach the far end, and **TLS** —
the harness generates a certificate and hands it to the child through
`REQUESTS_CA_BUNDLE`, so `verify=True` stays on and the HTTPS and HSTS items get their
first verdicts from a real handshake.

What remains is **a Search Console property with enough history for the cannibalization
items**. It needs a property Google recognises and a key that can read it; neither is
something a fixture can be, and a test that stubbed the API while claiming live
coverage would be worse than the gap. Those items are covered by stubbed unit tests and
report `NO_DATA` against any fixture, which is the honest answer.

Still true, and worth keeping in view: every origin in the suite is loopback, so
nothing here exercises a slow network, a flaky connection, or a CDN's behaviour under
load.

## 4. Closed in 0.12.0 — the deliverable has history

`.seo-runs/` always stored every run. The comparison was computed only when somebody
passed `--diff`, printed to a terminal, and gone when the terminal closed — so the
report a client received could not say whether the last round of fixes worked, from
data that was already on disk. It is computed whenever a previous run exists now, and
both renderers carry a "Since the previous audit" section: score and coverage
movement, and the items that changed.

The part worth keeping is the third bucket. A change is `improved`, `regressed`, or
**`evidence`** — because `PASS` → `NO_DATA` is not the site getting worse, it is the
run losing the ability to tell, usually a third-party service that was down or a
supplied file that stopped being supplied. Filing that under regressions would tell a
client their site broke when the measurement broke, and the reverse would take credit
for a fix nobody made.

The baseline is named rather than implied: the artifact carries `compared_with` with
the other run's timestamp, registry version, mode, profile and scores. "Since the
previous run" is not a date, and a comparison whose other half is anonymous cannot be
checked by the person being shown it.

**Still one previous run, not a series.** A trend over six months is a different
feature and is not written.

## 5. Closed in 0.12.0 — there is a machine-readable fix list

`--fixes PATH` writes just the actionable items — id, status, severity, effort,
priority, category, title, what to do, evidence — as CSV or JSON, chosen by the
suffix. Ordered the way the report orders them, so a tracker and the report agree
about what to do first.

`FAIL`, `WARN` and `MANUAL` only. `NO_DATA` is not a fix — it is usually work for
whoever runs the audit rather than whoever owns the site — and `LLM_PENDING` is a
question still waiting for an answer; either one would fill somebody's sprint with the
auditor's own unfinished business.

The URL column is called `audited_url` and not `url`, because that is what it is: most
items record no page. A page-level check run over a sample reports the worst page's
verdict without carrying its address, and a site-level check has no single page to
name. A column called `url` would be read as "fix this page".

## 6. Smaller, but they will bite

- **Open — CI-019 fails every site that does not sell anything, and its own fix text
  cannot satisfy it.** Found on a live audit of a Lithuanian café, 5 August 2026, where
  it reported `high`/FAIL naming `/cart`, `/checkout`, `/login` and `/search`. All four
  return **404**. The site has no shop and no login.

  The item runs `robots_path_tester.py {url} /search /cart /checkout /login` and asserts
  `allowed_urls` is empty. That script fetches **robots.txt and nothing else** — read it:
  `test_paths` calls `fetch_robots`, then `robots_allowed` per path, and never requests
  the path itself. So it cannot know whether the URL exists, and a site answering
  `Allow: /` reports all four as exposed whether they are pages, 404s, or names nobody
  ever used. This is 0.9.0's "five checks accused every correct site", sixth member, and
  the blast radius is larger than any of those: **every brochure, local-business and
  portfolio site on the internet fails a `high` item here.**

  **The second defect is worse than the first and is not fixed by adding a fetch.** The
  title says *Noindex* System & Search Pages and the `fix` says "Set noindex,follow"; the
  assertion tests **robots.txt allow/deny**. Those are different mechanisms and the
  advised one *cannot* satisfy the check — a page carrying `noindex` is still `allowed`
  in robots.txt, so an operator who does exactly what the item tells them still fails it.
  Meanwhile the only remediation that *does* satisfy it, `Disallow:` in robots.txt, stops
  Google fetching the page and therefore from ever seeing the `noindex` — the documented
  way to leave a URL indexed with no content behind it. **The check rewards the fix that
  breaks the thing the item is named after.** That is §2's "a check and its own advice
  disagree", promoted from a recorded inventory item to a verdict shipped against a real
  site.

  **Why the good-site sweep does not catch it — answered, and it is the first of the two
  hypotheses this entry offered.** `tests/fixtures/good/robots.txt` contains
  `Disallow: /search`, `/cart`, `/checkout`, `/login`, under a comment reading *"The paths
  CI-019 exists to keep out of an index."* The fixture was built to satisfy this item. So
  the sweep is not blind in general — it is looking at the one site on the internet where
  CI-019 is meaningful.

  That generalises past CI-019 and is the more useful half: **a fixture constructed to
  pass the registry cannot catch an item that accuses every real site**, because whoever
  built the fixture tuned it for that item. The sweep's guarantee — "nothing is decided
  against a site that should pass" — is narrower than it reads: it holds for the site the
  registry was written against, and says nothing about the ones it was not. Nothing here
  fixes that; a second fixture built *without* consulting the registry would, and is not
  written.

  **It was not a single case, and the same run proved it.** CN-053 is titled *Avoid
  Critical Content in iFrames*, its fix text says "Do not hide critical content inside
  iframes", and its assertion is `raw.word_count >= 300`. **It counts words.** Nothing in
  it observes an iframe. The café failed it on three of eight pages for a 293-word page
  and was advised about iframes it does not have. This one is the more dangerous of the
  two: CI-019's mismatch is visible in the evidence, which lists four URLs a reader can
  check, while CN-053's FAIL looks entirely sensible until somebody opens
  `checklist.json`. **Two instances in one audit means 0.20 is about a class, not an
  item** — the whole registry needs the triple checked: does the assertion measure what
  the title names, and does the fix text describe the thing that would satisfy it. That
  is a mechanical audit and belongs in `tools/`.

- **Open — four items are two items, written twice, and both halves score.** `CI-017` and
  `TE-181` are both titled *Validate HTML (W3C)*, both call `html_validator.py` with the
  same arguments, and both assert `summary.errors == 0`; they differ in category and in
  the wording of the fix. `CI-016` and `MD-186` are the same pair for alt text —
  one `image_inventory.py`, one `missing_alt == 0`, `high` on both. On the café audit two
  validation errors produced two FAILs and **one image missing an `alt` produced two
  `high` FAILs.**

  Under `SEVERITY_WEIGHT` that is one defect carrying double weight in the headline
  number, and in `--fixes` it is two rows for one piece of work. The duplication arrives
  honestly — the Plerdy source lists the same requirement under two of its own headings,
  and `plerdy_ref` is load-bearing — so deleting an id is not obviously right. But the
  score must not double-count: either one id decides and the other mirrors its verdict
  without contributing weight, or they merge and the mapping records that two source
  numbers point at one check.

  **Counted, and it is eleven groups rather than two.** `tools/audit_item_semantics.py`
  compares script, args and assertion across all 214: CI-016/MD-186, CI-017/TE-181,
  GO-144/GEO-004, GO-145/GEO-005, MB-097/MD-189, MB-102/MD-190, MB-104/TE-166,
  MS-027/MS-028, MS-029/CN-041, SE-116/TE-171, SE-117/SE-118. Three pairs mix severities,
  so **the weight one defect carries depends on which twin the reader looks at.** Two was
  never a count — it was how many a single audit happened to fail on, and nothing in this
  tree had ever asked.

  **One of the eleven is a different and worse defect than the other ten.** `SE-117`
  *Force HTTPS Sitewide* and `SE-118` *Valid TLS Certificate (HTTPS)* are both `critical`
  and both assert `https == True`. Those are not one requirement written twice — they are
  two requirements sharing one assertion, and the second **cannot fail independently on
  any site**. A site with HTTPS forced and a certificate that expired yesterday passes
  both. SE-118 sits in the registry weighing `critical` and checks nothing SE-117 does
  not, so the fix is neither a merge nor a mirrored verdict: it needs evidence of its own
  — `notAfter`, the chain, the hostname match — and until it has that, this registry has
  never once verified a certificate.

- **Open — two items report something that is not a defect of the site, and one of them
  cannot be acted on at all.**

  `TE-179` *Review Domain History & Reputation* asserts `whois.age_days >= 90`. The café's
  domain was 58 days old, so it failed. **A new domain is not a reputation problem and
  there is no work that closes this item** — it resolves itself in a month, and until then
  it occupies a line in the fix list. A task nobody can do teaches the reader to skim the
  list, which is the one thing a prioritised list cannot survive.

  `GO-134` *Resolve Search Console Issues* reads `opportunities` through
  `none_severity: [critical, high]`, and on this site it fired on **"Position 4.0 with 115
  impressions — within striking distance"**. Ranking fourth is good news, printed as a
  `high` failure. §2 already says `gsc_checker.py`'s opportunity rules are SEO folklore
  stated in numbers, but that is about whether the thresholds are right; this is narrower
  and does not depend on them. **The field is called `opportunities`. An opportunity is
  not a failure at any threshold**, and reading one through a severity gate turns the
  best finding in the report into the item a client is told to fix first.

- **Closed in 0.19.1 — and it was never a flake.** `none_matching` over an `issues[]`
  array without a `field` matches the whole serialised issue, URLs included, so
  GO-138's `404` matched the *port* of a test origin that bound 40455. The
  nondeterminism was an ephemeral port sometimes containing three digits, and every
  theory built from the "flaky test" framing — DNS, the parallel runner, shared
  rate-limit state — was wrong. It is a registry defect: a sitemap listing
  `/blog/404-errors-explained` fails GO-138 on any site, and GO-143's `WebSite` was one
  `/website-design` URL from the same. **Third occurrence of one mistake** — the
  keyword items fired on their own remediation text in 0.5.0, which is why `field`
  exists, and the soft-404 guard says "never a substring" in writing. Neither was ever
  turned on the rules. The entry below is what it replaced; it is kept because the
  useful part is the shape: printing the payload cost four lines and settled in one
  firing what three rounds of reasoning got wrong.

- **One test is not deterministic, in a suite whose whole premise is that it is.**
  `test_go_138_needs_the_urls_fetched_to_find_anything` failed once on CI under 3.10
  and passed on a re-run of the same commit; 15 local runs of the full suite and of
  that module alone produced 0 failures. It asserts that a sitemap check run *without*
  `--fetch-urls` cannot report a 404, a redirect or a noindex, and it saw one.
  Reading `sitemap_checker.py` settles what it cannot be: all three of those issues
  are emitted inside the `if fetch_urls` branch, and that run does not pass the flag.
  The parallel runner was the obvious suspect and is not — `run()` returns its key
  with its payload and shares no path between the four concurrent `sitemap_checker`
  runs. **Not diagnosed, and deliberately not guessed at**: the assertion now prints
  the issues it actually saw, so the next occurrence names its own cause instead of
  costing another hour of theory. Until then the honest statement is that one verdict
  in this suite has been observed to depend on something nobody here has identified,
  which is the same class of defect as the parser divergence 0.14.0 pinned as a fact
  — and the lesson from that one is that recording the symptom is not the same as
  understanding it.

- **Closed in 0.15.0 — the answer-block score.** `answer_block_scanner.py` found the
  answer to a heading with `find_next_sibling()`, which asks the parser where the
  heading's parent ends, and that is the one question the two parsers answer
  differently. Three queries were rewritten against document order and nearest-ancestor
  ownership, which is what both parsers — and the browser — agree about. Kept here
  because of what it turned into: 0.14.0 *pinned* the 10-against-32 as a fact, and a
  verdict that depends on which library is installed is not a fact worth recording. And
  the sibling walk was hiding a second defect that needed no invalid markup at all — a
  `<div>` between the heading and the paragraph, which is every themed CMS there is, was
  itself read as the answer, so the word count was the whole section's. **The bug that
  gets written down instead of fixed is the bug whose neighbour never gets found.**
- **macOS kills a forked child inside Apple's own framework, and the runner forks 55 of
  them.** Once Network.framework has been initialised in a process, `fork()` runs its
  `pthread_atfork` child handler — `nw_settings_child_has_forked` — which dereferences
  freed state and segfaults *in the child, before it execs*. Nothing of the child's own
  code has run, so the failure is silent: signal 11, no stdout, no stderr. It surfaced
  in this project's own suite, where `tests/test_shapes.py` passed alone and its audits
  died under `discover` depending only on which module ran first; the crash report names
  the chain outright. `run_script` and `harness.spawn` now start children through
  `posix_spawn`, which does not fork, and a signal death is classified as `signal` with
  the signal named rather than as `crash` with "exit code -11". What is *not* fixed: the
  trade is that a child inherits this process's descriptors for the moment before exec.
  **The 0.14.0 note that "the workaround holds while nothing reintroduces a `cwd=` or
  `close_fds=True`" was already wrong when it was written**: eight other call sites in
  this tree still forked, because `posix_spawn` also requires
  `os.path.dirname(executable)` to be non-empty and a bare `openssl` or `git` has none.
  The openssl child in the TLS harness died of signal 11 and reported itself as
  `SkipTest("openssl unavailable")`, so the site shape 0.14.0 called *exercised live* had
  never run on macOS — 4 local skips against Linux CI's 1, which nobody read. Closed in
  0.15.0 as three AST-checked rules over every `subprocess` call in the tree —
  `close_fds=False`, no `cwd=`, no bare binary name. The lesson kept here: **a workaround
  guarded at its own call site is guarded at one call site**, and a diagnostic that names
  the wrong cause is worse than no diagnostic.
- **Closed in 0.15.0, and still a claim by default.** `--verify-bots` does the
  reverse-then-forward DNS check Google, Bing and Yandex document, and re-attributes a
  forged crawler's requests out of the crawl-budget figures rather than annotating them
  in place. What is *not* closed is the default: without the flag, `bot_identity` still
  says the identity is a claim, because the flag is a network call about a third party
  and this project does not make those without being asked. Three crawlers —
  DuckDuckBot, SeznamBot, PetalBot — publish address ranges rather than a DNS
  convention, so they answer `no_published_rule` and remain claims even with the flag;
  inventing a rule for them would report every visit they make as forged.
- **The rendered-page artifacts are the one input that cannot be checked by
  re-measuring**, and 0.15.0 got as close as that allows. 0.7.0 closed the part that
  could be checked: an artifact naming a different page is refused with the reason. The
  age is now stated in the report in days and `--max-artifact-age` refuses one that is
  too old — off by default, because how stale a measurement may be depends on how often
  the page changes and there is no honest default for that. The age comes from the
  filesystem's mtime and not from any timestamp inside the file, which is the whole of
  what it adds: everything an artifact says about itself is the operator's claim. **Still
  not verifiable** — `touch` exists — only visible and boundable, which is as far as
  re-measuring cannot reach.
- **The page guard is fingerprint-based**, so an interstitial from a vendor it does
  not recognise still gets through. Deliberate: an unknown interstitial and a
  client-rendered shell are indistinguishable from the HTML, and the second is a
  real finding, so the run warns with the visible word count instead of refusing to
  score.
- **Closed in 0.19.0 — the Russian report is Russian throughout.** All 214 item
  titles and all 214 recommendations are translated, and the claim is computed by a
  test against `checklist.json` rather than declared in the file. That matters here
  more than the translation does: this file has twice asserted a completeness it did
  not have, both times in the flattering direction. What no test can catch is a
  translation that has drifted in meaning from the item it translates — a translated
  title is a second copy of the registry's wording, and only the ids are checkable.
  The stale entry below is what it replaced.

- **A Russian report still carries English item titles.** The report's own 100 strings
  are fully translated as of 0.15.0. The 19 that were not — and this file said six,
  because 0.12.0's "Since the previous audit" section arrived untranslated after the
  claim was written — were the "what was audited" caveat block, the highest-stakes prose
  in the document, silently falling back to English. What remains is `item_titles` and
  `item_fixes`: 214 titles and their recommendations, which is a translation project
  rather than a code change. The stderr warning names both layers rather than implying
  the report is fully Russian, and that counting — added in 0.7.0 — is the only reason
  either gap was ever visible.

---

## Fixed in 0.9.0

Found by replacing six crawls with one, and by two four-line sweeps that the release
also taught to derive their own coverage.

- **The crawling half of issue 1.** `site_crawl.py` crawls once into an inventory; the
  ten site-wide items read it. 97 → 72 requests for one audited page of the fixture,
  and the site's inner pages went from six fetches each to two. The report now lists
  broken URLs with the pages that link to them.
- **AR-149 could not fail, and had been NO_DATA on every site for a release.** The item
  is titled "Eliminate Internal Redirects" and asserted that `internal_links.pages` was
  non-empty — true of any site that answers. Then 0.8.0 introduced a `fetch_error` set
  unconditionally (the check ran before the field it tested was filled), so the item
  was NO_DATA everywhere; its contract exemption said "no internal redirects to find
  without a server that redirects", which was true, unrelated, and hid both defects.
  It now reads `summary.internal_redirects`, which the shared crawl can measure.
- **Twelve more items graded a site that answered nothing**, three of them `critical`:
  `indexability_matrix.py` reported a page "not indexable" and robots.txt "allows it",
  `canonical_checker.py` reported a missing canonical, `local_seo_checker.py` reported
  a business with no local signals, and `orphan_pages_from_sitemap.py` reported no
  orphan pages — all about a host that refused every connection. Every one was outside
  0.8.0's sweep, because that sweep's script list was maintained by hand.
- **AR-146 could not fail either.** It asserted `pagination` was truthy, and
  `pagination` is a dict that always holds both keys — `{"prev": None, "next": None}`
  is a non-empty dict. Its twin CN-055 asserted `pagination.next` was truthy, so every
  page that is not part of a paginated series — nearly every page audited — was told to
  "make infinite scroll crawlable". AR-146 now reads a pagination `issues` list;
  CN-055 became an LLM item, because nothing here observes scroll behaviour.
- **Five checks accused every correct site.** `schema_required_props.py` asked for
  `name`, `position` and `item` *on the BreadcrumbList*, where no correct markup puts
  them (they belong to each `ListItem`), and its placeholder detector tested `"["`
  against a JSON dump of the value — so every property whose value was a list or an
  object was "placeholder text". AR-158 failed every site with a working breadcrumb,
  twice over. `image_inventory.py` and `image_weight_audit.py` treated the first `<img>`
  in document order as the LCP candidate regardless of size, so CN-054 and MD-185
  reported a correctly lazy-loaded 64px logo as a deferred LCP image.
- **The W3C validator answering "I could not fetch your page" was read as "no
  errors".** Nu reports that as `type: non-document-error` with a 200, so CI-017 and
  TE-181 said the HTML validated on any page the validator could not reach — a 403
  aimed at its user agent, a timeout, a TLS problem. The same family as the outage
  0.8.0 fixed, one step further in: the service answered, and the answer was not about
  the page.
- **The good fixture had a dead internal link on purpose**, planted before the pair
  existed and invisible while TE-168 checked one page's links. A site-wide check found
  it immediately and warned about the fixture the pair calls good.

## Fixed in 0.8.0

Found by writing the last 43 scripts' tests. The first one written found nothing; the
one written *last* found sixty-two items, which is worth remembering next time the
cheap sweeping test gets postponed for the careful per-script ones.

- **62 items graded a site that answered nothing.** A script that fetched nothing
  exits 0 and returns its defaults, and the defaults grade. The entry-reachability
  gate catches a site dead *before* an audit; nothing caught one that stops answering
  *during* it. Fixed in the runner for every script at once, plus twelve scripts that
  recorded no failure for the runner to read.
- **GEO-007 read `key_valid`, a field never emitted** — NO_DATA on every site,
  including one hosting its IndexNow key correctly. It outlived MS-031 because the
  item needs a secret to run, so nothing ever probed its output.
- **GO-132 could not see the ordinary GA4 duplicate** (two copies of the loader, which
  is how a theme and a plugin collide), **BL-083 could not see a dead domain** (no
  status code means no `status >= 400`), and **AR-163 could not fail at all** (a crawl
  trap needs a set of URLs; the registry passed one).
- **Seven items reported a site defect when a third party was unavailable.** `None`
  pre-seeded into a summary reads as a failing value to `eq` and `truthy`; an empty
  `issues` list reads as "nothing wrong" to `none_severity`. A busy W3C validator
  became "your HTML has errors"; an expired token became "you do not rank first for
  your own brand".
- **A 404 page was analysed as thin content**, so one dead internal link produced a
  `Critical` finding advising somebody to expand a page that does not exist.
- **`entity_checker.py` dropped the address half of its own NAP check**, and
  `jaccard_from_minhash` compared signatures without `strict`, which would bias
  similarity downwards and lose duplicate pages rather than raising.

## Fixed in 0.7.0

Two of these were found by supplying the fixture pair with the artifacts it had been
withholding, and two by turning on a linter that had been sitting in
`requirements.txt` unused. Both are the same lesson as every other release here:
the defects are not where anybody was looking.

- **An artifact was trusted without being asked which page it describes.** A
  `--cwv-json` or `--rendered-json` file decides eight items, two of them `high`, and
  it is the only evidence in an audit that cannot be checked by measuring again. A
  trace of a staging copy, or of yesterday's URL, produced eight confident verdicts
  about a page nobody measured — and looked like a clean result. Now refused with the
  reason, which is a different sentence from "missing input": one tells the operator
  to measure, the other tells them the file they made is about somewhere else.
- **A single measured page became a verdict about every sampled page.** `--sample`
  runs inherit the run context, so the same file was read once per URL and the
  aggregate said "4/4 pages" about pages no browser had opened.
- **MB-096 and MB-097 failed sites for following the recommendation.** The image
  audit read `<img>` attributes only, so a `<picture>` offering webp through
  `<source>` with a png fallback in the `<img>` — the recommended pattern — counted
  as having no modern format and no `srcset`. The one guaranteed-old thing in that
  markup was the only thing inspected.
- **The tool that finds drift had drifted.** `probe_shapes.py` held its job list by
  hand and named seven scripts that no longer exist while missing three the registry
  reads. Jobs now come from the registry.
- **The Python floor was undeclared, and then unexercised.** `>=3.10` is now stated
  and CI runs it, tied together by a test that also measures the claim against the
  tree's syntax.
- **Two half-implemented checks, found by the linter's first run.**
  `entity_checker.py` computed whether a street address is visible and dropped it, so
  only the phone half of "visible phone/address" was ever reported;
  `hreflang_checker.py` computed an `xhtml:link` flag it never returned.
- **The report claimed its own wording was fully translated.** Six of 51 strings were
  not, and they were the caveat block. The warning now counts instead of asserting.

## Fixed in 0.5.0

Found by writing the first tests the evidence layer has ever had. Every one had been
reporting the same verdict on every site ever audited, and the count is the point:
after 0.1.0 removed fifteen dead regex assertions, eighteen more were sitting in two
families the pattern audit could not see.

- **Five `critical` items could not fail.** CI-009 asked for `critical`/`high` issues
  from a script whose whole vocabulary is `warning`/`error`. CI-001 "is this URL
  indexed" asserted the same field, with the same rule, as CI-005 "does robots.txt
  block it" — so `noindex` passed it. SP-107/SP-113/SE-119 compared a rating to
  `"fast"`, a word only CrUX uses, so a fast page with no CrUX sample **failed**.
  SP-108 asserted that field data exists, failing every site too small to be sampled.
- **Ten more items** asked for `critical`/`high` over scripts that only say
  `error`/`warning`/`info`. The runner now maps the two vocabularies onto each other
  and those items carry a `warn` rule, so an error fails and a warning warns.
- **Two items read prose that has no severity at all.** `robots_checker.py` and
  `security_headers.py` append plain strings to `issues`; the latter was printing
  "Site not using HTTPS" while TE-175 reported PASS. Both now read structured fields.
- **One item read a field that was never emitted.** MS-031 asserted `meta_keywords`
  with `missing_is: pass`, and `parse_html.py` had no such key.
- **`tools/audit_assertions.py` now audits severity rules and asserted paths**, not
  only patterns, so each of the three families fails the build instead of the audit.

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
