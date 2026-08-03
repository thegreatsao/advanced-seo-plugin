---
name: seo-checklist
description: >
  Deterministic SEO audit against a fixed 211-item registry. Every item gets a
  status and nothing is silently skipped, so two audits of the same site check
  the same things. Use when the user asks for a checklist audit, a full SEO
  checklist, reproducible coverage, a comparison against a previous run, or an
  audit of local site files rather than a live URL.
---

# Checklist Audit

`resources/config/checklist.json` holds **211 items** — the Plerdy 200-point
checklist plus 11 checks it does not cover (GEO/AI search, `llms.txt`, AI-crawler
policy, IndexNow, schema guards). Each item names what answers it: a script and an
assertion over that script's output, a Search Console call, a language-model
judgement, or a human.

The registry is the point. Coverage is a contract, not whatever the model
remembered to run.

## Run it

```bash
# full audit of a live site
python3 <SKILL_DIR>/scripts/checklist_runner.py <url>

# single live page, no crawling (fast)
python3 <SKILL_DIR>/scripts/checklist_runner.py <url> --mode page

# local copy of a site, no network at all
python3 <SKILL_DIR>/scripts/checklist_runner.py <url> --archive ./site-backup

# compare against the previous run for this domain
python3 <SKILL_DIR>/scripts/checklist_runner.py <url> --diff

# narrow the registry to what this kind of site can be judged on
python3 <SKILL_DIR>/scripts/checklist_runner.py <url> --profile ecommerce

# judge page-level checks across several pages instead of one
python3 <SKILL_DIR>/scripts/checklist_runner.py <url> --sample 10

# answer the incoming-link items from a Search Console Links export
python3 <SKILL_DIR>/scripts/checklist_runner.py <url> --links-csv ~/Downloads/Links.zip

# render the deliverables (add --lang ru for a Russian report)
python3 <SKILL_DIR>/scripts/checklist_report.py checklist-results.json
```

## Site profiles

`--profile` narrows the registry to what a given kind of site can actually be
judged on: `default`, `local`, `ecommerce`, `saas`, `blog`, `media`. An excluded
item reports `N/A` with the profile as the reason and leaves both metrics alone.

**Ask the user which profile to use before the first run of a session, unless
they already said what kind of site it is.** Offer the six names with their
one-line descriptions and let them pick; then pass the answer as `--profile` so
the run is not left guessing. If the user's request already makes it obvious —
"audit my shop", "our SaaS landing page", "the blog" — take that as the answer
and say which profile you chose rather than asking again.

To answer with evidence rather than a guess, run the detector on the entry page
first and put its suggestion in the question:

```bash
python3 <SKILL_DIR>/scripts/detect_profile.py <url> --json
```

It reads structured data, platform fingerprints and cart/pricing markup — never
wording, which is the first thing that lies: a plumber's nav says "shop" and a
store's homepage says "about our family business". Report the suggestion with the
signals behind it and the confidence, and let the user correct it. When the
evidence is thin the detector says so and suggests `default`, which is the right
answer rather than a shrug.

Do not skip the question and default silently. `default` runs the full registry,
so nothing is hidden by it, but a local business audited under `default` collects
storefront failures it can never fix, and the priority list fills with noise.

The runner does the same thing on its own: it fetches the entry page **before**
settling the profile (one request, not two — archive mode uses its local file),
detects, then asks with the suggestion pre-selected so Enter accepts it. The
signals and the confidence are shown, and a close second is flagged as "the guess
is not clear-cut".

`--profile auto` accepts the detection without asking — the one way a heuristic
is allowed to narrow scope, because passing the flag is itself a decision.

Passing any other `--profile` disables the prompt entirely. The script asks only
when a terminal is attached; in CI, cron and background runs it uses `default`,
mentions what detection would have suggested, and prints why it did not act on
it. `--no-prompt` forces that behaviour anywhere.

Exclusions are deliberately conservative, and no profile may exclude a
`critical` item — a test enforces that. Narrowing scope must never become a way
to raise the score by hiding hard failures.

An unknown profile name is an error, not a fallback to `default`: quietly
auditing a store as a blog would drop the storefront checks and lift the score
for the wrong reason. Every non-answer resolves to the **widest** scope, never a
narrower one.

## Auditing several pages

`--sample N` collects up to N same-host URLs — sitemap first, on-page links
second — and runs the **page-level** checks (`requires` of `offline` or `fetch`)
against each. Site-level checks still run once.

Aggregation takes the worst verdict, because a check failing on any sampled page
fails for the site, but the evidence always carries the count: `3/8 pages: ...`
never reads the same as every page. When no second URL can be found the run says
so and audits the single page rather than pretending to have sampled.

Only real pages enter the sample. Candidates come from `<a href>` alone, asset
extensions are rejected by path, and anything whose `Content-Type` is not a page
is dropped at fetch time with the reason printed. This matters more than it
looks: a stylesheet sampled as a page fails every page-level check, and the worst
verdict wins — one asset in the sample would condemn the whole site.

