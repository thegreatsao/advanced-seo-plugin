# Changelog

`registry_version` in `checklist.json` tracks the audit contract — which items
exist and what each one asserts. It changes whenever the checklist changes, which
is not the same event as the plugin changing. This file tracks the plugin: the
runner, the report, the scripts and the run modes around that contract.

Versions are `MAJOR.MINOR.PATCH` before 1.0, where the minor is bumped for
anything that changes what a run produces — including a change that makes the
output *more* honest. A verdict that used to be `PASS` and is now `NO_DATA` is a
breaking change for whoever read the old number, and saying so is the point.

## 0.45.0 — four items measure the document they name, and a page is read in the charset it declares

CI-017 and TE-181 were the same *Validate HTML (W3C)* check twice: both asked Nu to
fetch the served URL and both asserted `summary.errors == 0`. TE-181 now POSTs a
rendered DOM to Nu instead, while CI-017 keeps validating the HTML the server sends.
Served markup and a script-mutated DOM are two different documents and either can be
valid while the other is not, so this is a genuinely second measurement.

The DOM comes from a rendered-page artifact — the one `rendered_audit.py` already
reads, with an added `html` key — and **not** from a browser launched inside the run.
That was tried first and the request-discipline step caught it: a browser fetches the
page and its subresources again behind the response cache, taking one audit of the
6-page fixture from 22 requests to 31 and asking for the entry URL three times. One
audited page, one fetch, is a property worth more than the convenience of rendering
in-line, and the measurement belongs outside the run exactly as `cwv_metrics.py`'s
trace does. Playwright therefore stays an optional dependency and CI installs no
browser.

The pair carries 6 weight points rather than the 3 it carried through `scores_with`.
This is not the double-charging rejected for MD-189: that conjunction would have
charged one missing-modern-format fact through two items, while CI-017 and TE-181
charge two independently observed documents. Without `--rendered-json` the item
reports `NEEDS_INPUT`; with an artifact that recorded measurements but no document it
reports `NO_DATA`. Neither passes a DOM nobody built.

TE-181 is now titled *Validate the Rendered DOM (W3C)* and its fix names validation
errors in that rendered document. CI-017's title, fix, arguments, assertion and
translations are unchanged.

A page served as bare `text/html` is no longer read in the wrong character set. `requests`
takes the charset from `Content-Type` and falls back to ISO-8859-1 when a `text/*` response
names none, so a site that sends bare `text/html` and lets `<meta charset="utf-8">` speak
for the page was decoded as latin-1: `—` arrived as `â\x80\x94`, and every title, heading,
description and word count downstream carried the damage. The shared HTTP path now lets the
document's own declaration decide **when, and only when, the server named no charset** — a
BOM, an XML declaration, or a `<meta>`, with comments skipped as a browser skips them. A
server that does name a charset still wins, because a document disagreeing with its server
is a site defect for an item to report rather than something to quietly correct. Character-set
*detection* is deliberately not consulted: a guess that silently rewrites a page's text is
the failure this project keeps paying for, so a document declaring nothing keeps the old
behaviour.

Nothing had caught this because nothing compared two readings of the same page. MB-105 began
to, one release after it stopped passing sites it had never rendered, and immediately found
two differences in a fixture built to have none — the browser had honoured the meta and we
had not. Sites whose servers do send `charset=` — including the audited one — were never
affected.

MD-189 *Use Modern Formats & Responsive Images* named two halves while asserting
only the modern-format count. Both halves were already measured separately: MB-096
reads the responsive-image count, and MB-097 reads the modern-format count.

MD-189 now takes the responsive half and defers to MB-096, whose title names that
shared assertion exactly. MB-097 comes off the old pointer and carries the
modern-format half itself. The three items still carry 6 weight points in total:
one medium responsive-image check and one medium modern-format check, with MD-189
reporting the shared responsive verdict without scoring it again.

The literal alternative — making MD-189 require both counts — was rejected because
it would raise the theme from 6 to 9 weight points and charge one missing-modern-format
fact twice, through both MD-189 and MB-097. `scores_with` deliberately requires an
exact shared check and cannot make a conjunction into a weightless aggregate.

KW-076 *Include the Primary Keyword in Body Copy* asserted a keyword that
`article_seo.py` extracted from the page itself, so any page with enough prose passed
and the item could never fail. The keyword is now an operator input supplied with
`--keyword`; without one, KW-076 reports `NEEDS_INPUT` and does not affect the score.
Its assertion now reads whether that supplied keyword occurs in the body copy, which
is what the title says. A measured absence is therefore a reachable `FAIL` for the
first time.

MB-105 *Ensure Parity: Content, Meta & Directives Match Desktop* used to emit an empty
`diffs` array when Playwright was unavailable, a browser failed or rendering timed out.
That empty array passed every site without a renderer even though the raw and rendered
documents had never been compared. `javascript_render_audit.py` now omits `diffs` when
no render happened, so MB-105 reports `NO_DATA` instead of claiming parity. Its
`diffs len_eq 0` assertion is unchanged: an actual matching render still passes and an
actual difference still fails. TE-169 and TE-177 are unaffected because they assert
the raw document, which is measured whether or not rendering succeeds.

Registry `715c6bb46461` replaces `2dd52fda3e6f`. The fixture oracle remains 98 matched,
0 disagreed and 10 indeterminate across 53 items and 108 declarations, with 42 opposed.
The 852-test baseline becomes 887, with the POSIX-only signal-naming test still the one
expected skip.

## 0.44.0 — the plugin runs on Windows, and two items measure what their titles promise

The runner now resolves its fetched `{html}` temporary files against the disk on
Windows instead of mistaking their backslash-separated paths for bare domains and
fetching them from the network. The shared HTTP lock no longer requires POSIX, and
`load_html` now prefers an existing file over a bare-domain spelling on every
platform. A `test-windows` CI job runs the eight portable gates on `windows-latest`,
which is how the drive-letter defect above was found: eight gates passed on a
single-drive developer machine while `os.path.relpath` raised on a runner that checks
out on `D:` with its temporary directory on `C:`.

TE-179 now asserts `whois.age_days >= 90`: an established domain passes, a younger
one warns, and a missing whois age remains `NO_DATA`. The `lt 90` warning band is the
assertion's exact complement, so FAIL is deliberately unreachable. The item no longer
needs a Safe Browsing credential; its script-level `api` requirement keeps it outside
the loopback-fixture oracle.

This explicitly reverses the TE-179 decision recorded in 0.21.0 without pretending
that decision was wrong on its facts. Age is still not reputation, and an unfixable
FAIL still does not belong in a prioritised fix list. The proposition is different:
SE-114, SE-116 and TE-171 assert reputation through Safe Browsing three times, while
none of the 215 items otherwise asserts domain history, and a WARN costs half of one
`low` point rather than the whole point a FAIL would cost.

This does not add an informational status or disturb GO-134's opportunities section.
Those opportunities are a list of findings with no item to attach to; domain age is a
single scalar with a row already named for it, and that row is the clearest place to
render the evidence.

MB-104 previously read only the favicon URL extracted by `parse_html.py`, so any
declaration passed even when the icon returned 404 or was only 16px. It now fetches the
declared icon and reads PNG, ICO, GIF, JPEG, WebP and SVG headers. A missing declaration,
an unreachable icon, or a measured raster shorter than 48px is a FAIL. A fetched but
unrecognised format is `NO_DATA`, because no size was measured; it does not invent a
small dimension. A resolvable SVG passes as a scalable vector.

That separate measurement removes MB-104 from TE-166's `scores_with` group. TE-166 keeps
the declaration check; MB-104 now carries weight 1 where the synonym pointer made it
carry 0. The item count, title, severity and fixture oracle do not change.

Registry `2dd52fda3e6f` replaces `843026f5d5dd`. The fixture oracle remains 98 matched,
0 disagreed and 10 indeterminate across 53 items and 108 declarations, with 42 opposed.
The 833-test Windows baseline becomes 852, with the POSIX-only signal-naming test still
the one expected skip.

## 0.43.0 — registry assertions measure the facts their titles name

KW-071 now reads the emitted `contested_queries` count instead of the deleted
`worst_spread` field, and grades it with a `lte 3` warn band. The band matters: the
rule it replaced was `worst_spread lte 3`, so the item already tolerated a little
before failing, and a bare `eq 0` would have made a `high` item fail on one contested
query without that being anyone's decision. MS-023 grades the broader
`cannibalized_queries` on the same script with `lte 3`, and a narrower signal should
not be stricter than the broader one.

MS-022 gets a case-insensitive, whitespace-normalized duplicate title count that skips
missing titles, leaving duplicate body content to CN-041.

The four Safe Browsing items now read one threats-list assertion and score it once,
with SE-114 as the primary. CI-013 discovers the audited page's same-origin CSS,
JavaScript and image references instead of testing three invented paths; a page with
no such asset remains undecided. Same-origin is an exact scheme, hostname and
effective-port match after URL resolution.

`image_inventory.py` no longer emits the unread
`lazy_lcp_performance_candidates` count. MD-185 retains the condition as the warning
`Likely LCP image is lazy-loaded` from `image_weight_audit.py`.

AR-158 now reads `breadcrumbs.schema` and `breadcrumbs.ui` from `parse_html.py` and
requires both. Parseable JSON-LD, Microdata and RDFa can establish the schema half;
the UI half accepts a breadcrumb-named nav landmark, class/id marker, or the
Microdata/RDFa trail itself. This is intentionally stricter about the two presences
the title names, while required-property validation remains MS-032's separate job.

TE-168 now passes only when the site-wide internal inventory has neither broken nor
redirecting targets. Redirects alone warn, one to three broken targets retain the
existing warning tolerance, and only a fourth broken target fails. Strictness moves
only for the previously unread “Redirected” half; the broken-link bands do not move.

CN-048 now emits structural `issues`: a skipped heading level and a missing `main`
landmark are errors. Its old H2 minimum is removed and CN-066 keeps the separate
two-H2 rule. Strictness moves in both directions to match “Hierarchical Headings and
Semantic HTML”: real structural defects now count, while a correctly structured
H1-only gallery no longer fails.

Absence of `nav` or `footer` is deliberately **not** a finding. Both were warnings in
the first cut of this rule, and that put the exemplary fixture into WARN over blog
pages with no footer — entirely ordinary pages. A page with no navigation correctly
has no `nav`, and penalising the absence measures page design rather than markup
semantics. `main` stays an error because every page has main content, so failing to
mark it is a real defect.

LO-198 is site-level. `site_crawl.py` inventory version 3 records the types of each
parseable JSON-LD node, and `local_seo_checker.py --inventory` asks whether at least
one crawled HTML page carries a LocalBusiness or subtype. This is less strict than
requiring repetition on every sampled page and broader than entry-only evidence;
LO-200 remains a separate per-page NAP/GBP/reviews judgement.

Registry `843026f5d5dd` replaces `07e64f9c9fc6` for the combined 0.43.0 release.
AR-158 good moves INDETERMINATE to FAIL, TE-168 broken moves INDETERMINATE to WARN,
and CN-048 good moves PASS to WARN. The 108 fixture declarations remain fully agreed:
98 matched, 0 disagreed and 10 indeterminate across 53 items, with 42 opposed. Batch
A's interim 814-test baseline becomes 823; the release-to-release baseline is 808 to
823.

## 0.42.0 — absent HSTS is a failure, not missing evidence

`security_headers.py` now emits an empty value for every tracked response header
that a successfully fetched page omits. SE-115 therefore fails an HTTPS page with
no Strict-Transport-Security header instead of reporting `NO_DATA`; a real fetch
failure still carries `error` and remains undecided.

The fixture oracle now serves both site trees over verified TLS as well as HTTP.
Its hardened TLS origin emits HSTS, CSP, Referrer-Policy, X-Content-Type-Options,
and Permissions-Policy, while its sparse origin omits all six tracked headers. A
direct crawler regression test also locks the 0.40.0 rule that a normalized page
key is never substituted for the discovered trailing-slash URL at fetch time.

Registry `07e64f9c9fc6` is unchanged. The 807-test baseline becomes 808.

## 0.41.0 — image verdicts distinguish absence, deferral and discoverability

MB-096 and MB-097 no longer fail an image-free sampled page. The image audit omits
`responsive_count` and `modern_format_count` when there is no image to assess, so
that page is undecided and pages that serve images determine whether the site uses
responsive and modern formats. Pages with old or non-responsive raster images still
emit zero and fail as before.

CN-054 now answers its title. Native `loading=lazy` with an ordinary `src`, `srcset`,
or `<picture>` source remains crawl-discoverable and passes; a JS-deferred
`data-src`/`data-srcset` image with no native source fails. Likely lazy-loaded LCP
images remain reported separately as a performance observation.

The fixture oracle triage settles five declarations, marks two fixtures
indeterminate, and defers AR-158 and TE-168 to registry decisions 1 and 2. All
remaining settled declarations now agree with the runner. Registry
`07e64f9c9fc6` is unchanged. The 803-test baseline becomes 806.

## 0.40.1 — sampled-page evidence names the full sample

Per-page aggregate evidence now keeps the sample size as its denominator when
some pages are undecided, and names how many were undecided. A five-page verdict
from an eight-page sample therefore reads `5/8 pages (3 undecided)` instead of
`5/5 pages`; fully decided samples retain their existing wording.

Verdicts and the structured `pages_checked`, `pages_decided`, and
`pages_matching` counters are unchanged. Registry `07e64f9c9fc6` is unchanged.

## 0.40.0 — crawl identity and keyword evidence describe what was observed

