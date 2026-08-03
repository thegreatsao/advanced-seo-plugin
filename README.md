# seo-checklist

A deterministic SEO audit for Claude Code. One fixed registry of 214 checks, run
the same way every time, with a status on every item and an honest account of
what could not be decided.

Version 0.2.0 — see [CHANGELOG.md](CHANGELOG.md). Several checks are stricter than
in 0.1.0 in ways that *lower* the reported numbers, which is the point: the entries
say which verdicts used to be fabricated.

Read [KNOWN-ISSUES.md](KNOWN-ISSUES.md) before you rely on a report. Nine defects
and gaps are measured and ranked there; four of them change how the numbers should
be read, starting with the fact that `--sample` is not a sample.

## Why it exists

The usual failure of LLM-driven SEO tooling is that the model picks what to run.
Two audits of the same site check different things, and neither tells you what was
skipped — so the score looks like a measurement when it is really a sample of
whatever the model remembered.

This plugin separates the two halves of that problem.

`resources/config/checklist.json` is the contract: 214 items, each naming what
answers it — a script plus an assertion over that script's output, a Search
Console call, a language-model judgement, or a human. Nothing in the registry is
executable; assertions are declarative and interpreted by the runner. Coverage is
therefore a property of the registry, not an accident of the run.

Two numbers come out, and they are deliberately never merged:

- **SEO Score** — of the items actually decided, how many passed, weighted by severity
- **Coverage** — of the items that applied, how many could be decided at all

A 96/100 at 19% coverage is not a good site. It is a thin audit. Collapsing these
into one number is how audits come to sound more confident than they are.

## What is in the registry