## Incoming links

The Links report is the one part of Search Console with **no API at all**, so
`--links-csv` takes the export instead: Search Console → Links → Export. Three
items are answered from it — link concentration (BL-084), total links (BL-086)
and linking root domains (BL-087). The rest of the backlinks block stays manual
because judging link quality needs a link index this does not have, and a
fabricated toxicity score would be worse than the silence.

Scripts need `requests` + `beautifulsoup4` + `lxml`. Search Console additionally
needs `google-auth` and `google-api-python-client`.

## Run modes

| Mode | Capabilities | Use when |
|---|---|---|
| `live` (default) | offline + fetch + crawl + external APIs | full audit of a reachable site |
| `page` | offline + fetch + external APIs | one page, no crawl — much faster |
| `archive` | offline only | you have files, not a URL; zero network calls |

Each item declares what it `requires`. Anything a mode cannot satisfy is reported
**`N/A`** and drops out of *both* metrics — "we did not crawl" must never read as
"the site failed".

Search Console is the one capability that can be missing for two different
reasons, and they are not the same status. In `archive` — a mode that promises no
network at all — its items are **`N/A`**, genuinely out of scope. In `live` or
`page` **without a key** they are **`NO_DATA`**: the run could have asked and did
not manage to decide. Calling the second one `N/A` would drop seven items out of
the coverage denominator and raise coverage exactly where the audit is thinnest.

## When the site cannot be read

If the entry page does not load — DNS failure, 4xx/5xx, a non-HTML response —
every check that reads the live site (`requires` of `fetch`, `crawl` or `api`) is
`NO_DATA` with the reason attached, **no script is run against it, and no score
is reported at all**. Search Console items still run: Google's stored history
does not stop existing because the site is down today.

This is not a nicety. Most evidence scripts exit 0 with a well-formed empty
result when they cannot fetch anything, and an empty result satisfies exactly the
assertions this registry is built from — `errors = 0`, `duplicates = 0`, no match
for a warning pattern. Before the gate, a run against a host that does not
resolve returned **61/100 on 40 fabricated passes**. `missing_is` cannot catch
this: the key is present and its value is zero.

What it does **not** catch: a bot-protection challenge or a soft 404 answers 200
with real HTML, and at this level is indistinguishable from the site. If a live
audit comes back implausibly clean, check what was actually served.

## Statuses

`PASS` · `FAIL` · `WARN` (counts as half) · `NO_DATA` (ran, could not decide) ·
`LLM_PENDING` · `MANUAL` · `N/A` (out of scope for this mode).

Absence of a field is `NO_DATA`, not `PASS`. An item only passes on absence when
its rule sets `missing_is: pass` — a parser that never emits a key must not be
read as the site being clean.

## Secrets

`checklist-results.json` and everything under `.seo-runs/` is what gets shared —
with a client, in a ticket, in a repo — and the run log is built from each
script's argv, so a key passed as an argument lands in it verbatim. Values taken
from `INDEXNOW_KEY` and `PAGESPEED_API_KEY` are replaced with `<redacted>`
throughout the payload before anything is written. Credential *paths* are not
secrets and stay readable.

## Two metrics, never one

- **SEO Score** — passed checks among those actually decided, weighted by severity
- **Coverage** — how many applicable items could be decided at all

Always report both. A 96/100 over 19% coverage (typical for `archive` mode) is not
a good site, it is a thin audit.

## Search Console

Auth is a **service account**, not user OAuth. Credentials are discovered in
order: `--gsc-credentials` → `GSC_CREDENTIALS_PATH` → `GV_SA_KEY` →
`~/.config/gcloud/gsc-service-account.json`. Grant access by adding the service
account's `client_email` as a user on the property.

The property defaults to `sc-domain:<registrable domain>` — note that
`www.example.com` is not a property, `example.com` is. Override with
`--gsc-property` for URL-prefix properties.

```bash
python3 <SKILL_DIR>/scripts/checklist_runner.py https://example.com/page \
    --gsc-property sc-domain:example.com
```

Seven items are answered from live GSC data: MS-023 and KW-071 (cannibalization),
KW-070 and GO-139 (branded-query ownership), GO-134 (reported opportunities), and
CI-010 and GO-135 through the URL Inspection API — Google's chosen canonical and
the page's indexing state. CI-010 is the one worth the setup: a page can declare
`rel=canonical` to itself and still have Google pick another URL, and nothing in
the page reveals the disagreement.

Three items stay `NO_DATA` even with valid credentials, and that is not missing
wiring — **the Search Console API exposes no endpoint for manual actions
(GO-141), the Index Coverage report (GO-142), or mobile-usability signals
(MB-099).** Those exist only in the web UI; mobile usability was withdrawn from
the API in December 2023. The Links report is UI-only too, which is why backlinks
stay manual.

GSC is offered only by modes allowed to reach external services. In `archive`
mode a key sitting on disk is ignored and those items report `N/A` — "no network
calls at all" has to hold even when credentials happen to be present.