The shared crawler now keeps `page_key` solely as its deduplication, inbound-link
and orphan-bookkeeping key. It fetches the first URL spelling actually discovered
in a sitemap or link and reports that spelling in the page row and redirect list.
The root slash remains intact, and `/about` plus `/about/` still produce one page.
This removes the two internal redirects the crawler fabricated by changing the
site's `/en/` and `/ru/` links before requesting them.

An undetermined primary keyword is now absent from `article_seo.py` output instead
of present as an empty string, so KW-076 reads it as `NO_DATA` rather than `FAIL`.
This is an output-contract correction independent of which words are filtered.

Keyword extraction now selects curated English, Lithuanian or Russian stopwords
from the page's declared `<html lang>`, retains Unicode letters, and treats a
stopword as an n-gram boundary rather than splicing the words around it into a
phrase that never appeared. A new language belongs in its own list rather than a
global union.

In the fresh eight-page live rerun, all three gallery pages omit
`target_keyword`; `/bbq` and `/menu` both extract `molėtų rajone` ("in the Molėtai
district"). That is a meaningful local phrase rather than function words, but it
is not page-specific enough to be a strong inferred primary keyword. At aggregate
level KW-076 moves FAIL to PASS because five sampled pages provide a keyword and
the three absent values are undecided rather than failures.

The crawl remains 24 HTML pages with no broken or blocked pages. Redirected pages
fall from 2 to 0 and `redirected[]` becomes empty; every other summary field,
including `summary.requests = 27`, is unchanged. That counter records top-level
fetch calls rather than redirect hops, so the two eliminated HTTP hops do not make
the stored count fall. AR-149 moves WARN to PASS; CI-008, AR-162 and TE-168 remain
PASS. No other item moves. The score rises from 88 to 89 over the same 117 decided
items and the same 62% weight coverage (510/826).

Registry `07e64f9c9fc6` is unchanged: no checklist item, title, threshold or
assertion was edited. The 791-test baseline becomes 797.

## 0.39.0 — NAP identity and query evidence follow the measured business

NAP name comparison now keys business identity on equal normalized telephone,
equal normalized street and locality, or an explicit `@id` link in either
direction. A shared schema type, street without locality, and shared social
profile are not identity evidence. This restores the live page's two name
warnings while preserving the different-phone, different-address false-positive
guard introduced in 0.38.0.

The Search Console cannibalization artifact now retains every analyzed query with
its normalized brand form, complete classification inputs, exclusive bucket, and
bounded brand-match evidence. Classification is independent of the 25-entry
human-facing list caps. The evidence list is capped at 1,000 with every classified
query first and a `queries_truncated` flag; authentication failure still leaves
the evidence empty and the verdict undecided.

The eight-page live rerun retains all 243 queries without truncation: 8 are
`branded_spread`, 2 are cannibalized (including the 1 `contested` query), and
233 are `single_page`. `green valey` records `greenvalley` at edit distance 1.
The evidence artifact grows from 1,667,888 to 1,729,670 bytes (+61,782). NAP
findings grow from 2 to 4 and total entity issues from 8 to 10, but no checklist
item status, measure or evidence changes; the run remains 88/100 at 62% coverage
(510/826 weight). The 781-test baseline becomes 791.

Registry `07e64f9c9fc6` is unchanged: no checklist item, title, threshold or
assertion was edited.

## 0.38.0 — sampled evidence follows every graded page

`--evidence-json` now keeps each sampled page's complete script output under a
top-level `pages` mapping while leaving the entry-page script mapping unchanged.
A skipped sampled page remains present with its skip reason, and a non-sampled run
omits `pages`. Before this release, an aggregate such as “3/8 pages” preserved only
the entry page's evidence: a reader could neither identify the three pages nor
verify what the other five scripts reported. Redaction now covers both levels.

NAP comparison now separates shared premises from shared identity. Address and
telephone still compare across every local node, while names compare only across a
shared type or identity; distinct node identifiers take precedence over shared
profile links. Two cross-type name warnings disappear from the live shape and its
two real `addressLocality` warnings remain. The old four-warning list trained a
reader to skim the noise and made the address mismatch easier to miss.

Owned-brand query classification now accepts bounded spelling mistakes after the
same case, diacritic and spacing normalization as exact matches. Terms below five
characters never near-match; terms below ten permit one edit and longer terms two,
against both the whole query and its words. In the eleven-query live shape, the
one-edit brand misspelling moves from `cannibalized` to `branded_spread`:
`cannibalized_queries` falls from 3 to 2 and `contested_queries` from 2 to 1 because
the misspelling was itself one of the close contests. MS-023 remains WARN because
both 3 and 2 are inside its unchanged warn band; no evidence-driven status moves.

The comparable unmerged rerun remains 88/100 at 62% coverage (510/826 weight).
The saved prior result has twelve merged model answers, so a literal diff
returns AR-159, CN-049, CN-064, IN-130, KW-072, KW-075, LO-196, LO-197, MS-025,
MS-027 and TE-165 from PASS to LLM_PENDING and MS-024 from WARN to LLM_PENDING;
those are missing model inputs, not evidence changes. The complete evidence artifact
grows from 305,515 to 1,667,888 bytes for eight pages, while the new result is
157,758 bytes. The 1.7 MB evidence file remains practical as one JSON artifact and
is deliberately neither truncated nor summarized.

Registry `07e64f9c9fc6` is unchanged: no checklist item, title, threshold or assertion
was edited. All three regression families were observed failing against b648b33
before their repairs; 769 baseline tests become 781.

## 0.37.0 — the second live audit keeps the evidence it exposed

Runs can now write every evidence script's parsed output with `--evidence-json`;
`checklist-results.json` names that file without embedding it, and a run that omits
the flag says that its scalar measures are not the full evidence. Before this release,
an owner receiving CI-017's two errors or MS-023's query count could not recover which
errors or queries produced the verdict from the audit artifacts.

MinHash shingles now use Python's Unicode word definition and empty text is explicitly
not comparable. Russian pages about different subjects no longer become 100% duplicates
because only their Latin-script footer survived, and Lithuanian diacritics no longer
splice non-consecutive words together. The 0.85 threshold itself is unchanged.

Entity and local-SEO checks now share one LocalBusiness subtype hierarchy and accept
list-valued `@type`. A `Restaurant` is local; a `TouristAttraction` is a Place that may
participate in NAP comparison but does not answer LocalBusiness questions. Structured
`PostalAddress` comes before visible-text comparison, so non-English addresses are no
longer declared absent by an English street-name regex. Multiple local schema nodes now
surface normalized name, telephone and address disagreements, including the live-site
`addressLocality` split that the old "NAP consistency" function never compared.

Search Console brand spreads move out of the cannibalization failure count when the
homepage owns the inferred brand, and hreflang alternates count as one logical page.
Raw rank `spread` remains on each query but no longer carries a failing direction;
close non-brand competition is reported separately as `contested_queries`. KW-071 is
therefore `NO_DATA` until its keyword-overuse registry wording is reconciled with SERP
evidence, recorded in KNOWN-ISSUES rather than hidden behind a backwards threshold.

Sampled issue measures now apply the same severity aliases as their verdicts. The old
report could put “No critical/high/medium issues reported” beside a WARN whose evidence
named exactly such an issue; it now carries the issue count and sample from that same
worst page. A runtime guard refuses every sampled WARN/FAIL whose rendered measure says
the assertion passed, across `issues`, `count`, `number` and `matches` measures.

The exact Task 9 rerun changes MS-023 FAIL -> WARN: 11 reported splits become
three after seven owned brand spreads move aside and locale alternates collapse.
KW-071 changes FAIL -> NO_DATA because its unchanged registry path no longer exists.
Eleven PASS model answers and one WARN model answer from the saved 11 August artifact
return to LLM_PENDING because the required runner command queues no model review; those
twelve movements are missing inputs, not evidence repairs. No other status changes.

The raw comparison moves 87/100 at 67% (550/826 weight) to 88/100 at 62%
(510/826). Coverage does not rise. The only old near-duplicate pair,
`/ru/blueberries` against `/ru/petting-zoo`, moves from 1.0 to 0.1 and is the only
pair crossing 0.85; the threshold stays 0.85. `checklist-results.json` is 157,758
bytes and the complete `checklist-evidence.json` is 305,195 bytes. The evidence file
is larger by design and is not trimmed: the old, smaller result could not identify
the errors, queries, duplicate pair or NAP findings behind its scalar counts.

Registry `07e64f9c9fc6` is unchanged: no checklist item, title, threshold or assertion
was edited. Every regression was observed failing against 8d47729 before its repair.

## 0.36.0 — the default locale's whole unprefixed route tree

IN-127 changes FAIL -> PASS for every site whose default locale is unprefixed while
its other locales use same-host subdirectories. The compatibility rule now compares
normalized paths: an unreadable alternate is compatible only when its path equals a
readable alternate's path after removing that readable alternate's locale prefix.
Trailing slashes are equivalent and query strings do not participate in the comparison.

The rule does not accept any unmarked same-host path. The deliberate 0.33.0 mixed case
is preserved: `/about` beside `/fr/` remains FAIL because the prefix-stripped readable
route is `/`. An unreadable URL under another locale's prefix remains mixed as well;
the implementation never strips the unreadable path itself.

The live-site rerun changes IN-127 from FAIL on 7/8 pages to PASS on 8/8,
with structure `subdirectory`. No other item verdict moves. Score remains 86/100 and
coverage remains 62% (516/826 applicable weight) against the 0.35.0 `-after` run.
Registry `07e64f9c9fc6` is unchanged: this release repairs evidence interpretation, not
the checklist contract. 740 -> 742 tests, with the inner-route regression observed
failing before the implementation and the 0.33.0 guard kept green.

## 0.35.0 — seven defects exposed by one live multilingual audit

All seven defects were found by auditing one live trilingual local-business site on a matching-language ccTLD, not by a fixture.
None is theoretically impossible to encode in a purpose-built regression fixture;
the existing static, English-first fixtures could not expose a matching-language
ccTLD, differing values across a multilingual sample, a JavaScript-populated
src-less lightbox placeholder, or non-English navigation whose contact route was a
phone link. The regressions added here make those live shapes permanent test cases.

Verdicts change in both directions. IN-127 changes FAIL -> PASS for the reproduced
root set — a default locale at the root of its matching ccTLD with other locales in
same-host subdirectories — and real cross-host mixtures remain FAIL. The live rerun
contradicted the predicted aggregate PASS: seven inner-page sets still fail because
their unmarked default-locale URLs, such as `/bbq`, are not bare roots. The specified
repair deliberately leaves that older compatibility rule unchanged; KNOWN-ISSUES §6
records the remaining false failure. CI-016 and its MD-186 twin change FAIL -> PASS
for a src-less lightbox placeholder and correctly preserve `alt=""` as an explicit
decorative alternative. CN-044 changes FAIL -> PASS when a page exposes a `tel:` or
`mailto:` contact route regardless of link language.

MB-102 and its scoring primary MD-190 change PASS -> N/A when
`video_schema_checker.py` reports its real `videos = 0` field. This restores the
registry's founding rule that an empty result set is not a clean measurement. Both
twins report N/A together and leave the score together; their `SAME_CHECK` declaration
still carries video SEO's weight once. SE-114, SE-116, TE-171 and TE-179 change
NO_DATA -> NEEDS_INPUT when network is available but neither
`GOOGLE_SAFE_BROWSING_KEY` nor `SAFE_BROWSING_API_KEY` is set. In archive mode they
are N/A; TE-167 and TE-178 still run without a key.

IN-122 remains PASS on the audited site but now runs `--verify-returns` automatically
in live and page modes, never archive mode, so its evidence proves the return-tag work
happened. Sampled evidence keeps its verdicts and counts while naming the page whose
value it prints and appending “values differ” when the matching rows disagree; this
fixes both MS-020's three title lengths and PASS rows such as IN-123's three languages.
The institutional word list remains English-only beyond language-neutral phone and
email routes, and KNOWN-ISSUES §6 states what a proper multilingual repair requires.
The like-for-like machine-only live comparison moved score 84 -> 86 and coverage
63% -> 62%; coverage did not rise when the video twin pair left both numerator and
denominator, and its primary MD-190 removed one medium-severity weight, not two items'
weight. The literal saved artifacts are 84/77% before and 86/62% after because the
before artifact contains 38 model answers and Task 8 deliberately queued none.

Registry `27003b24ce60` -> `07e64f9c9fc6`: four Safe Browsing requirements, two
video applicability rules and IN-122's verified-return assertion change; titles,
fixes, severities and thresholds do not. 719 -> 740 tests, with each defect's
regression observed failing before its fix.

## 0.34.0 — CI-002 promises exactly what its evidence answers

This defect was found and written by an earlier pass whose release was never landed,
rescued from its reading copy, and held back once because another session held
`audit_item_semantics.py`. It is re-derived here against the current tree; the old
patch was read for intent and never applied.

**CI-002 no longer turns one inspected URL into a claim about a site's important
content.** Since 0.26.0 it has asserted Google's URL Inspection `indexed` answer, but
`requires: gsc` keeps the item out of the per-page sampled pass: one audited URL is
inspected once. The inherited title *Ensure Important Content Is Indexed* survived
that repair for eight releases and promised a scope the evidence cannot answer. A
declared, reasoned override now titles it *Confirm Google Has Indexed the Audited
URL*, while `plerdy-titles.json` stays faithful to the source checklist.

The rescued draft proposed *Ensure the Audited URL Is Indexed*. This release departs
from it deliberately: CI-001 is already *Ensure URL Is Indexed* and asks whether the
page can be indexed from this plugin's crawl, while CI-002 asks whether Google has
indexed it. Putting those two titles one word apart would obscure two different
instruments and allow their verdicts to look contradictory. The override loader also
refuses unknown ids, plugin-owned items, blank titles or reasons, and titles that
merely repeat their source; metadata keys never reach the generator. The shipped-title
regression was observed failing before the registry was regenerated.

The Russian catalogue now names Google's evidence and remains distinct from CI-001.
The semantics audit records CI-002's narrowed scope, corrects IN-127's stale account
of mixed URL structures, and prints its inert historical rulings as information rather
than a gate. Important-URL inspection remains open: it needs a policy for the 2,000
daily inspections per property, selection rules and aggregation.

Registry `03fb71754eb2` -> `27003b24ce60`: CI-002's title is the only item field that
changes; 215 items remain, with no assertion, severity, score weight or verdict
change. 716 -> 719 tests.

## 0.33.1 — the gate reads an item's subject, never its side of it

Written in a parallel session and tagged `v0.32.1` from a commit that never reached
`main` — both releases branched from `0.32.0` and only one push won the race. Nothing
was lost: the tag still points at the original commit, and this is its content,
cherry-picked on top of `0.33.0` and renumbered to match where it actually lands.

**`audit_item_semantics.py` cannot tell a title that states the desired state from one
that states the failure.** It asks whether an item asserts about what its title names.
It has never asked whether a PASS means what the title says, and the two answers come
apart when the title is phrased as the defect: the subject matches, the verdict
inverts, and the item reports the opposite of what it found.

GEO-008 was drafted that way inside 0.32.0 — *"This page or marked text is restricted
in Google AI answers and result snippets together"* over `snippet_controls.restricted`
`falsy: true`, so it passed exactly when the page was not restricted. The vocabulary
check was satisfied by the very word that made the title wrong. Corrected by hand
before it landed; the other 214 titles state the desired state.

The heuristic for catching it — a title should not repeat the last segment of a path
the assertion requires to be absent or bounded — was written and measured against the
registry, and is **not** shipped. 23 of 215 titles fire and all 23 are correct, because
naming the defect is what a remediation title does. Only 74 items assert a
negative-polarity path at all, a 34.4% ceiling, and inside it the rule catches one of
four plausible phrasings of GEO-008's own defect. KNOWN-ISSUES §6 records the numbers,
the refinement that gets false positives down to two and why its verb list is fitted to
the corpus it was tuned on, and states plainly that no reliable check exists.

Documentation only. No script, registry, assertion or verdict changes: registry stays
`03fb71754eb2` at 215 items, and a run produces exactly what 0.32.0 produced. 712 tests,
ruff, five registry gates and four calibration checks green.

## 0.33.0 — unreadable evidence can no longer award a clean result

These defects were found and written by an earlier pass whose release was never
landed, and are rescued here from the reading copy after being re-derived against the
current tree.

**Every test file now runs when invoked directly.** The AST guard checked that an
existing `unittest.main()` came last but never required one to exist.
`test_evidence_apis.py` and `test_evidence_scripts.py` consequently exited 0 after
running none of the 17 and 128 tests they defined. The strengthened guard first failed
naming both files; final main blocks now run 18 and 128 tests respectively, including
the URL Inspection regression below.

**IN-127 no longer discards the alternate that disproves its URL-structure verdict.**
An unreadable alternate such as `en-GB -> example.uk/` is compatible with a host-based
scheme, or with a subdirectory scheme only when it is the bare default root on the
same host. Otherwise the set is `mixed`, and the finding names the incompatible URL.
This deliberately changes contradictory sets that previously returned IN-127 `PASS`
as `subdirectory` to `FAIL` as `mixed`.

**The standalone URL Inspection command no longer crashes when Google supplies no
canonical pair.** `analyze()` deliberately omits `canonical_match` in that case, but
the text renderer indexed the optional key and raised `KeyError`. The renderer now
prints `unknown`; the JSON path remains unchanged.

Registry `03fb71754eb2` unchanged at 215 items. 712 -> 716 tests.

## 0.32.0 — ordinary snippet directives govern Google's AI answers too

**GEO-008 checks the only documented control over whether page content appears in
Google's AI answers.** Each indexability row now reports `nosnippet` from `robots` and
`googlebot` meta tags or `X-Robots-Tag`, the effective `max-snippet` integer with every
source that supplied it, and the number of `data-nosnippet` attributes in the HTML.
`max-snippet:-1` is unlimited and passes; `max-snippet:0` suppresses the snippet and
warns. When sources disagree, the smallest non-negative limit wins, so an unlimited
directive cannot erase a restriction from another source.

The new item states the coupling the setting creates: the same directive restricts a
page or marked passage in Google's AI answers and in its ordinary result snippet, and
Google provides no setting that separates the two. A restriction is a legitimate
editorial choice, so GEO-008 uses the registry's `warn` branch. Clean pages `PASS` and
every detected restriction is `WARN`; the item cannot return `FAIL`. Live response
fixtures cover meta and header delivery, `-1`, `0`, `data-nosnippet`, a clean page and
the complete no-`FAIL` contract.

CI-004 is retitled from *Allow Indexing via Meta Robots / X-Robots-Tag* to *Allow
Indexing via Meta Robots*, matching the saved HTML that `parse_html.py` actually reads.
It does not fetch the page a second time to recover headers. `X-Robots-Tag: noindex`
continues to be fetched and enforced by `indexability_matrix.py` under CI-001, including
the existing header-specific evidence test.

Registry `f7dc6c5d1f5b` -> `03fb71754eb2`; 214 -> 215 items. 705 -> 712 tests.

## 0.31.0 — Google-Extended is not an AI Overviews control

**This is the same defect 0.29.0 fixed for OpenAI, repeated across three vendors.**
The AI crawler matrix treated one robots.txt token as a vendor's whole AI policy. Every
row now carries a machine-readable scope separating model training, answer retrieval
and ad landing-page review. `Google-Extended` is classified with model training: it
governs Gemini training and grounding in Gemini Apps and Vertex AI, and it is not an
HTTP user-agent.

Anthropic documents three independent tokens. `ClaudeBot` is now correctly classified
as training collection; `Claude-User` handles user-requested retrieval; and
`Claude-SearchBot` crawls to improve search answers. Perplexity likewise separates
search indexing under `PerplexityBot` from user-requested retrieval under
`Perplexity-User`. The latter generally ignores robots.txt, so each row now says
whether its token honours robots.txt and its policy is reported as `not_enforced`
instead of confidently claiming that a declared restriction will be obeyed.

Apple's documentation puts `Applebot` on both sides of the old boundary: it crawls for
Spotlight, Siri and Safari, and that data may also provide current context for
AI-generated answers. It is included as answer feeding for that reason. `nosnippet`
controls answer use, while the non-crawling `Applebot-Extended` token controls training
use.

**No robots.txt token controls AI Overviews or AI Mode.** Those Search features follow
`Googlebot` access and the ordinary snippet directives. GEO-003's English and Russian
remediation now says so instead of implying that a `Google-Extended` rule settles the
question, and now names the Anthropic, Perplexity and Apple splits. The assertion and
item set are unchanged; this release corrects the claims and expands the matrix output
contract rather than adding a new check. Registry `666f511a91ad` -> `f7dc6c5d1f5b`.
699 -> 705 tests.

## 0.30.1 — nine GSC thresholds get a written refusal

Nine inherited Search Console thresholds now name the evidence that is missing rather
than implying that an unexamined number merely awaits more of the same data. The pilot
is one small property, roughly ten thousand impressions over sixteen months. Its
CTR-by-position curve is non-monotonic, only five queries reach the bucket needed to
study the striking-distance average-position floor, and Search Console performance
data cannot calibrate either backlink concentration or a high-versus-medium severity
choice. The refusal is grouped by what could settle each family: many properties across
markets for six ranking and CTR claims, query-level mean-position variation for the
striking-distance sample floor, backlink evidence for concentration, and an explicit
product convention for severity. More months from one property cannot substitute for
the missing cross-market sample. No query, URL, page path, property or client identity
is committed.

Two other inherited floors are statistical questions and keep their values with a
measured basis. For a binomial CTR proportion, this release requires the 95% confidence
interval half-width at the tested CTR threshold to be no larger than that threshold.
At 5%, the minimum is 73 impressions and `LOW_CTR_MIN_IMPRESSIONS = 100` has 27
impressions of headroom, delivering +/-4.271721 percentage points. At 2%, the minimum
is 189 and `HIGH_IMPRESSIONS = 200` has 11 impressions of headroom, delivering
+/-1.940301 points. The offline calibration tool and committed report rederive those
figures and show the same half-width arithmetic at 10, 50, 100, 200, 500 and 1,000
impressions, including the uncalibrated 50- and 10-impression floors for context.

No threshold value and no verdict changes. Threshold inventory: 11 measured, 59
inherited, 117 verdict thresholds total. Registry `666f511a91ad` unchanged.
697 -> 699 tests.

## 0.30.0 — SERP character limits admit that truncation is pixels

`META_MAX_CHARS` moves from 165 to the measured Arial desktop capacity of 144.
This deliberately changes verdicts: descriptions from 145 through 165 characters
now warn where they passed before. The title ceiling stays 65; at the declared
ordinary-title-case mix 65 characters measure 591.37px and 66 measure 600.47px
against the assumed 600px desktop budget. At the same mix, 144 description characters
measure 917.08px and 145 measure 923.44px against the assumed 920px desktop budget.
Advice now names the exact enforced 30-65 title and 100-144 description ranges, so a
passing 35-character title is no longer simultaneously told to expand to 50 and no
description advice names 155.

Both ceilings use one selection rule: ordinary composition in Arial, chosen as the
representative mix rather than the most favourable one. Arial's all-caps, ordinary and
lowercase-heavy mixes would respectively hold 45, 65 and 67 title characters, and 98,
144 and 147 description characters. Selecting the most favourable mix consistently
would therefore have produced 67 and 147 instead. The committed report records those
alternatives and the ordinary-mix result in every sensitivity font, so the choice can
be audited without rerunning the font measurement.

The committed report measures four real font files, records their hashes, and crosses
three composition mixes with desktop-title, desktop-description and mobile-description
surfaces. Arial is bracketed by wider Verdana and narrower Times New Roman: title
capacity spans 57-72 and desktop-description capacity 126-158 across the four fonts
under the selected ordinary mix. Verdana holds about 126 ordinary-composition
description characters, so a lower-capacity rendering font than Arial would make even
the corrected 144-character bound permissive.
That spread is the result, not noise hidden behind one average. At 20px Arial's
narrowest ASCII letter (`i`, 4.443px) and widest (`W`, 18.877px) differ 4.25x, and
60 frequency-weighted capitals occupy 798.92px. A character ceiling is consequently
useful for the declared average text and cannot be exact for every title.

The 600px desktop-title, 920px desktop-description and 680px mobile-description
budgets are explicitly assumed third-party observations, not Google-published facts;
Arial is explicitly a stand-in for Google's own rendering family. If either input is
wrong, its derived character capacity is wrong. The two minimums therefore become
`convention`, not `measured`: a truncation budget says nothing about how much copy is
editorially enough, so 30 and 100 remain disclosed project judgements.

The full font run supersedes the pilot's approximations. It gets 591.37px rather than
about 596px for the 65-character title mix. Under the selected ordinary mix it holds
144 desktop and 106 mobile description characters; the pilot's lowercase-heavy
comparison measures 147 and 109 rather than about 146 and 108. In the selected mix the
old 165 description characters measure 1,050.82px (14.22% over budget), and the old
155-character advice still fails at 987.13px (7.30% over). The full all-caps mix is
798.92px for 60 characters rather than about 794px, and its lowercase-heavy
52-character counterpart is 463.30px rather than the pilot's roughly 402px. The full
run remains the source of both selected ceilings: 65 and 144. `fonttools` is
development-only and no audit imports it. Registry `666f511a91ad` unchanged.
693 -> 697 tests.

## 0.29.1 — the 100KB font warning gets evidence, not a new value

`LARGE_FONT_BYTES` remains 100,000 after measurement against 3,241 font files from
eight pinned npm packages. The corpus separates 3,214 `@fontsource` WOFF2/WOFF files
from 27 full `@expo-google-fonts` TTF faces, records every tarball hash and file label,
and leaves a wide observed gap: ordinary subsetted files end at 66,856 bytes and full
TTFs begin at 309,828. The threshold's exact location inside that gap is indifferent
on this corpus, so changing it would add precision without changing an answer.

The old rationale was half wrong: **100KB does not detect a non-WOFF2 face.** The 150
Latin/latin-ext WOFF controls have a 17,352-byte median and 47,440-byte maximum, with
none crossing the threshold; `font_audit.py`'s separate extension check is the format
signal. Their paired WOFF2 population has an 18,656-byte median and 34,520-byte maximum,
confirming the other half of the rationale with 2.9x headroom at the ceiling.

All 27 full TTFs cross: Inter spans 309,828-316,716 bytes and Noto Sans spans
401,372-561,488. The full run contradicts the pilot's Inter comparison: the required
Latin-plus-latin-ext Inter WOFF2 distribution has a 28,094-byte median, making the
median-to-median gap 11.2x rather than about 17x. It also moves the pilot's claimed
47KB-310KB empty band's lower endpoint to 66,856 because an ordinary CJK WOFF control
reaches that size. Nine of the 1,125 Noto Sans JP WOFF2 files cross, exactly the
un-ranged `japanese` fallback at each weight rather than any of its 120 numbered
unicode-range subsets, with a maximum of 1,158,688 bytes; the WOFF control repeats
those nine crossings and reaches 1,605,444 bytes. Registry `666f511a91ad` unchanged.
691 -> 693 tests.

## 0.29.0 — OpenAI's four crawler tokens, not one

**GEO-003 was checking one OpenAI token out of four and calling the answer a policy.**
`GPTBot` trains, `OAI-SearchBot` and `ChatGPT-User` answer, and `OAI-AdsBot` fetches the
landing page of a ChatGPT ad; they are separate robots.txt tokens and blocking one does
not block the others. A site that disallowed `OAI-SearchBot` while allowing `GPTBot` had
its AI-search visibility cut off and passed, because the matrix never asked. All four are
now in `ai_crawler_policy_matrix.py`, `robots_checker.py` and `robots_path_tester.py`,
and GEO-003's remediation names them. **This deliberately changes some GEO-003 verdicts**,
in both directions: a site that declared only `GPTBot` no longer speaks for the rest.

`OAI-AdsBot` is the one that is not an SEO check at all. Disallowing it does not cost a
ranking — it gets the site's ChatGPT ads **rejected at review**, a failure no other item
here surfaces and one that reads as an unexplained approval problem in a tool nobody
would think to point at robots.txt. It is checked where robots.txt is read and
deliberately **excluded** from `server_log_audit.py`'s `AI_BOTS`, on the reasoning that
file already applies to `AdsBot-Google`: its visits measure ad review, not reach, and
folding them into an AI-crawler count would inflate a number read as visibility.

Registry `18948c09ef94` -> `666f511a91ad`; the Russian GEO-003 fix was re-read and
re-stamped. 691 tests, unchanged.

## 0.28.1 — four thresholds carry the right kind

Four existing thresholds are **relabelled, not measured**; no value changes and no
verdict moves. `SEVERITY_ORDER` is `presentation`, because all thirteen uses order
complete report or export collections after their verdicts exist. The 70, 50 and 30
Flesch Reading Ease boundaries are `standard`, with the 1948 primary source named on
each declaration; the script's three-way grouping and audience wording remain its own.

Two other candidates were considered and rejected. `SEVERITY_WEIGHT` and `EFFORT_COST`
stay `inherited`: `tools/audit_score_sensitivity.py` establishes that they *matter*, not
that they are *right*, while `measured` means calibrated against something. The
inventory is now standard 9, measured 6, convention 36, inherited 66 and presentation
13: 117 verdict-affecting numbers in all. Registry `18948c09ef94` unchanged. 690 -> 691
tests.

## 0.28.0 — CSS minification gets the first measured threshold family

The five CSS-minification constants and the unnamed multiplier behind
`wasted_bytes` are now measured against 527 labelled CSS files and 173 exact
source/minified pairs from 19 pinned npm packages. The committed report records every
tarball hash, package-relative observation, split signal distribution, pair saving and
gzip result; the calibration tool can reproduce it from the network or compare it with
the live constants entirely offline. Tests bind all six constants to that artifact and
validate its dated, hashed manifest and all six `basis: measured` declarations.

The two corpus groups are deliberate. Generated Sass/PostCSS source clusters much more
tightly than authored CSS, so build output alone would teach the classifier that normal
hand-written stylesheets are minified. The full corpus keeps 180 bytes/line, 8% comments,
20 indented lines, the 20KB warning and the 2KB small-file cutoff. It also says what
those values do less well than their old comments claimed: comments change only two
classifications and both are false negatives; 20 is arbitrary in a broad equivalent
indent band; and the sub-2KB population is 170 files from only five packages, led by
98 `animate.css` animation fragments and 41 `tachyons` source partials. Those packaging
conventions do not establish a general property of small stylesheets.

The package-weighted paired estimate contradicts the inherited 20-30% saving claim: the
median of per-package medians is 18.918%, so the estimate moves from 0.25 to 0.189.
Package weighting matters because `@picocss/pico` supplies 119 of 173 pairs through
closely related variants; the pooled file median is 10.773%, effectively that one build
pipeline's median. Keeping pico but giving each package one equal-weight observation
fixes the pseudo-replication without shrinking the corpus. The change moves when
`wasted_bytes` crosses the medium finding and requires a minor release. The full corpus
also contradicts three pilot predictions: two source-labelled one-line files exceed
180 bytes/line, gzip retains 10.824% of aggregate savings (the median of package medians
is 7.188% and the pooled pair median 14.402%, not the pilot's 3.2%-8.5%), and the
package-weighted paired estimate differs from the pilot's ~16.5%. The line-wrapped
Bulma false negative and the uncompressed meaning of `wasted_bytes` are recorded in
[KNOWN-ISSUES.md](KNOWN-ISSUES.md).

The threshold inventory now recognizes named multiplicative estimates, closing the
blind spot that hid the old bare `0.25`. This makes the honest total 118 rather than the
handoff's arithmetically impossible predicted 117: standard 6, measured 6, convention
36, inherited 70, presentation 12. The other 70 inherited thresholds are untouched.
Registry `18948c09ef94` unchanged. 686 -> 690 tests.

## 0.27.2 — the one kind of threshold that is evidence now has to prove it

`basis: measured` no longer passes by carrying arbitrary prose. Its comment must name
the corpus, measurement date and method, and the date must be a real `YYYY-MM-DD` date.
The gate explains the exact form to write and reports the source line and malformed
field; it does not change a threshold or claim that one has been measured.

A `basis:` marker whose kind is absent or outside the documented five now fails the
same CI audit instead of disappearing from its inventory. The three existing
`external standard` markers turned out not to annotate numeric thresholds at all: two
described Search Console severity strings and one cited URL-structure guidance in a
function docstring. Their prose remains, without the threshold-only marker.

The inventory is unchanged: standard 6, measured 0, convention 36, inherited 75,
presentation 12. Registry `18948c09ef94` unchanged. 683 -> 686 tests.

## 0.27.1 — five helpers become three, and two of the four "duplicates" were not

**Three drifted `fetch_html` functions and three identical JSON walkers made one
change mean six edits, while the audit that found them overstated two other
duplicates.** `seo_common.fetch_html` now owns the guarded request and returns the
body with its post-redirect URL. The two callers that used to return only the body
drop the URL explicitly, and the hreflang caller keeps its old 10-second default and
silent failures with `quiet=True`; consolidation does not change any caller's timeout
or stderr contract. The three byte-for-byte `_walk_json` recursions are now the public
`seo_common.walk_json`, and a structural test rejects another script-local copy of
either helper.

`hreflang_checker.fetch_robots_txt` was not a second implementation of the live
`robots_checker` function. It had no caller and returned a bare string; the live
function returns the nine-key robots audit dictionary, and `seo_common.fetch_robots`
has a third contract again. The dead function is deleted and `robots_checker` is
unchanged rather than folded into a helper that would alter its output shape.

`checklist_runner.html_parser` was not a second parser decision either. It is the
lazy, defensive wrapper around `seo_common.html_parser` that keeps archive mode
importable without optional parser dependencies. The wrapper remains, and a test now
proves an unimportable `seo_common` costs the artifact its parser label rather than
costing the run.

**Two shared decisions still had two homes after the first pass.** The byte-identical
`_is_url` functions are now `seo_common.is_url`, and the two spellings of `as_list`
are now `seo_common.as_list`; both callers keep their existing behaviour for files,
URLs and JSON-LD scalars. The structural gate now rejects all six public and
formerly-private spellings of the four shared helpers it protects.

**`seo_common` called itself a bag of small helpers rather than the scripts' public
API, so copying one looked as legitimate as importing it.** Its module contract now
states the one-copy rule, groups the shared surface, and explains the flat and
package-compatible import forms that the scripts need in their two execution modes.

The runner's argument surface, mode decision, Search Console gate and console report
now sit in `build_parser`, `resolve_mode`, `resolve_gsc` and `print_report`. Registry
loading stays in `main`: the proposed two-value extraction overlooked two live outputs,
the registry schema version and normalized `--only` categories, and hiding either in a
side effect would make the calling convention less honest rather than more readable.
The entry fetch, profile, artifact, crawl and payload blocks still thread their state
into one another and remain together deliberately.

Registry `18948c09ef94` unchanged. Archive-mode artifacts are identical after removing
run timestamps; every one of the 214 item `id`/`status` pairs is identical. 681 -> 683
tests.

## 0.27.0 — 8 August 2026

**The SSRF guard reached 54 of the 55 scripts, and the one it missed is the one that
opens its own socket.** `checklist_runner` states the rule in a comment beside the
switch that carries it: "55 scripts in 55 processes each call `assert_safe_url` for
themselves, so the allowance has to travel with them." `tls_certificate.py` did not.
It needs the handshake rather than a response body, so it never fetches through
`safe_get` — and `safe_get` is where every other script picks the guard up. It took a
host and a port straight from argv and handed them to `socket.create_connection`.

**What that meant in practice: `--allow-private` was not a switch this script had.**
An audit that had not been given the flag could still reach `127.0.0.1`, an RFC 1918
staging box, or `169.254.169.254` — the cloud instance metadata address that is blocked
even *with* the allowance, because link-local is deliberately absent from
`PRIVATE_ALLOWED_NETWORKS`. Nothing showed it. The script returned a well-formed result
either way, which is the shape every defect in this file has.

`assert_safe_url` is now called once before the first handshake, which covers both
passes. A blocked address returns without `valid` — **NO_DATA to SE-118, not
`valid: False`** — because "we were not allowed to look" and "we looked and the
certificate is bad" are different claims and only the second is a fact about the site.
Importing `safe_http` costs this script nothing: `requests` is optional inside it and
`assert_safe_url` reaches only `socket` and `ipaddress`, so the file keeps the
stdlib-only property that lets it run where `requests` is not installed.

Two tests, both directions, in the pattern `test_runner.PrivateAddresses` set: loopback
refused when the run was not given the allowance, and the metadata address refused when
it was. Both were confirmed to fail with the guard removed — the second by spending
fifteen seconds timing out against 169.254.169.254, which is the defect demonstrating
itself.

**`_load_source` was copied into eleven scripts, and the copies had drifted into two
versions — one of them wrong.** Six tested `Path(source).is_file()`; five tested
`os.path.exists(source)`, which is also true of a directory, so those five raised
`IsADirectoryError` on an archive directory instead of falling through to `load_html`.
Eleven copies of five lines is how one defect gets to live in five files and not in the
other six. It is now `seo_common.load_source`, on the `is_file` reading, and the scripts
import it.

**`script-output-shapes.md` documented seven scripts that do not exist.** Four had full
output-shape sections — `product_schema_checker.py`, `review_schema_checker.py`,
`readability.py`, `x_robots_header_checker.py` — and three more were listed in the
"scripts needing extra required args" table. The `readability.py` section described
`has_loop` and `has_mixed_protocol`, which are `redirect_checker`'s fields: the section
was not merely stale, it was wrong about a script that was not there.

`audit_assertions.py` never caught this because it audits paths only for scripts the
registry names, and a section nothing points at is checked by nobody — the same blind
spot 0.8.0's hand-maintained sweep had. Removed; 63 sections down to 59, which is what
is on disk. The gate now checks both directions: every `### <script>.py` here exists,
and every script the registry or runner names has a section. A second gate checks that
every script which can open a connection reaches the private-network guard, and that
its written exemption list has no stale entries.

Registry `18948c09ef94` unchanged: no item added, removed, re-pointed or re-graded. This
release changes how three scripts behave and what one reference document claims, not what
the checklist asserts. 676 -> 678 tests.

## 0.26.0 — 7 August 2026

**The two items this file has called defects since 0.22 now check what they are named
after.** Both were left open on the same argument — that each needed a new check rather
than a new assertion — and both turned out to be one check each.

**CI-002 *Ensure Important Content Is Indexed* asserted that a sitemap listed at least one
URL.** Submission is not indexation: a sitemap with one entry passed a site of five hundred
pages, however much of it Google had dropped, and the floor it actually tested — a sitemap
exists and is not empty — is GO-136's. It now asserts `indexed` from URL Inspection, which
is Google's own answer and the only place that answer exists.

The narrowing is the honest half of the trade and is stated rather than hidden: URL
Inspection answers for **one** page, the audited one, while the title says "content".
Whole-site coverage is the Index Coverage report, which the Search Console API has never
exposed, and the available substitutes are worse than a narrow truth — counting pages with
impressions would fail every indexed page nobody has searched for yet. **Sites audited
without a `gsc` capability get `NO_DATA` where they used to get a `high` PASS**, which is
this file's rule about honest breakage: nobody had measured indexation, and now the report
says so instead of crediting a sitemap for it.

**Pointing an assertion at `indexed` found that the field could not carry one.** It was
pre-seeded with `None` in the result dict, two lines below a comment explaining why
`canonical_match` must not be — `truthy` reads `None` as a *failing value*, not as missing.
So the first run of the new test reported a page as **not indexed** at `high` for a
property nobody could open. `indexed` is now assigned only when the coverage wording is
recognised, exactly as `canonical_match` is. The defect had been there since URL Inspection
arrived and was invisible because no rule read the field.

**IN-127 *Use a Clear International URL Structure* asserted whether the hreflang set mixed
http and https.** A real defect under the wrong name: a site running every locale on
`?lang=` passed *Use a Clear International URL Structure*. `hreflang_checker.py` gained
`check_url_structure`, which answers `ccTLD`, `subdomain`, `subdirectory`, `parameter`,
`mixed`, `single` or `unmarked`. # basis: external standard — Google Search Central,
"Managing multi-regional and multilingual sites", which names the first three and says URL
parameters "are not recommended".

It reads **each alternate against its own hreflang code** rather than comparing alternates
with each other, which was the first attempt and was wrong on the case that matters:
`example.com/de/` beside `fr.example.com/` differs in the host, so component comparison
called a mixture a subdomain structure and passed it. `single` and `unmarked` carry no
`passed` key at all, so one alternate — or a set whose URLs do not encode their locales,
`en-GB` on `.uk` — is `NO_DATA` rather than credited with a structure. A default locale at
the root beside `/de/` and `/fr/` reads as subdirectory, which is the commonest shape there
is.

Protocol consistency is still computed, still reported and still counted in the severity
tally; **no item asserts it now**. An ungraded signal is the smaller problem — the larger
one was an item asserting it under somebody else's title.

Registry `8372d12db748` -> `18948c09ef94`: CI-002 changes script, capability and assertion;
IN-127 changes assertion. No item added or removed, no severity changed. 666 -> 676 tests.

## 0.25.0 — 6 August 2026

**Three of the five Core Web Vitals items measured something else, and the group is now
one measurement asked per device.** This is GO-134's defect in the speed category: the
right title over the wrong field. It was recorded in 0.22 and deferred as "a redesign of
the group, not four edits", which was true and turned out to be a smaller redesign than it
looked.

`performance_score` is Lighthouse's blended lab number — it mixes Total Blocking Time and
Speed Index — and `SP-111` and `SP-112` asserted `>= 90` on it under the titles *Check Core
Web Vitals (Desktop / Mobile) in Search Console*. On the café audit the site's real users
were entirely inside the thresholds — LCP 1974ms, INP 159ms, CLS 0.00, every metric green
in CrUX — and the report told its owner twice, at `high`, to fix Core Web Vitals. The
threshold was not miscalibrated; `>= 90` is a number nobody here chose, and no value of it
turns a blended lab score into Core Web Vitals.

Search Console's CWV report **is** CrUX split by device, and `field_cwv.verdict` is exactly
that. So:

- `SP-111` reads it with `--strategy desktop`. Desktop field data had no item asserting it
  in this registry before, which makes this the one genuinely new verdict in the change.
- `SP-112` reads it with `--strategy mobile`, which makes it identical to `SP-108` in
  script, args and assertion. 0.22's objection to the repair was correct and pointed at the
  mechanism that already exists for it: it is declared a twin in `SAME_CHECK`, so the call
  runs once, the weight counts once, and the item keeps its own title and status.
- `SP-113` *Meet Core Web Vitals Thresholds* (`critical`) asserted `metrics.LCP.rating` —
  one metric — while its fix text has always named all three, so **a page failing CLS
  passed an item titled after all of them.** Also a twin of SP-108 now.

`SAME_CHECK` gained a list value to hold a group of three rather than a pair.

**The `metrics` field switches data source, and SP-113 was the item that hid it.** `metrics`
carries CrUX when CrUX has a sample and Lighthouse's lab audits when it does not. So
SP-113 was a field item on large sites and a lab item on small ones, without saying which,
and it awarded a `critical` PASS about *Core Web Vitals* from a lab number to every site
CrUX has never sampled. **Those sites now get `NO_DATA` where they used to get a critical
PASS.** That is a breaking change for whoever read the old number, and by this file's own
rule it is stated rather than smoothed: Core Web Vitals are field metrics by definition,
"nobody measured this page's real users" is the honest answer, and the lab measurement of
the same page has its own three items (SP-214 to SP-216) fed from a browser trace.

**An unrecognised CrUX band is no longer graded as a failure.** `field_cwv_verdict` decided
failing with `rating != "good"`, so a band this code does not know — a new API category, a
spelling `CRUX_RATING` misses — counted as failing. That was survivable while only SP-108
read it and became load-bearing here: SP-113 had its own `value_map` and answered `NO_DATA`
on an unknown band, and routing it through this function would have converted that honesty
into a `critical` FAIL about a page nobody had measured. Unknown bands are dropped from the
grading and named in `unknown`, and the two halves are deliberately asymmetric: **a failure
among the graded metrics is reported** — one bad metric fails the assessment whatever the
unknown one is — **while a pass is not**, so nothing-failing-plus-an-unknown-band yields
`verdict: "unknown"`, which no `value_map` maps and every item reads as `NO_DATA`.

**The blended score keeps its place and stops being a verdict.** It is the only speed signal
that exists for a page CrUX has no sample for, so the runner lifts it per strategy into
`lab_performance` and both reports print it under *Worth knowing* — the section 0.23.0 built
for exactly this shape of fact — named as Lighthouse lab, attributed to Google's network
rather than the site's visitors, and outside the score, the partition and `--fixes`.

Registry `12b5f87a35f7` -> `8372d12db748`: SP-111, SP-112 and SP-113 change assertion, two
of them gain `scores_with`, SP-112 and SP-113 lose warn bands that came from reading a
three-band rating on one metric. No item added or removed, no severity changed. 662 -> 664
tests.

**Correction, after the release: this release committed a client site's crawl.** Verifying
the new assertions meant re-probing, `tools/probe_shapes.py` writes two files, and
`.gitignore` listed one of them — so `probe-inventory.json`, 224KB of one audited site's
URLs, titles and meta descriptions, went into `681f952` and was published. It is out of the
index, along with a second copy under `scripts/` that a fixture-server probe left behind in
0.9.0 and nothing has read since. **The history still carries both:** removing a file from
the index does not remove it from the commits that added it.

`AnAuditDoesNotCommitItself` is the test that exists to prevent exactly this, and it passed
throughout, for two reasons, both now fixed. It read the audit scripts' argparse defaults
and no tool's. And it compared bare filenames against `git ls-files` **paths**, so it could
only ever see an output committed at the top of the checkout — neither copy was. It now
reads the probe's own `probe-*.json` literals and compares by basename, and it fails on
either file being staged, which was checked by staging them.

**Three more, from a second reviewer reading the same tree, all of the same shape: a test
that could not fail.** The cross-process pacing test opened with `assertTrue(... or True)`
and never started a second process, so the one guard that protects a third party's server
was never measured — three children now race for one host at 5 rps and the gaps are
checked, with the pacing-off case as the other half. The Search Console scenarios accepted
`PASS` **or** `NO_DATA` on good fixtures and "something failed" on bad ones, which a rule
that has stopped deciding satisfies too; all four now pin the full verdict map. The
cache-cleanup test asserted that the shared temp directory held no `seo-http-*`, a claim
about the machine rather than about the run, and failed whenever a second suite ran
alongside; the child now gets its own `TMPDIR`. Each was verified against the failure it
names, not just re-run: per-process pacing slots collapse the gaps to 0.001s, dropping
`summary` from the GSC output drops two items to `NO_DATA`, and two full suites in parallel
now both report 666 OK where one used to fail.

**Also after the release: four test files ran 96% of what they define.** `if __name__ ==
"__main__": unittest.main()` sat above the last class in `test_runner.py`,
`test_registry.py`, `test_report.py` and `test_translated_sites.py` — the last one added
in 0.23.0 — so a direct `python tests/<file>.py` executed `main()` before those classes
existed and reported OK over 58 tests it never ran. `unittest discover` imports the module
instead, so CI collected all of them and had nothing to report, which is why this survived.
No test changed; the block moved to the end of each file, and
`ATestFileRunsEverythingItDefines` parses every `test_*.py` and fails if anything is
declared after it. 664 -> 665 tests here, 666 with the pacing-off half above.

The client domain is also out of the two places it had been written by hand:
`script-output-shapes.md` now says what *kind* of property the Search Console scripts were
probed against without naming it, and `gsc_links_csv.py`'s branded-anchor example uses a
reserved `.example` name. The `GV_SA_KEY` / `gv-sa-key.json` credential paths keep their
spelling — that is a local file an operator has to keep working, and it names no domain.

## 0.24.0 — 6 August 2026

**Three defects in the deliverable, all of the same shape: a field written by one layer
and never read by the next.** 0.23.0's own new section was one of them, which is the
argument for reviewing a release against a real report rather than against its diff.

**A synonym pair was one row in the score and two rows in the task list.** `scores_with`
arrived in 0.22.0 so a single defect could not pull the headline down twice — and
`checklist_report.py` never read that field, not once. So on the 0.23.0 audit one image
missing an `alt` still produced *Provide Meaningful Image Alt Text* (CI-016) at priority
6.0 and *Provide Meaningful Alt Text* (MD-186) at 3.0, both `high`, four rows apart in
the same "what to do first" list and both in `--fixes`. A wrong score is one wrong
number; a task list with a duplicate sends two people to the same image, or teaches the
reader that the list has filler in it.

`twins_folded()` folds synonyms in exactly the two places a reader is asked to *act* —
the priority list and the fix export — and deliberately nowhere else. The full checklist
still prints every item with its own status, because the twin genuinely ran and its
verdict is part of the audit log; folding it there would make the registry's item count
stop adding up. Which half survives is decided before the walk rather than by list order:
the scoring id is the one the score, the diff and the history all name, so it is the one a
reader who looks it up will find. Ordering happened to give the right answer for CI-016 /
MD-186, and "happened to" is not a rule.

**0.23.0's new section spoke English inside a Russian report.** `gsc_checker.py` composes
`finding` and `fix` as sentences at run time, and the section printed them verbatim, so a
`--lang ru` report carried seven English rows. Item titles and registry fixes have a door
into the language file through `item_titles` / `item_fixes`; a string a script wrote has
no such door, and this section was the first time anything in a report came from one.
`OPPORTUNITY_PHRASE` keys on the opportunity's `type` — a stable identifier, never the
sentence — and rebuilds it from `position`, `ctr` and `impressions`, which are already
separate fields beside it. An unknown type falls back to what the script said, in English:
worse than a translation, much better than an empty cell. A test asserts every type
`detect_opportunities` can emit has a phrase, so adding a fourth one there cannot silently
ship English.

**A test skipped itself for eleven releases while reporting that there was nothing to
test.** `test_the_property_string_is_passed_through_untouched` probed
`hasattr(gsc_checker, "fetch_search_analytics")` — a name the module has never had — and
on failing to find it skipped with *"gsc_checker has no single-call entry point to
exercise"*. The entry point is `get_performance_data`, and `main()` calls it. A probe for a
function that does not exist reports the **subject** as missing, and the suite printed
`OK (skipped=1)` over an untested call into Search Console. It now exercises the real
function and asserts both the property string and the parsed rows. The suite has no skips.

**`KNOWN-ISSUES.md` was carrying two stale entries, in the file whose whole purpose is an
honest ledger.** CI-019 was listed `Open` three releases after 0.21.0 fixed it — it
reports `PASS` on the same café now. The duplicate-items entry said "both halves score",
which stopped being true in 0.22.0 and was replaced by a defect it did not mention: the
weight was deduplicated and the reader's list was not. Both corrected at the top of their
entries rather than at the end, because that section is what a person reads before
defending a verdict to a client.

What stays open from the CI-019 entry is the half worth keeping: **no fixture here was
built without consulting the registry, and that is where these keep coming from.** Four
items have now been found by auditing a real site — CI-019, CN-053, GO-134, BL-081 — and
zero by the good-site sweep. Two of the four are invisible on any monolingual fixture, and
every fixture here is monolingual.

**A profile can now say what a kind of site is measured *against*, not only which items
are out of scope for it.** Three findings on the café audit were properties of the
checklist rather than defects of the site, and all three came from one assumption: that a
page has something to explain.

- `CN-039` *Eliminate Low-Value/Thin Pages* reported **14 thin pages of 24** against the
  inherited 300-word default. A service page for a physical business says what it does,
  what it costs and where it is, and then stops: the menu is 189 words, the blueberry page
  220, the petting zoo 232. The three pages a person would actually call thin — the
  galleries, 74 to 94 words — were buried in a list of eleven that were fine.
- `CN-056` *Show Publication and Updated Dates* and `CN-057` *Show Author and Publisher
  Clearly* (`high`) are editorial-content signals. A café's grill page has no publication
  date and no byline, and adding either would be theatre.

`profiles.json` gains `script_args`, and `local` passes `duplicate_content.py
--thin-words 150`. It lands in **argv**, which matters: the number is in the run log, two
profiles produce two different plan keys, and `duplicate_content.py` echoes it into
`summary.thin_words_threshold` so a verdict says what it was measured against. A moved
threshold no evidence string mentions is worse than a wrong threshold. On the café: 14
FAIL -> **3 WARN**, and the three are the galleries.

The 150 is not a better guess than the 300 — it is a number chosen against an observed
site and it says so. Both are `convention`; neither is `measured`. What changed is that
the checklist stops asking a five-page local business to write like a blog.

`exclude_items` gains `exclude_item_reasons`, and a test refuses an exclusion without one.
An exclusion by category names the category, an exclusion by script names the script, and
an exclusion by id used to say only *"excluded by profile"* — the one exclusion a reader
cannot reconstruct, on the only surface where narrowing scope has to argue for itself.
**Narrowing scope is the one operation here that raises the score**, and on this audit it
did: 83/100 over 128 items became 85/100 over 126. Two points of that is scope, not the
site, and the report's own diff says which items left.

`CN-068` *Strengthen Authorship & E-E-A-T Signals* was left failing on purpose. E-E-A-T
for a local business is real — an owner with a name, an address, reviews, a history — and
excluding it would be the exclusion this mechanism exists to prevent.

Also recorded rather than fixed: `THIN_CONTENT_THRESHOLDS` holds five entries and only
`["default"]` has ever been read, because the page-type detection the other four need does
not exist. `location_page: 350` has been dead since import.

Registry unchanged at `12b5f87a35f7`: no item changed its assertion. 643 -> 662 tests, and
one of the 643 was a skip that is now a test.

## 0.23.0 — 6 August 2026

**Two items reported the wrong thing, and both were found by auditing a real site
rather than by reading the code.** A trilingual Lithuanian café: 24 pages, three
languages, one of the plainest link structures a site can have. It collected a `high`
failure for its best search result and a `medium` failure for its navigation menu.

**`GO-134` no longer grades an opportunity as a defect.** It asserted
`none_severity: [critical, high]` over `gsc_checker.py`'s `opportunities[]`, so
*"Position 4.2 with 60 impressions — within striking distance"* arrived as a `high`
FAIL and ranked first in the fix list. Ranking fourth is the best news in the report.
This was open since 0.20 and the reason it stayed open was a misdiagnosis, recorded in
ROADMAP §4: it looked like the registry needed a new **status** meaning *worth knowing*,
which would have cost the runner, both reports, the CSV, both translations, the score
partition, the diff buckets and the every-status-reaches-every-surface test.

It needed no status. A status is a verdict about an item, and no item was failing —
nobody is doing anything wrong by ranking fourth. What was missing was **a place in the
deliverable for a finding that is not a verdict**, and that is a report section, not a
vocabulary word.

So the item asserts on what its title says: `gsc_checker.py` now emits `issues[]`,
built from what Search Console reports as **broken** — errors and warnings recorded
against a submitted sitemap. That is the only such report the API exposes; manual
actions, Index Coverage and mobile usability have no endpoint, which is why GO-141,
GO-142 and MB-099 are `MANUAL` and not wired to a script. Errors fail the item,
warnings warn it, using the same `ISSUES_ANY` / `NOTHING_SERIOUS` pair every other
issue-shaped item uses.

`detect_issues()` returns `None` rather than `[]` when the sitemap list could not be
read, so the item reports `NO_DATA` instead of passing on an answer nobody got. An
unreadable report is not a clean one — the same trap `missing_is: pass` sets, one field
along.

**The opportunities did not lose their home.** Deleting the assertion and keeping
nothing would have thrown away the most useful thing GSC returns: each entry carries
its own `finding` and `fix`, and on the café's own data the list was five pages sitting
at position 2.0–2.2 with 0.4–1.2% CTR. The runner lifts them into
`gsc_opportunities` in the artifact and both reports print them under **Worth knowing:
what Search Console suggests**, stated in the text as outside the score, outside the
item partition and outside `--fixes`. In the HTML they are deliberately not `row`s with
a `data-st`, because the status filters are a filter over items and an opportunity is
not one.

**`BL-081` stops reporting a translated site's menu as anchor spam.** 0.9.0 taught the
check that repetition *across* pages is a navigation bar and repetition *within* one
page is stuffing. That fix asked "does this (target, anchor) pair appear on more than
half the crawled pages" once, of the whole site — and a translated site has one menu per
language. On 24 pages in three languages no menu entry reaches more than 8 of them:
33%, under any share worth calling sitewide. So `navigation_links()` returned the empty
set, all 489 menu links were graded as editorial, and 21 of 24 targets came back as
`overused_exact_match_targets` on a site whose links are fine. Verified against the
live inventory before changing anything: max pair reach 8, threshold 12, navigation
classified 0.

The question is now asked once per **language section** as well as once per site, and
the grouping is the page's declared `<html lang>` — measured, not inferred from `/en/`,
because a URL prefix is a convention and `lang` is a statement. Stuffing still cannot
hide in the new scope: a pair with one source page has a reach of one, and one is never
more than half of a group that must hold at least four pages to be asked about at all.
A site that declares no language is one group, so nothing about a monolingual site
changes.

`site_crawl.py` records `lang` per page, from the parse it was already doing.
`INVENTORY_VERSION` 1 -> 2 — bumped rather than treating absence as tolerable, because
a reader that reads "no lang recorded" as "one language" puts a trilingual site's whole
navigation back into the editorial set, silently, which is what that counter exists to
prevent.

Registry `e7d966be23f9` -> `12b5f87a35f7`: GO-134 changes assertion and gains a warn
band. No item added, none removed, no severity changed.

## 0.22.0 — 6 August 2026

**The open list, emptied — and emptying it found four more defects than the list had.**

**Ten duplicate groups were two problems, not one.** Two of them were never
duplicates: they were two different requirements sharing one assertion because the
second was never written, which is SE-118's defect wearing different clothes.

- `MS-027` *Write Unique, Compelling Meta Descriptions* and `MS-028` *Fill Missing
  Meta Descriptions* both asserted `meta_description truthy`. So "unique and
  compelling" was answered by "exists", and MS-027 could not fail on any page MS-028
  passed. MS-028 keeps the presence check, which is exactly what it asks. Uniqueness
  became MS-029's job. **Compelling** is a judgement no assertion makes, so MS-027 is
  an LLM item on the copy lens — leaving it as a presence check let the registry claim
  it had graded the copy.
- `MS-029` *Eliminate Duplicate Meta Descriptions* read `summary.exact_duplicate_groups`
  — duplicate page **content**, CN-041's verdict. A site running one description across
  forty distinct pages passed it. `duplicate_content.py` now computes
  `duplicate_description_groups` from the crawl inventory, which has carried
  `meta_description` per page since 0.9.0 with nothing reading it. Compared on
  collapsed whitespace and case, because two descriptions differing by a trailing
  space are one description to anyone reading a SERP. Pages with *no* description are
  not counted as duplicates of each other: that is MS-028's finding, made once.

**The remaining eight are real synonyms, and they now carry weight once.** *Add a
Favicon* and *Ensure Favicon Displays in Mobile SERPs* are one question the two
merged source checklists both asked. Scoring both halves did two things: one defect
pulled the headline down twice, and where the twins disagreed on severity — `MB-102`
low against `MD-190` medium — the weight of a defect depended on which twin the reader
looked at. A `scores_with` pointer, decided by hand in `SAME_CHECK` and checked five
ways by tests, keeps the higher-severity item as the one that scores. The twin still
runs, still reports its status, still appears in the report. It is out of
`weight_registry` as well as out of the score, so the denominator matches and
`weight_pct` does not shrink for an item that was in fact decided.

**CN-053 counted words.** Titled *Avoid Critical Content in iFrames*, asserting
`raw.word_count >= 300`. Nothing in the item observed an iframe and
`javascript_render_audit.py` reports no iframe signal of any kind, so a café was told
to stop hiding content in frames it does not have — on three of eight pages, because
one ran to 293 words. It does not become a script item with a better field: embeds are
normal, and whether the content that *matters* is inside one is a judgement about what
matters. Layout lens.

**The 42 unreviewed vocabulary misses are 0, and 14 of them were the tool's fault.**
`len(w) > 2` dropped `h1`, `h2` and `ga4` — which are the entire subject of the items
that name them, and dropping them from the *assertion* side left those items with an
empty vocabulary, unable to share a word with anything. The heuristic now keeps short
tokens carrying a digit, stems regular English endings so `indexed` matches
`indexability`, and reads `field` and `value_map` keys as part of what an item asserts.
The remaining 28 are each answered in writing in `REVIEWED`. Four are defects:

- **`SP-111` and `SP-112`**, *Check Core Web Vitals in Search Console*, assert
  `performance_score >= 90` — the blended Lighthouse score, which mixes TBT and Speed
  Index and is not Core Web Vitals. `pagespeed.py` already computes the right thing in
  `field_cwv`, from CrUX, which is the data Search Console shows. Neither reads it. And
  pointing SP-112 at it would make it identical to SP-108 in script, args and
  assertion — so it is a ninth duplicate pair, not a repair.
- **`CI-002`** *Ensure Important Content Is Indexed* asserts `summary.urls >= 1`. A
  sitemap listing one URL passes a site of five hundred pages, and being in a sitemap
  is not being indexed.
- **`IN-127`** *Use a Clear International URL Structure* asserts whether the hreflang
  set mixes http and https. Worth checking; not URL structure.

All four are left open rather than rewritten in the same pass that found them.

**Presence is not parity.** The i18n tests check that a translation exists, is not
blank and contains Cyrillic — all three stayed green through 0.20 while SE-118's
English fix changed and its Russian did not. `tools/i18n_digest.py` stores a digest of
the English `(title, fix)` beside each translation, so changing the English fails the
build and names the item until somebody re-reads the Russian. Deliberately not a
digest of the translation: improving Russian wording should not require re-stamping
anything. An item with no digest counts as drift, not as a fresh start — a translation
added without recording what it translated is the same unverifiable claim.

**Two CI steps that could not exist before.** `audit_item_semantics.py` was held out
of CI through 0.20 and 0.21 because it exited 1 on the registry as shipped, and a
required check that is red by default is a check nobody reads. It is green now, so it
holds the line: an item added with no ruling, or one silently sharing another's
assertion, fails the build. `i18n_digest.py --check` joins it.

**And the good fixture had duplicate meta descriptions.** Both blog posts carried a
description saying it was shared *"on purpose, so the duplicate-content check has a
duplicate to find"* — except the duplicate content moved to the broken fixture two
releases ago and the descriptions stayed behind. Nothing noticed because nothing
checked descriptions. MS-029's first act on being given real evidence was to accuse
the site the pair calls good, correctly.

Registry `598d714134d9` -> `e7d966be23f9`: MS-027 and CN-053 become `llm` items,
MS-029 changes assertion, eight items gain `scores_with`. No severity changed.
615 -> 629 tests. `llm` 36 -> 38, `script` 144 -> 142.

## 0.21.0 — 6 August 2026

**CI-019 accused every small business on the internet of exposing a shopping cart it
does not have.**

The item reads `/search`, `/cart`, `/checkout`, `/login` and asserted `allowed_urls` was
empty — the paths robots.txt does not disallow. The script never fetched them. So a café
with no cart fails, because nothing disallows a page that does not exist, and the
accusation is `high`.

This is the *second* defect in one field, in opposite directions. Until 0.13 the rule
matched text across a nested dict, `allowed` and `true` never landed in one string, the
pattern never fired, and every site passed. Flattening to `allowed_urls` fixed that and
produced the inverse.

`--probe` now fetches each path robots permits and the assertion reads `indexable_urls`:
the path exists, a crawler may have it, and nothing keeps it out of the index. A 404 is
not an indexable page. A probe that errored lands in `unprobed_urls` rather than either
verdict, so a network failure cannot read as a clean site. Only permitted paths are
fetched — spending a request to confirm that a disallowed path is disallowed buys
nothing.

**And the mechanism repair, which went the opposite way from how it looked.** The title
says `noindex`; the assertion said robots.txt `Disallow`. Those are different
instruments and they conflict — a path blocked in robots.txt is never crawled, so its
`noindex` is never read. The title was not what was wrong. It is inherited wording from
`plerdy-titles.json`, a record of someone else's checklist, and it described the goal
correctly the whole time. `indexable_urls` accepts either mechanism, which is what the
title always asked for.

**Two things found while fixing it, both about this suite rather than the item:**

- After the repair CI-019 passed on *both* fixtures, because neither had a system page
  at all — a check that cannot tell them apart, which `test_contract` refuses. The
  broken fixture now has `/search/index.html`: reachable, crawlable, no `noindex`. It
  had looked like a working test for two releases while testing nothing.
- The first probe read `noindex` off a `<meta name="robots">` quoted **inside that
  fixture's comment block**, where it is listed among the things the page deliberately
  lacks — so the page built to fail the item passed it. Markup inside a comment is not
  markup. Fourth appearance of one mistake in this tree: the keyword items fired on
  their own remediation text in 0.5.0, three assert rules matched a port number in
  0.19.1, and the soft-404 guard carries the warning in writing.

**TE-179, and the answer to whether this registry needs a status meaning "worth knowing
but not actionable".** It does not, and the case for one dissolved on inspection.

TE-179 *Review Domain History & Reputation* asserted `whois.age_days >= 90`. A café's
domain was 58 days old, so it failed a `low` item with a fix nobody can perform — it
resolves itself in a month and until then occupies a line in the fix list, and a task
nobody can do teaches the reader to skim. That looked like the case for a new bucket.
But age is neither history nor reputation, and `domain_safety_check.py` already reports
reputation: age was a proxy reached for because the real signal needs a key. It now
asserts `safe_browsing.threats`, so a clean domain passes at any age, a listed one fails
at any age, and with no `GOOGLE_SAFE_BROWSING_KEY` the field is absent — `NO_DATA`, "we
could not look", which this vocabulary has always been able to say.

GO-134 was the other candidate and fails for a different reason: `opportunities[]` each
carry their own `finding` and `fix`, so that work is real and doable. What is wrong
there is the name and the weight, not the actionability, and both are inherited. Left
open rather than quietly rewritten.

A new status would have cost the runner, the report, the HTML, the CSV, both
translations, the score partition, the diff buckets and the every-status-reaches-every-
surface test — to make two miscategorised assertions comfortable. What was missing was
not a status. It was a correct assertion.

One more thing `audit_assertions.py` caught on the way: TE-179's new rule was first
written against `safe_browsing.matches`, which is the key in Google's raw response and
a name the script never re-emits. The tool exists for exactly that and found it before
a run could.

Registry `a7bb134d42f9` -> `598d714134d9`: CI-019 and TE-179 change assertion, CI-019
gains `--probe`. No severity and no other item changed. 608 -> 615 tests. `ru.json`
follows both fix texts.

## 0.20.0 — 5 August 2026

**The registry said it verified certificates. It never once did.**

SE-118 — `critical`, titled "valid TLS certificate" — asserted `https == true` on the
output of `security_headers.py`. That is SE-117's field, from SE-117's script. Two
critical items therefore shared one assertion: SE-118 could not fail independently on
any site in the world, and a certificate that expired yesterday passed it, because
`https://` was still `https://`. Every audit this plugin has produced since 0.1.0
reported a verified certificate on the strength of a URL scheme.

It now runs `tls_certificate.py` and reads `valid`, which is set by a handshake with
`verify_mode = CERT_REQUIRED` and `check_hostname = True` against the system trust
store. Nothing re-implements verification: `ssl` rejects the connection and the reason
it gave is what gets reported. A second, non-verifying pass exists only to *read* a
certificate the first pass refused — without it, "expired" and "connection refused"
would arrive as the same empty result.

**A verdict that used to be unconditionally PASS can now FAIL.** By the rule at the
top of this file that is exactly why this is a minor and not a patch. Anyone whose
SE-118 result moved has not regressed; they are being told something true for the
first time.

**Three things the fix uncovered, none of them about TLS:**

- No fixture in this suite can exercise SE-118. Both fixture sites are plaintext and
  `http.server` does not speak TLS, so SE-118 dropped out of `ACCUSED_ON_PURPOSE` and
  its only coverage is `test_tls_certificate.py`, which stands up its own TLS origin.
- The first draft opened TLS against the good fixture's plaintext port and reported
  `SSLError: WRONG_VERSION_NUMBER` — an error about our own request, presented as a
  fact about the site, which the good-site sweep counted as a crashed script. An
  `http://` URL now returns without a handshake and without `valid`, so the item is
  `NO_DATA`. SE-117 is the item that says a site is not on HTTPS, and it already fails.
- `test_evidence.EveryCriticalItemIsCovered` measured coverage against a hand-written
  set literal and never opened a test file, so a script named there and tested nowhere
  would have read as covered. A third test now makes the suite prove each name.

**`tools/audit_item_semantics.py`** is new, and deliberately not wired into CI: it
exits 1 today, and a required check that is red by default is a check nobody reads.
It finds two classes of defect. Exact duplicates — items whose (script, args, assert)
triple is identical, so they cannot disagree. There were **eleven groups**; SE-117 and
SE-118 were the worst because both are `critical`, and closing that one leaves **ten
still standing**, none of which this release touches. And a vocabulary
heuristic: items whose title and fix text share no terms with the script and assertion
path underneath them, 42 of which are unreviewed. CI-019 and CN-053 are confirmed real
by hand — they accuse a site over indexable URLs the crawler never fetched — and
TE-179 and GO-134 are confirmed false alarms.

**The step-1 question, answered.** The good-site sweep is not blind to CI-019; the
fixture's `robots.txt` was written to satisfy it, `Disallow: /search /cart /checkout
/login` and all. Which generalises: a fixture built to pass the registry cannot catch
an item that accuses every real site.

Registry `ae29bf452412` -> `a7bb134d42f9`: SE-118 changes script and assertion. No
other item, severity or script changed. 601 -> 608 tests. `ru.json` follows SE-118's
new fix text — and worth stating, nothing caught that gap: the i18n parity tests check
that a translation exists, is non-blank and contains Cyrillic, none of which notices a
Russian sentence that has quietly stopped describing the English one.

## 0.19.1 — 5 August 2026

**The flake was not a flake. Three assertions could match a URL and call it a
verdict.**

`test_go_138_needs_the_urls_fetched_to_find_anything` failed once on CI, passed on a
re-run of the same commit, and survived 15 local runs of the full suite. 0.18.0 shipped
a diagnostic instead of a guess: the assertion now prints the issues it actually saw.
It fired again on the next push and named its own cause in one line.

The test origin had bound port **40455**, and GO-138's rule is
`none_matching: "(?i)404|redirect|noindex"` over `issues`. Without a `field`, the
pattern is matched against the whole serialised issue — severity, message, url,
evidence — so `404` matched the port inside
`{"message": "Sitemap URL missing lastmod", "url": "http://127.0.0.1:40455/"}` and a
clean sitemap was reported as full of dead URLs.

**This is a registry defect, not a test defect.** A sitemap listing
`/blog/404-errors-explained` fails GO-138 on any site. GO-143 matched `WebSite` the
same way and was one `/website-design` URL away from the same failure; AR-158's
`BreadcrumbList` shares the shape. All three now name `field: "message"`.

**Third occurrence of one mistake.** The keyword items fired on their own remediation
text in 0.5.0, which is why `field` exists at all and why the comment beside it in
`checklist_runner.py` explains the hazard. The runner's soft-404 guard carries the same
lesson in writing — *"Never a substring: `404` appears in the title of every article
ever written about broken links"*. Neither was ever turned on the rules themselves.
A test does it now: an `issues` pattern without a `field` fails the build, and a
`field` naming something no issue carries fails it too.

Worth keeping in view about the diagnosis: the mechanism was only reachable when an
ephemeral port happened to contain `404`, so it looked like nondeterminism and every
theory built from that framing — DNS, the parallel runner, shared rate-limit state —
was wrong. Printing the payload cost four lines and settled it on the first firing.

Registry `1c4b3697cc1f` -> `ae29bf452412`: three assert rules gain a `field`. No item,
severity or script changed. 599 -> 601 tests.

## 0.19.0 — 5 August 2026

**A trend, not a pair — and a Russian report that is Russian all the way down.**

`.seo-runs/` has stored every audit since 0.1.0 and exactly one of them was ever
read. `--diff` answers "what changed since last time"; the question a site owner
actually asks is whether months of work moved anything, and the data to answer it was
already on disk.

The report gains an **Over time** section: every stored run, oldest first, with the
score, the share of the weight it spoke for, and how much it could decide. The reach
column is there deliberately — a run that decided less of the checklist is not a run
that found less wrong, and a score line alone cannot tell those apart. The current run
is the last row and says so; leaving it out showed a reader an arc that stopped a
month before the report in their hands.

**`open_since` is the part that earns the section.** For every item failing now, how
many consecutive audits it has been failing and since when. A score can sit at 70 for
six months while a different item fails each time, so the arc alone cannot say whether
anything is stuck; "open in all six audits since April" can. Counted as an unbroken
streak backwards from today, never as a total — an item that was fixed and broke again
is not an item nobody has touched, and reporting it as one would be an accusation the
data does not support.

`--history-limit` bounds how far back it reads (12 runs by default). Per-run status
maps are dropped before writing: they are what the streak is computed from, and
carrying them into the artifact would multiply a file people email by the length of
the history.

**The Russian report is complete.** All 214 item titles and all 214 recommendations,
translated. From 0.2.0 to 0.18.0 `--lang ru` produced a document whose own prose was
Russian and whose every checklist row was English — including, until this release, the
one table naming what had been broken longest, which read `row["title"]` directly
instead of going through the translation lookup like every other item row.

The completeness is **computed, not declared**. Four tests check both directions
against `checklist.json`: no item without a translation, no translation for an item
the registry dropped, nothing blank, nothing without Cyrillic in it. This file has
twice claimed a completeness it did not have — 0.12.0's diff section arrived
untranslated after the note was written, and the caveat block was 19 strings while the
note said six — and both errors were in the flattering direction. What no test can
catch is a translation that has drifted in meaning from the item it translates.

**Two tests changed because the gap they described closed.**
`test_a_partly_translated_language_names_what_is_still_english` read `Lang("ru")`
directly and passed because the item layers were genuinely empty, so completing them
broke a test that was about the *warning*. It hobbles a copy now, and a second test
asserts the warning can go quiet — a caveat that is always printed is one nobody reads
by the third report.

**Also in this release: four passages of prose that had been wrong since 0.15.0.**
`SKILL.md`, `seo_common.py`, `checklist_runner.py` and the scanner's own docstring all
still told the reader that `answer_block_scanner.py` scores 10 under `lxml` and 32
under `html.parser` and that **neither reading is right**. 0.15.0 rewrote that file
against document order and both parsers return 42 on exactly that markup. `SKILL.md`
is the agent's instruction file, so this was not cosmetic: it instructed a model to
hedge a verdict that had been sound for four releases. All four now state what was
true, when it stopped being true, and what still justifies recording `html_parser` in
the artifact.

585 -> 599 tests. Registry unchanged at `1c4b3697cc1f`, 214 items.

## 0.18.0 — 5 August 2026

**How much of the SEO Score is the site, and how much is a table nobody chose.**

`SEVERITY_WEIGHT` — critical 10, high 6, medium 3, low 1 — decides the headline, and
`EFFORT_COST` orders the fix list. Both are `inherited`: they arrived with borrowed
code and nobody here has examined them, while the score has been reported to two
significant figures the whole time.

The step taken here is deliberately not calibration. What a critical item is worth
relative to a low one cannot be measured from anything in this repository — it needs
outcome data over real properties. What *can* be measured today is whether the answer
matters, and `tools/audit_score_sensitivity.py` measures it by re-scoring finished
runs under a spread of defensible tables.

**The result is neither of the two outcomes that were predicted.**

| Run | Decided | flat 1/1/1/1 → steep 27/9/3/1 | Spread | Pass-rate range |
|---|---:|---|---:|---:|
| good fixture, live | 106 | 69.3 → 69.1 | **0.2** | 11.8 |
| broken fixture, live | 106 | 33.5 → 31.6 | **1.9** | 27.0 |
| good fixture, page mode | 88 | 89.8 → 80.5 | **9.3** | 37.5 |
| smoke page, archive | 16 | 56.2 → 70.8 | **14.6** | 50.0 |

So the table is neither decoration nor uniformly decisive, and the driver is not how
many items were decided — it is **how far the per-severity pass rates spread**. A
weighted mean can only differ from an unweighted one by as much as the groups differ,
so the score is least sensitive to the weighting on a site that passes its critical
and its low items at the same rate, and most sensitive on one whose critical items are
the broken ones. That is the sobering direction: the weighting matters most on exactly
the sites worth auditing.

`measured` in the threshold inventory stays **0**, and that is the honest count. What
was measured is the consequence of the number, not the number.

**`EFFORT_COST` is closed.** Dividing by effort changes 2-4 of the first ten fixes
against not dividing at all, so the idea earns its place; the exact ratio does not —
1/2/3 gives the identical first ten on every run measured and 1/3/9 differs by one
row. Whether to divide is the decision, which numbers is not, and the basis line says
so now.

**The tool.** `tools/audit_score_sensitivity.py` reads artifacts a normal audit
already writes and re-runs no check. It asserts nothing, and CI prints its read-out
over `live.json` rather than gating on it: the spread is a property of the site
audited, so a threshold on it would fail whenever the fixture changed. Five tests pin
the thing that would make the whole exercise meaningless — that its arithmetic and
`checklist_runner.score`'s are the same one, over the same decided items, and that its
fix ordering is the report's.

580 -> 585 tests. Registry unchanged at `1c4b3697cc1f`, 214 items.

## 0.17.0 — 5 August 2026

**The two groups that could only sit at zero can now be answered.**

0.16 made the report say that 49 items were waiting on the operator and 34 needed a
person. Neither number could move: 34 of them — 16% of the registry, 116 points of
weight — had no way back into a run at all, and the queue's 36 needed an agent to
construct JSON by hand.

**`--manual-answers`**, the mirror of `--llm-answers`. Merges `MANUAL` items only, so
it cannot flip a verdict a script reached, and it cannot answer the language model's
queue either — one file that could do both would let a person quietly settle the
questions the queue exists to make somebody read the page for.

**A reason is required.** An LLM answer with no rationale degrades to "no rationale
given" and a reader can weigh it; a human `PASS` with nothing beside it is
indistinguishable from a tick made to clear the list, and thirty-four of those move
the score with nothing to argue with. Refused by id, on stderr.

**`decided_by` on every decided item** — `measured`, `model` or `claimed` — and the
report prints the mix whenever it is not all measurement:

```
SEO Score 70/100 — over 109 items, 57% of the weight in scope
  of the decided: 3 claimed, 106 measured
```

Set once, at the end of `grade()`, rather than at each branch that produces a verdict,
so a path added later cannot mint one with no provenance. A contested LLM verdict
drops its `decided_by` with its status, because it no longer has one.

The HTML report's "Needs a person" section exports the ticked items as a starting
file. A tick claims `PASS` and carries no reason, so the exported evidence says
exactly that and is deliberately not good enough to merge as it stands.

**Each queue file's JSON skeleton now names its own items.** It printed `CN-047` and
`CN-060` whatever the file was asking about, so the locale queue — `IN-126`, `IN-130`,
`TE-165` — showed a template for two items that were not in it. A merge keyed on an id
that is not pending applies nothing, and until this release said nothing either.

**Three defects found while building it.**

- **An answer for an item in the wrong state vanished silently.** Both merges read the
  file, changed nothing, and printed a success line. They now name the id and its
  actual status. The audit's own rule — nothing is silently skipped — did not apply to
  the audit's own inputs.
- **`evidence: null` became the literal reason `"None"`.** `.get("evidence", "")`
  returns the stored value when the key is present and null, so the default never
  applies and `str(None)` is a non-empty string that walked through the reason guard.
  Found by a test parameterised over `("", "   ", None)` rather than over `""` alone.
- **The same shape crashed the LLM merge.** `None.strip()` raises, so a null rationale
  killed the merge instead of degrading to "no rationale given" — present since the
  merge was written, and reachable from any answer file.

Dispatching the four lens agents stays a `SKILL.md` change and is documented rather
than automated: the runner is a Python CLI that launches subprocesses and has no
model, so it cannot dispatch anything. `ROADMAP.md` records the correction.

Russian: 6 new strings, 122 in all. 571 -> 580 tests.

Registry unchanged at `1c4b3697cc1f`, 214 items.

## 0.16.0 — 5 August 2026

**Coverage was one number standing for three things, and it is gone.**

`Coverage %` divided decided items by applicable ones. That sum added together how
far the tool reached, how much work the operator had done, and how much of the
checklist was never the audit's job to answer — so it moved for any of the three
without saying which. Coverage falling from 62% to 50% between two audits read as
the site becoming harder to measure when it could equally mean nobody answered the
queue that week. It is the same objection this project raises to a single SEO score,
one level down, and it was in every report from 0.1.0 to 0.15.0.

Measured on the good fixture, `--sample 3`, no key and no artifacts: `50%`. What it
was made of — 106 decided, 36 nobody had answered, 34 that no audit can answer, 13
waiting on a file, 25 genuinely undecidable. One percentage for five facts.

**The score now carries the share of the weight it was computed over.**

```
SEO Score 69/100 — over 106 items, 55% of the weight in scope
```

489 points of 890. `96/100 at 19%` reads wrong on sight, which is what the old pair
of numbers was reaching for; what it never said was which of the two you were
holding, because the same 69 was printed over 55% and over 95% of the registry.
`N/A` items are out of the denominator, as they are out of every other number here.

**Under it, a partition — not percentages.**

Every item lands in exactly one bucket named for **whose action moves it**, and the
buckets add up to the registry, so nothing hides in a denominator:

| Bucket | Fixture run | Who moves it |
|---|---:|---|
| decided | 106 | — the score is computed over these |
| waiting on you | 49 | the operator: 36 unanswered queue items, 13 missing inputs |
| needs a person | 34 | a human, in the Search Console UI or by looking |
| undecided | 25 | nobody: no such field, service unreachable, check failed |
| not applicable | 0 | out of scope for this mode or profile |

A test asserts the sum equals the registry. A percentage can be read without
noticing what fell out of its denominator; rows that have to add up cannot.

**`NEEDS_INPUT` is a status now, because the partition has to come from statuses.**

`NO_DATA` was carrying four unrelated sentences: an input was not supplied, the site
served no such field, an external service could not reach the host, the script died.
Only the first is work for the person running the audit, and printing it as "could
not be determined" reads as a limit of the tool rather than a missing argument.
Thirteen items said that on the measured run; seven of them were a Search Console
key.

The first version of the partition was computed by matching `"missing input"` inside
the evidence prose, which is how it was first measured — and that coupling breaks in
silence the first time a reason is reworded. A status is what makes it structural.
`NEEDS_INPUT` gets its own report section, **"What this audit was not given"**, in
both renderers and in Russian; it is not a `--fixes` row, for the same reason
`NO_DATA` and `LLM_PENDING` are not: a client's sprint should not fill with the
auditor's unfinished business.

**Two defects the change turned up on the way.**

- **The HTML history section was printing `coverage None%`.** The same sentence
  lives in two renderers, the markdown one had a test, and the HTML one was found by
  grepping for the renamed key rather than by anything failing. Both are asserted now
  — over a payload that exercises the history section, against the literal word
  `None` — and the assertion was checked by reintroducing the bug.
- **The report would not have parsed on the declared Python floor.** An escaped
  quote inside an f-string is 3.12 syntax; the floor is 3.10 and the development venv
  is 3.14, so only `ruff` saw it. The shared sentence is a module constant now.

Also: the report's status table, bar legend and filter buttons read one
`STATUS_ORDER` tuple instead of three hand-written lists, and a test ties that tuple
to the statuses the runner can actually emit. Adding a status to two surfaces out of
three fails the build rather than going missing from a document nobody diffs.

Russian: 16 new strings and the two statuses, 116 in all. `item_titles` and
`item_fixes` remain empty.

Registry unchanged at `1c4b3697cc1f`, 214 items: this release changes how the run is
reported, not what it checks. Every one of the 214 verdicts on the fixture is the
same before and after — only their arithmetic is presented differently.

## 0.15.0 — 5 August 2026

Registry unchanged (`1c4b3697cc1f`, 214 items). Tests 552 → 564.

Every phase of the plan had shipped, so this release is the open list in
KNOWN-ISSUES.md — the items that were written down because they could not be closed at
the time. Four of the five closed. The largest one turned out to be hiding the second
largest.

### Fixed — the answer-block score no longer depends on whether the page closes its tags

`answer_block_scanner.py` found the answer to a question heading with
`find_next_sibling()`, which asks the parser where the heading's parent ends — and that
is the one question `lxml` and `html.parser` answer differently. `html.parser` applies
none of HTML's implied end tags, so an unclosed `<p>` swallows every heading and list
after it and three unclosed `<li>` nest three deep. One page, two parsers, scores of 10
and 32, and **neither was the reading a browser gives**. 0.14.0 pinned those numbers as
a fact; recording a verdict that depends on which library is installed was the wrong
thing to do with it.

Three queries were rewritten against what both parsers agree about, which is also what
the browser agrees about:

* the answer is found in **document order** to the next heading, not by sibling walk;
* a paragraph's word count is its **own** text, with block-level descendants excluded;
* a list's items are the `<li>` whose **nearest list ancestor** is that list, not its
  direct children.

Three shapes that a browser renders identically now score identically under both
parsers, where they used to produce five different numbers between them.

**And a second defect the sibling walk was hiding, which needed no invalid markup at
all.** A `<div>` between the heading and the paragraph — every themed CMS there is —
was itself read as the answer, so the reported word count was the whole section's and
the reported answer text was every paragraph in it. Two paragraphs measured 53 words
and squeezed under the 70-word ceiling with the wrong text attached; three or more went
over it and the page had no direct answer at all. Wrappers are walked through now.

Nothing changed on the fixture pair: both fixture pages close their tags and wrap
nothing, so all 214 verdicts are identical. That is the shape a fix like this should
have — no movement on valid markup, and the right answer on the markup most of the web
actually serves.

### Fixed — 0.14.0's fork fix covered two call sites out of ten, and one of them was lying

0.14.0 diagnosed macOS killing a forked child inside Apple's Network.framework
`atfork` handler, fixed `checklist_runner.run_script` and `tests/harness.spawn`, and
wrote down that the workaround "holds only while nothing reintroduces a `cwd=` or
`close_fds=True`". It was already broken when that sentence was written. **Eight other
call sites in this tree still forked**, and the crash dialogs never stopped.

The missing condition is one CPython checks and nobody reads. `posix_spawn` is used only
when **`os.path.dirname(executable)` is non-empty** — so `["openssl", …]` and
`["git", …]` take the fork path however carefully `close_fds` and `cwd` are set. Every
call that passed `sys.executable` looked fixed because that path is absolute. Every call
that named a binary on `PATH` was not.

**What that cost is the finding.** `harness.tls_context()` generated its certificate with
a bare `subprocess.run(["openssl", …], check=True)`. The child died of signal 11, and the
`except` around it raised `SkipTest("openssl unavailable, so the HTTPS shape cannot be
served")`. openssl was installed and working. So the TLS site shape 0.14.0 announced as
*exercised live* had **never once run on the machine it was written on** — it ran on
Linux CI, which is the only reason the claim was not simply false — and the skip message
named a cause that was not the cause, which is the failure this entire tree is built to
refuse. Local runs went from 4 skips to 1, which is what Linux has always reported.

Three rules now, checked by AST over `scripts/`, `scripts/lib/`, `tools/` and `tests/` —
every `subprocess` spawn in the tree, not the two functions somebody remembered:

* `close_fds=False` on every call;
* no `cwd=` on any call — `git -C`, `PYTHONPATH` and, where a working directory is
  genuinely the thing under test, `runpy` inside the child after exec;
* no bare executable name — resolved with `shutil.which` first.

`harness.spawn` lost its unused `cwd` parameter, because an unused parameter that
silently reopens the bug is worse than no parameter, and it now spells `close_fds` at the
call rather than folding it into a kwargs dict — a guard a helper can hide from is a guard
that stops at the helper. The two sites this actually mattered for outside the tests were
`domain_safety_check.py`, the one evidence script that starts a child process (`whois`),
and `tools/probe_shapes.py`.

### Changed — every number a verdict rests on has a name and a stated basis

`tools/audit_thresholds.py` reported 36 named thresholds and **77 comparisons against a
bare literal**, held as a ceiling in CI because "a number nothing can name is a number
nobody can argue with". All 77 are named now, and the count is zero.

The point was never the count. It was what naming them made visible:

| | 0.14.0 | 0.15.0 |
|---|---|---|
| `standard` — a published authority, named | 4 | 6 |
| `measured` — calibrated against something | **0** | **0** |
| `convention` — a judgement made here, stated as one | 18 | 32 |
| `inherited` — arrived with borrowed code, never examined | 14 | **75** |

**`inherited` went from 14 to 75.** The unnamed literals were not a random scatter: 59
of the 77 were already there in the initial commit, which is checkable rather than
remembered — the classification comes from `git show <initial commit>`. So the honest
figure is that roughly two thirds of the numbers this registry's verdicts rest on
arrived with borrowed code and have never been examined by anybody here, and the old
14 read that way only because the other 61 had nowhere to carry a label.

`measured` is still zero, which remains the finding underneath the finding.

Three things fell out of the pass, and each is the argument for doing it:

* **Two thresholds were written twice.** 300 words for thin content lived in
  `duplicate_content.THIN_CONTENT_THRESHOLDS` *and* as a literal in `article_seo.py`;
  the 30-second `Retry-After` ceiling lived in `safe_http.MAX_RETRY_AFTER_WAIT` *and* as
  a literal in `html_validator.py`. Both now have one home. One number in two places is
  one number that can be revised in one of them.
* **A check and its own advice disagree.** `article_seo.py` accepts a title of 30-65
  characters while the fix text beside it asks for 50-60, and accepts a meta description
  of 100-165 while advising 120-155. Recorded in the basis lines rather than reconciled:
  deciding which pair is right is a calibration, and this pass was an inventory.
* **The audit tool had two blind spots of its own.** It excluded 100, 1000 and 1024 as
  "units rather than limits" — removing them surfaced eleven comparisons, **ten of them
  real thresholds**, including "a meta description under 100 characters is too short"
  and "under 1000 words may be thin for a blog post". And it counted equality
  comparisons on the unnamed side while counting only ordering comparisons on the named
  side, so the two halves of one tool disagreed about what a threshold is.

A fifth basis kind, `presentation`, now covers the eleven numbers that decide what is
*printed* and never what is decided — a truncation length, a "… and 7 more" cut-off, how
much of an API key is masked. They are named and checked like the rest and kept out of
the verdict total, because a report listing three linking pages instead of four is a
report making a different choice, not an audit reaching a different verdict.

### Added — `--verify-bots` confirms a crawler is the crawler it claims to be

`server_log_audit.py` classified crawlers by User-Agent, which is a string the client
chose, and the direction of that error was always towards *over*-reporting the crawl:
nobody forges a User-Agent to look less important. A scraper announcing itself as
Googlebot spent Google's crawl budget in the figures CI-018 reports.

`--verify-bots` (on `server_log_audit.py`, and on the runner, off by default in both)
does the reverse-then-forward DNS check Google, Bing and Yandex all document. **The
second step is the one that matters**: a reverse lookup alone trusts whoever controls
the PTR record for the address, which is the address's owner, so anybody with a rented
block can name it `crawl-203-0-113-1.googlebot.com` and be believed. Confirming that the
name resolves back to the same address closes that, because the forward zone is Google's.

Requests from an address that fails are **re-attributed out of the crawl-budget
figures**, not annotated in place — the whole cost of an unverified identity was that a
scraper's 404s counted as Google's, and leaving them there with a note beside them would
leave the number wrong. A `medium` finding says how many.

Four things it deliberately does not do:

* **Treat a DNS failure as forgery.** `unresolved` keeps the requests attributed to the
  crawler that claimed them. Reading "the resolver did not answer" as "not Googlebot"
  would turn one outage on the auditing machine into a report telling a client their
  entire crawl is fraudulent — the same shape as a busy W3C validator becoming "your
  HTML has errors".
* **Invent a rule for crawlers that publish none.** DuckDuckBot, SeznamBot and PetalBot
  publish address ranges rather than a DNS convention, so they answer
  `no_published_rule` and stay claims.
* **Ask DNS more than once per address.** A log is millions of lines and a crawler
  reuses its addresses; the cache means eight requests from two addresses cost two
  lookups. Bounded at 64 addresses, beyond which an address is `not_checked` and, again,
  not assumed either way.
* **Run by default, or reach the network from the test suite.** The resolver is
  injectable, which is what lets eight tests cover forgery, a lying PTR record, a
  label-boundary suffix (`notgooglebot.com` ends with `googlebot.com`), a dead resolver,
  the cache, the budget and the default path — all offline.

### Added — a supplied measurement's age is shown, and can be bounded

A `--cwv-json` or `--rendered-json` file is the one input an audit cannot check by
measuring again. 0.7.0 closed the part that could be checked: an artifact naming a
different page is refused with the reason. What remained was *when* — a trace from six
months ago describing today's URL was accepted without comment.

The report now states the age of the oldest supplied measurement in days, and
`--max-artifact-age DAYS` refuses one that is older. Off by default, because there is no
honest default: how stale a measurement may be depends on how often the page changes.

The age comes from the filesystem's mtime and **not** from any timestamp inside the
file, and that is the whole of what it adds. Everything an artifact says about itself is
the operator's claim. An mtime is still forgeable — `touch` exists — but not by writing
JSON, which is what producing one of these files involves, and files usually go stale by
being left alone rather than by anybody deciding to lie. It does not make the age
verifiable; it makes it visible and boundable, which is as far as re-measuring cannot
reach.

### Fixed — the Russian report is no longer missing its highest-stakes prose

`--lang ru` left 19 of the report's 100 own strings in English, silently, because `t()`
falls back. They were the "what was audited" caveat block — the private-host warning,
the scored-interstitial warning, the thin-page warning, the supplied-measurement
warning — and the whole "Since the previous audit" section, which arrived untranslated
in 0.12.0 and was only noticed because 0.7.0 had taught the warning to *count* instead
of asserting completeness.

All 19 are translated. `item_titles` and `item_fixes` are still empty and still
reported: 214 item titles and their recommendations are a translation project, not a
code change, and the warning says so rather than implying the report is fully Russian.

The test that guarded this had to change with it. It asserted that `missing_strings()`
was non-empty, which would have started failing the moment the work was done — a test
that punishes the fix is a test that keeps the defect. It now removes a string the
report asks for and checks the counter finds it.

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
