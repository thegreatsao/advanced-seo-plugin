# Known issues

What is wrong with this plugin as of **0.11.0**, ranked by consequence, with the
evidence for each. Nothing here is a suspicion: every entry was measured against
the tree.

This file exists because the audit's one promise — that "we could not check this"
never reads as a verdict — applies to the plugin's own description of itself. A
defect known and unwritten is the same failure one level up.

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
fires; it cannot show the threshold is right.** MB-095 warns at 250 KB, CN-039 at 300
words, SP-216 at 200 ms of blocking time, BL-081 at five identical anchors, the LCP
candidate floor at 100×100 declared pixels — those numbers came from Google's
published guidance, from the borrowed scripts, and in the last two cases from this
release deciding them. No test here argues with any of them. A site audited at the
wrong threshold gets a confident verdict about the wrong question, which is the
failure this suite is worst at seeing.

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
- **The `<picture>` fix nearly shipped broken** because `lxml` and `html.parser`
  disagree about the DOM, and which one runs depends on import order — see §6. A test
  now pins both. Nothing pins the other structural queries that do not exist yet.

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

- **Which HTML parser reads a page depends on import order.** `seo_common.parse_html`
  picks `lxml` if and only if `"lxml" in sys.modules` at the moment it runs — not on
  whether lxml is installed. So a page can be parsed two different ways on the same
  machine, and the two are not equivalent: libxml2 predates `<picture>` and does not
  know `<source>` is void, so it nests the `<img>` *inside* the first `<source>` while
  `html.parser` follows the spec. Nothing structural depended on this until 0.7.0,
  when the `<picture>` fix nearly shipped broken because of it — `picture_sources()`
  copes with both and a test pins the divergence. The real fix is to decide the parser
  deliberately, and it is not a one-liner: choosing lxml everywhere spreads the
  mis-nesting, choosing `html.parser` everywhere gives up its tolerance of broken
  markup, and both change the substrate under every verdict. It needs measuring on
  real sites, not a default.
- **A crawler's identity in a server log is a claim, not proof.** `server_log_audit.py`
  classifies by User-Agent, which is a string the client chose. Confirming Googlebot
  needs a reverse DNS lookup plus a forward confirmation, and this script makes no
  network calls at all — partly by design, and partly because the test suite is offline
  and a DNS-dependent check could not be verified there. So a scraper announcing itself
  as Googlebot inflates the crawl-budget numbers, and the direction of the error is
  towards *over*-reporting the crawl. `bot_identity` says this in the output rather than
  in a comment, and distinct IPs per crawler are reported so a reader can notice one
  address doing all of it. Verification would be a `--verify-bots` flag; it is not
  written, because adding an unverifiable network call to a new script's first release
  is the risk this project keeps refusing.
- **The rendered-page artifacts are the one input that cannot be checked by
  re-measuring.** 0.7.0 closed the part that could be: an artifact naming a different
  page is refused with the reason. What remains unverifiable is *when* — a trace from
  six months ago describing today's URL is accepted, because a timestamp in the file
  is the operator's claim too. The report says which verdicts came from a supplied
  measurement, so a reader can weigh it; nothing can make that automatic.
- **The page guard is fingerprint-based**, so an interstitial from a vendor it does
  not recognise still gets through. Deliberate: an unknown interstitial and a
  client-rendered shell are indistinguishable from the HTML, and the second is a
  real finding, so the run warns with the visible word count instead of refusing to
  score.
- **Client-facing reports are English-only.** `--lang ru` translates 45 of the
  report's 51 own strings and all 16 category explanations. The six it does not are
  the "what was audited" block — the caveats — and `item_titles` and `item_fixes` are
  empty, so item titles and recommendations come out in the registry's English. As of
  0.7.0 the stderr warning *counts* what is missing rather than asserting the chrome
  is complete, which is how those six were found; it had been claiming otherwise
  since the translation shipped.

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