## Mandatory: answer the LLM queue

`checklist_report.py` writes `LLM-QUEUE.md` — items no script can judge (grammar,
cloaking, doorway pages, translation quality, ad density, people-first content).
**These are not optional.** Left alone they stay `LLM_PENDING` and cap coverage.

It also writes one file per **lens** — the evidence an item is answered from,
which is not the same as the checklist category it sits in. Four agents can run
concurrently, each reading its own slice of the page once:

| Queue file | Agent | Items |
|---|---|---|
| `LLM-QUEUE-copy.md` | [seo-llm-copy](resources/agents/seo-llm-copy.md) | 14 — prose quality, originality, intent match |
| `LLM-QUEUE-layout.md` | [seo-llm-layout](resources/agents/seo-llm-layout.md) | 11 — ads, pop-ups, cloaking, navigation |
| `LLM-QUEUE-locale.md` | [seo-llm-locale](resources/agents/seo-llm-locale.md) | 3 — translation, language/region targeting |
| `LLM-QUEUE-market.md` | [seo-llm-market](resources/agents/seo-llm-market.md) | 2 — competitors, local-traffic need |

Splitting by lens rather than by category is deliberate: 16 category agents would
have four of them re-reading the same body copy. Answering the combined
`LLM-QUEUE.md` in one pass is equally valid — the split is for throughput, not
for correctness.

1. Read the actual page content — do not rule from the URL or the queue file alone.
2. Answer each item `PASS` / `FAIL` / `WARN` / `N/A`, with a concrete reason.
3. When the page does not support a verdict, answer `N/A` and say so. Never invent
   a `PASS` to raise the number.
4. Save verdicts as `{"<id>": {"status": "...", "evidence": "..."}}` and merge:
   `checklist_report.py checklist-results.json --llm-answers answers.json`

The merge only overwrites `LLM_PENDING` items — it cannot flip a verdict a script
already established.

## Bundled playbooks

The prose half of the audit ships **inside** the plugin, so it behaves the same
on any machine. Nothing here depends on another plugin being installed. Map:
[playbooks.json](resources/config/playbooks.json); provenance and licences:
`CREDITS.md`.

| Playbook | Use it for | Items |
|---|---|---|
| [local-seo.md](resources/playbooks/local-seo.md) | Business Profile, NAP, citations, reviews | LO-196, LO-199 |
| [competitor-research.md](resources/playbooks/competitor-research.md) | who actually ranks, with sources | CO-191…195, BL-088 |
| [client-report-structure.md](resources/references/client-report-structure.md) | reshaping the report for a decision | — |

**A playbook tells you how to answer an item. It never answers one.** Reading a
playbook does not move a status; doing the work does.

**local-seo** — read when the profile is `local`, or when `seo-llm-market`
answers LO-196 `PASS`. It cannot read the live Business Profile, so LO-199 stays
`MANUAL`; what changes is that the person doing the work gets categories, photo
cadence and citation targets instead of an item title.

**competitor-research** — read while answering CO-191. It uses firecrawl or exa
if those MCP servers are configured and falls back to `WebSearch`/`WebFetch` if
not. If no search tool is available at all, CO-191 is `N/A` — a competitor list
assembled from memory is fabrication with a confident tone.

**client-report-structure** — read when the audit is going to a client. It is
**presentation only**: no status, score or coverage number changes because a
report was reshaped. Run it after the LLM queue is answered.

## Deliverables

- `CHECKLIST-REPORT.md` — summary, priority actions, full checklist, manual items, undetermined items
- `CHECKLIST.html` — filterable view; `MANUAL` items are checkboxes persisted in localStorage
- `LLM-QUEUE.md` + one file per lens — the model's work list
- `checklist-results.json` — machine-readable; also archived to `.seo-runs/<domain>/<timestamp>.json`

Every result carries the `registry_version` it was produced from. `--diff` warns
when two runs came from different registry versions, profiles or modes — without
that, "no status changes" could mean the checklist itself changed underneath.

Priority actions are ranked by severity **against effort**, not severity alone:
ranking by severity puts a week of rewriting above a one-line meta tag. Effort is
a per-category heuristic, not a per-item estimate.

## Extending the registry

```bash
python3 <SKILL_DIR>/tools/build_checklist.py          # rewrite checklist.json
python3 <SKILL_DIR>/tools/build_checklist.py --check  # CI: fail if stale
python3 -m unittest discover -s tests                 # registry + runner + report
```

Edit `tools/build_checklist.py`, never `checklist.json` directly. Two rules:

1. **Write assert rules only against observed script output.** Capture it with
   `tools/probe_shapes.py` and consult
   [script-output-shapes.md](resources/references/script-output-shapes.md).
   A guessed JSON path produces a rule that silently reports `NO_DATA` forever.
2. **Every LLM item needs a lens.** The build refuses without one — otherwise a
   new item belongs to no agent and quietly never gets answered.
