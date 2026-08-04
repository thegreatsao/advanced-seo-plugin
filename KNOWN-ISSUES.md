# Known issues

What is wrong with this plugin as of **0.8.0**, ranked by consequence, with the
evidence for each. Nothing here is a suspicion: every entry was measured against
the tree.

This file exists because the audit's one promise — that "we could not check this"
never reads as a verdict — applies to the plugin's own description of itself. A
defect known and unwritten is the same failure one level up.

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

That is **~275 fetches of the same pages per audit** on a site large enough to fill
those budgets, plus 36 more scripts each re-fetching the entry URL, with no shared
HTTP cache anywhere. At the default 4 rps/host that is over a minute of pure pacing,
and the audited site absorbs five crawls where one would do.

Measured rather than budgeted: the CI live step counts the requests its own server
receives, and **a seven-page fixture with `--sample 3` absorbs 181** — for a site
whose entire content is seven pages. The count is printed in the build log on every
run, so a change that makes it worse is visible here rather than only on somebody
else's server.

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

## 2. The tests prove a script's shape, not its thresholds

**Closed in 0.8.0**: all 55 evidence scripts have unit tests, 462 in total, and each
asserts *the field the registry actually reads*, named in the test. The count is not
the point — the yield is. Three releases of writing these found, in order: eighteen
assertions that had never fired, two items that failed sites for serving images the
recommended way, and then sixty-two items grading a site that refused every
connection. Roughly one defect per three tests, and the rate did not fall off.

Three layers now, each catching what the others cannot:

| Layer | What it proves |
|---|---|
| `test_evidence.py`, `test_evidence_scripts.py`, `test_evidence_apis.py` | a named field answers a named question, in both directions |
| `test_contract.py` — the good/broken pair | a check can tell two whole sites apart, or says in writing why it cannot |
| the dead-origin sweep | nothing is decided about a site that answered nothing |

What remains is not coverage but calibration. **A test can show that a threshold
fires; it cannot show the threshold is right.** MB-095 warns at 250 KB, CN-039 at 300
words, SP-216 at 200 ms of blocking time — those numbers came from Google's published
guidance and from the borrowed scripts, and no test here argues with them. A site
audited at the wrong threshold gets a confident verdict about the wrong question,
which is the failure this suite is worst at seeing.

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