214 items: the [Plerdy 200-point checklist](https://www.plerdy.com/seo-checklist/) plus 14
checks it does not cover — GEO/AI search, `llms.txt`, AI-crawler policy, IndexNow,
schema guards, and lab Core Web Vitals from a local trace.

| Answered by | Items |
|---|---|
| a script, asserted against its real output | 146 |
| a language model reading the page | 33 |
| a human | 32 |
| Search Console, with no API to answer it, so a person opens the UI | 3 |

146 script-backed items collapse to **55 unique process launches** — the runner
deduplicates, so `pagespeed.py` runs once, not seven times.

Nine items moved from script to judgement in August 2026 as a correction, not a
design change: each asked a script about wording it never emits, so each had been
reporting PASS on every site (see "Assertions that cannot fire"). Five then came
back to being measured, from a rendered page rather than from HTML — font size,
link distinctness, overlays and tap targets are computed values, and a model
reading markup cannot see them. The three that stayed judgements are judgements: a
close keyword variant and a localised title are not measurements.

Every item also carries an `effort` estimate, so the fix list is ranked by
severity **against** effort rather than by severity alone: ranking by severity
alone puts a week of rewriting above a one-line meta tag. Effort is a
per-category heuristic, not a per-item estimate, and the report says so.

Every result records the `registry_version` it came from, and `--diff` warns when
two runs used different registry versions, profiles or modes — otherwise "no
status changes" could mean the checklist itself changed underneath.

## Install

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Core requirements are `requests`, `beautifulsoup4`, `lxml`. Search Console checks
also need `google-auth` and `google-api-python-client`; without them those items
report `NO_DATA` with a reason rather than failing the run. `archive` mode needs
no HTTP library at all, only an HTML parser.

## Run

```bash
S=skills/seo-checklist
python3 $S/scripts/checklist_runner.py https://example.com               # full, live
python3 $S/scripts/checklist_runner.py https://example.com --mode page   # one page
python3 $S/scripts/checklist_runner.py https://example.com --archive ./backup
python3 $S/scripts/checklist_runner.py https://example.com --diff        # vs previous run
python3 $S/scripts/checklist_runner.py https://example.com --profile ecommerce
python3 $S/scripts/checklist_runner.py https://example.com --sample 10   # several pages
python3 $S/scripts/checklist_runner.py https://example.com --links-csv ~/Links.zip
python3 $S/scripts/checklist_report.py checklist-results.json            # render output
python3 $S/scripts/checklist_report.py checklist-results.json --lang ru  # Russian report
```

### Site profiles

`--profile default|local|ecommerce|saas|blog|media` narrows the registry to what
a given kind of site can be judged on. An excluded item is `N/A` with the profile
as its reason and touches neither metric.

Omit the flag and the run detects the site type first, then asks with that
suggestion pre-selected — Enter accepts it, anything else overrides it. Detection
reads structured data, platform fingerprints and cart/pricing markup rather than
wording, and it runs on the entry page the audit was going to fetch anyway, so it
costs no extra request. Thin evidence produces `default` and says so instead of
guessing.

`--profile auto` accepts the detection without asking. That is the only way a
heuristic narrows scope here, and it takes an explicit flag, because passing it
is a decision.

The prompt appears **only** when a terminal is attached: CI, cron and background
runs use `default` — the full registry — mention what detection would have
suggested, and print why they did not act on it. A question nobody can see is a
hang. `--no-prompt` forces that behaviour anywhere.

Every non-answer — Enter, nonsense, EOF — resolves to `default`, the widest
scope. Guessing a narrower profile would drop checks and lift the score without
anyone deciding to. For the same reason no profile may exclude a `critical` item;
a test enforces it. An unknown name is an error, not a silent fallback.

### Several pages at once

`--sample N` collects up to N same-host URLs (sitemap first, on-page links
second) and runs the page-level checks against each; site-level checks still run
once. The worst verdict wins, but the evidence carries the count — `1/5 pages:
title is 61 characters` is exactly what a single-page audit would have missed.

> **These are the first N URLs in document order, not a statistical sample.**
> Sitemaps are usually ordered by section or by date, so the first N tend to be one
> corner of the site. The report says "on 5 of 5 pages checked", which reads as a
> sample and is not one — read it as "N pages from the top of the sitemap". Known
> issue, see [KNOWN-ISSUES.md](KNOWN-ISSUES.md).

Candidates come from `<a href>` only, asset extensions are rejected by path, and
anything served as a non-page is dropped at fetch time. Because the worst verdict
wins, a single stylesheet in the sample would otherwise fail every page-level
check and condemn the site.

### Redirects to another host

When the entry URL redirects to a **different host**, the destination is what
gets audited, and `requested_url` records what you asked for. Otherwise the run
disagrees with itself: `--sample` filters candidates on the old host and collapses
to a single page, and `sc-domain:` is derived from a domain the service account
has no property for — both of which fail quietly, looking like a small site with
no search traffic.

A same-host hop (`/` → `/en/`, http → https) keeps the URL you gave, so
`redirect_checker.py` still sees the hop it exists to report.

### When a script does not finish

A timeout and a crash both leave the item `NO_DATA`, but they are recorded apart —
`error_kind` per item, `script_failures` for the run, `T` instead of `!` in the
progress line. A timeout means the site was slow and the run is worth repeating
with a longer `--timeout`; a crash means the script is broken and repeating it
changes nothing.

### When the site cannot be read

If the entry page does not load — DNS failure, 4xx/5xx, a non-HTML response —
every check that reads the live site is `NO_DATA` with the reason, no script runs
against it, and **no score is printed at all**. Search Console items still run,
because Google's stored history does not stop existing when a site goes down.

Most evidence scripts exit 0 with an empty result when they cannot fetch
anything, and an empty result satisfies exactly the assertions this registry is
built from. Without the gate, a host that does not resolve scored **61/100 on 40
fabricated passes**.

A page that answers **200 and is not the site** is caught too: a bot-protection
challenge (a vendor fingerprint in the markup plus almost no visible text) or a
soft 404 (a title that *equals* a not-found phrase). Both are treated as
unreadable, and the offline checks are gated as well — the file parses fine, so
nothing else would stop them from grading an interstitial's twelve words. A saved
challenge page in `archive` mode used to produce 6 passes and 10 failures.

Both tests are narrow on purpose. An article that quotes
`cdn-cgi/challenge-platform`, or one titled "How to fix 404 errors", is a real
page and is still audited — refusing it would be the same bug pointing the other
way. `--no-page-guard` overrides the guard and records that it did.

### Incoming links

The Links report is the one part of Search Console with **no API at all**.
`--links-csv` reads the UI export (Search Console → Links → Export) and answers
three items: link concentration, total links, linking root domains. The rest of
the backlinks block stays manual — judging link quality needs a link index this
does not have, and a fabricated toxicity score would be worse than the silence.

| Mode | Reaches | Use when |
|---|---|---|
| `live` | fetch, crawl, external APIs | full audit of a reachable site |
| `page` | fetch, external APIs | one page, much faster |
| `archive` | nothing — local files only | you have a copy of the site, not a URL |

Anything a mode cannot satisfy is `N/A` and drops out of both metrics. "We did not
crawl" must never read as "the site failed".

Deliverables: `CHECKLIST-REPORT.md`, `CHECKLIST.html` (filterable; manual items are
checkboxes persisted in the browser), `LLM-QUEUE*.md`, and
`checklist-results.json`, also archived under `.seo-runs/<domain>/`.

History filenames carry milliseconds, and a run never writes over an existing
file: at second precision two `--only` runs finished inside the same second and
the second one destroyed the first — which is the run `--diff` would have compared
against. `--diff` orders history by the timestamp inside each file rather than by
its name, so a directory holding both filename formats still finds the newest, and
a history file that will not parse is skipped instead of ending the run.

## Search Console

Auth is a **service account**, not user OAuth:

1. In Google Cloud, create a service account and download its JSON key.
2. Enable the Search Console API for that project.
3. In Search Console, add the service account's `client_email` as a user on the property.
4. Save the key as `~/.config/gcloud/gsc-service-account.json`, or point
   `GSC_CREDENTIALS_PATH` at it.

The property defaults to `sc-domain:<registrable domain>` — `www.example.com` is
not a property, `example.com` is. Override with `--gsc-property` for URL-prefix
properties.

The registrable domain comes from a bundled snapshot of the [Public Suffix
List](https://publicsuffix.org/), refreshed with
`tools/refresh_public_suffix_list.py`. It is bundled, not fetched at audit time,
so a run answers the same offline and next month. The seven hard-coded suffixes it
replaced handled `example.co.uk` correctly and every platform domain wrong —
`something.github.io` became `github.io`, `myapp.vercel.app` became `vercel.app` —
so the default property was one nobody owns and every Search Console item came
back empty, which reads as a site with no search traffic.

Seven items are answered from live data: cannibalization, branded-query ownership,
reported opportunities, and — via the URL Inspection API — whether Google indexed
the page and which canonical it picked. That last one earns the setup on its own:
a page can declare `rel=canonical` to itself and still have Google choose a
different URL, and nothing in the page reveals it.

Three items report `MANUAL` even with working credentials, and this is not
missing wiring: **the Search Console API has no endpoint for manual actions, the
Index Coverage report, or mobile-usability signals.** Those exist only in the web
UI; mobile usability was withdrawn from the API in December 2023.

They are `MANUAL` rather than `NO_DATA` because they are answerable today — by a
person opening Search Console. `NO_DATA` says the audit tried and could not
decide, which invites somebody to go fix the tool. Coverage is unmoved either
way: both statuses stay in the denominator and out of the decided count.

Without a key, those items are `NO_DATA` in `live` and `page` mode — the run
could have asked and did not decide — and `N/A` only in `archive`, which makes no
network calls at all. The difference matters: `N/A` leaves the coverage
denominator, so reporting a missing key that way would raise coverage precisely
where the audit is thinnest.

Credentials are never transmitted anywhere, and Search Console data is written only
to local files. Values from `INDEXNOW_KEY` and `PAGESPEED_API_KEY` are replaced
with `<redacted>` everywhere in `checklist-results.json` and `.seo-runs/` — the
run log is built from each script's argv, so a key passed as an argument would
otherwise be written out verbatim in the file you hand to a client.

## The LLM queue is not optional

30 items cannot be settled by a script — grammar, cloaking, doorway patterns,
translation quality, ad density, whether the page was written for a reader. Left
unanswered they stay `LLM_PENDING` and cap coverage.

The report splits them into one file per **lens** — the evidence an item is
answered from, which is not the same as the checklist category it sits in. Four
agents can work concurrently, each reading its own slice once:

| Queue | Agent | Items |
|---|---|---|
| `LLM-QUEUE-copy.md` | `seo-llm-copy` | 14 |
| `LLM-QUEUE-layout.md` | `seo-llm-layout` | 11 |
| `LLM-QUEUE-locale.md` | `seo-llm-locale` | 3 |
| `LLM-QUEUE-market.md` | `seo-llm-market` | 2 |

Answer each `PASS` / `FAIL` / `WARN` / `N/A` with concrete evidence, then merge:

```bash
python3 skills/seo-checklist/scripts/checklist_report.py checklist-results.json \
    --llm-answers answers.json
```

The merge only overwrites `LLM_PENDING` items; an answer file cannot flip a verdict
a script established. When the page does not support a verdict the answer is `N/A`
— inventing a `PASS` to lift the score corrupts the one metric this exists to
protect.

## The report is written for the person paying for it

Four layers, widest audience first, in one file:

1. **What this means** — three plain sentences before any number: how many things
   were checked, how many need work, how many are quick, and how many could not be
   settled by measurement at all.
2. **Where the problems are** — a bar per category, worst first, with one line
   explaining what that group of checks is about and what it costs when it is wrong.
3. **What to do first** — one card per failing or borderline check: how bad, how
   much work, what was measured *in words*, why it matters, what to do. The
   assertion's own output is folded away under "technical detail", not deleted.
4. **Every check, with its raw evidence** — collapsed. The audit trail, unchanged.

The measurement is phrased from structured data (`measure` on each item: the
operator, the threshold, the observed value, and up to four examples), so
`summary.thin_pages = 6 (want 0)` reads as "Found 6; there should be none" and
`len(allowed_urls) = 4` names the four URLs. Printing an assertion's internals in a
client's report is the same category of mistake as showing them a stack trace: the
old report did it in every row of every table.

Explanations live in the translation files rather than the code, per category
rather than per item — sixteen texts can be kept true, and 214 would drift out of
step with a generated registry the first time an item changed.

**Client-facing reports are English-only in 0.2.0.** `--lang ru` translates the
report's own wording and all sixteen category explanations, but `item_titles` and
`item_fixes` are still empty, so item titles and recommendations come out in the
registry's English — a half-Russian document. The report says which layers are
untranslated on stderr rather than letting the reader work it out. Falling back to
English is deliberate: a reader who gets the wrong language can still act, and a
reader who gets a gap cannot.

## Politeness

An audit is a burst by construction: the runner launches its evidence scripts
concurrently, and several of them walk a sitemap or a link list inside their own
process. Requests are paced to **4 per second per host by default**, shared across
those processes through a lock file — an in-process limiter would simply let eight
scripts go at once. `--max-rps N` changes it, `--max-rps 0` removes it, and
`SEO_MAX_RPS` does the same for a script run on its own.

A `429` or `503` carrying `Retry-After` is honoured once, up to 30 seconds. Past
that the request fails and the item reports `NO_DATA` with the reason, which is
more useful than an audit that appears to hang. A `Retry-After` on any other status
is ignored — some CDNs send it on a 200, and sleeping on that would pace the audit
to somebody else's cache policy.

Two gaps in this, both recorded in [KNOWN-ISSUES.md](KNOWN-ISSUES.md) and both
about the audited site rather than the audit: **the crawlers do not consult
`robots.txt`** before requesting a page, and five of them crawl independently, so a
single audit fetches the same pages around 275 times. Pacing limits the rate, not
the volume.

## Measuring the rendered page

Font size, link distinctness, overlays and tap targets are **computed** values:
they depend on stylesheets, media queries and scripts that HTML does not settle.
Measure them in a browser (chrome-devtools MCP, one `evaluate_script` — the snippet
is in `SKILL.md`), save the numbers and pass `--rendered-json`.

`viewport.width` is required, and from a desktop render the tap-target and
mobile-interstitial keys are dropped rather than zeroed: a desktop window cannot
answer either question, and a 0 would be a verdict about a viewport nobody looked
at.

## Assertions that cannot fire

`none_matching` passes when nothing matches. So an assertion aimed at wording its
script does not emit — or emits in a different word order — reports **PASS for
every site, silently, forever**. Fifteen of the registry's twenty-one pattern
assertions were in that state, including a `critical` one about blocking CSS and
JS in robots.txt whose pattern was matching its own script's docstring.

Prefer a counted field, or a `value_map` that enumerates the script's own
vocabulary — where a value nobody mapped is `NO_DATA` rather than a pass:

```python
{"path": "rows", "field": "verdict",
 "value_map": {"self_canonical": "pass", "cross_host": "fail"}}
```

`tools/audit_assertions.py` reports any pattern that cannot match anything its
script emits, a test runs it, and CI fails on it.

## Core Web Vitals: field and lab, never merged

`pagespeed.py` reports CrUX **field** data — what real visitors experienced. That
is the better evidence and it answers SP-108 and SP-113 whenever it exists. It does
not exist for low-traffic URLs.

For those, measure the page locally with the chrome-devtools MCP, write the
numbers to a file and pass `--cwv-json`. SP-214/215/216 decide from it and are
`NO_DATA` without it. They are **separate items on purpose**: one controlled run on
your machine is a different claim from what visitors got, and one number standing
for both is the conflation this tool exists to avoid. TBT is reported as a lab
stand-in for INP, named as such, because INP needs a real interaction.

Units live in the key names (`lcp_ms`, `tbt_ms`, unitless `cls`) — a bare `lcp` of
2.1 could be seconds or milliseconds, and guessing wrong turns a failing page into
a passing one, so the file is refused instead.

## A second reading of the LLM verdicts

`--llm-review` folds in an independent second judgement of the same items.
Agreement corroborates. Disagreement returns the item to `NO_DATA` with both
readings recorded, and coverage drops accordingly.

The reviewer cannot change a verdict, cannot touch a script's result, and cannot
answer an item the first pass left unanswered. It withdraws confidence, which is
the one thing 38 unopposed judgements had no way to express.

## Bundled playbooks

The prose half of the audit ships **inside** the plugin. Nothing here depends on
another plugin being installed, because a missing dependency degrades an audit
silently — and a silent degradation is exactly what this tool exists to prevent.

| Playbook | Covers | Items |
|---|---|---|
| `resources/playbooks/local-seo.md` | Business Profile, NAP, citations, reviews | LO-196, LO-199 |
| `resources/playbooks/competitor-research.md` | who actually ranks, with sources | CO-191…195, BL-088 |
| `resources/references/client-report-structure.md` | reshaping the report for a decision | — |

**A playbook tells you how to answer an item; it never answers one.** Reading it
does not move a status — doing the work does. `local-seo.md` cannot read the live
Business Profile, so LO-199 stays `MANUAL`. `competitor-research.md` uses
firecrawl or exa when those MCP servers are configured and falls back to the
built-in `WebSearch`; with no search tool at all, CO-191 is `N/A`, because a
competitor list written from memory is fabrication with a confident tone.
`client-report-structure.md` is presentation only and changes no number.

Two of the three are adapted from MIT-licensed work in
[Everything Claude Code](https://github.com/affaan-m/ECC); provenance and the
full notices are in [CREDITS.md](CREDITS.md).

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Everything runs offline — no live site, no API key, no Search Console property.
The suite guards the parts that fail *silently*: an assert rule using an operator
the runner never implemented, a pattern that cannot fire, a script the registry
names but nobody shipped, an LLM item with no lens, a profile that hides a critical
check, and the boundary between "failed", "could not be decided" and "out of scope"
that every metric here depends on.

Three of them guard documentation rather than code, because a document that has
gone stale beside working code is its own kind of silent failure: the manifest
version must have a `CHANGELOG.md` entry naming the shipped `registry_version`, the
200 borrowed titles must record their source in the file that holds them, and every
category in the registry must have a plain-language explanation in every shipped
language. CI runs the suite on Python 3.11 and 3.13 along with the gates and four
end-to-end audits.

## Extending the registry

```bash
S=skills/seo-checklist
python3 $S/tools/build_checklist.py          # rewrite checklist.json
python3 $S/tools/build_checklist.py --check  # CI: fail if stale
```

Edit `tools/build_checklist.py`, never `checklist.json` directly. Two rules:

1. **Write assertions only against observed script output.** Capture it with
   `tools/probe_shapes.py` and consult
   `resources/references/script-output-shapes.md`. A guessed JSON path produces a
   rule that silently reports `NO_DATA` forever.
2. **Every LLM item needs a lens.** The build refuses without one — otherwise a new
   item belongs to no agent and quietly never gets answered.

Absence of a field is `NO_DATA`, not `PASS`. An item passes on absence only when
its rule says `missing_is: pass`: a parser that never emits a key must not be read
as the site being clean.

## Credits

See [CREDITS.md](CREDITS.md) for provenance and third-party licences: the Plerdy
checklist, the Agentic-SEO evidence scripts, and the two playbooks adapted from
Everything Claude Code.
