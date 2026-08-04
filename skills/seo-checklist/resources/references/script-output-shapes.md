<!-- Updated: 2026-08-02 -->
# Script output shapes

All 52 scripts the registry runs are documented here. Four of them break the
`issues[].severity` + `message` convention the rest share — `gsc_checker.py` and
`indexnow_checker.py` capitalise severity, `indexnow_checker.py` uses `finding`
instead of `message`, and `robots_path_tester.py` emits no `issues[]` at all.
Check the section before writing a rule.

Machine-probed JSON structure of the evidence scripts, captured by running each one
with `--json` against a live URL (https://www.plerdy.com/seo-checklist/, WordPress).
The Search Console scripts were probed separately against a property the key can
read (`sc-domain:greenvalleymoletai.lt`), since they address a property rather than
the audited URL. `checklist.json` assert rules are written against these paths —
re-probe with `tools/probe_shapes.py` after changing any script's output contract.

```bash
python3 tools/probe_shapes.py <url>                       # everything
PROBE_ONLY=html_validator.py,ga4_tag_checker.py \
    python3 tools/probe_shapes.py <url>                   # just what changed
PROBE_GSC_PROPERTY=sc-domain:example.com \
    python3 tools/probe_shapes.py <url>                   # include GSC scripts
```

**Universal pattern:** almost every script returns an `issues[]` array whose items carry
`severity` (`critical`/`high`/`medium`/`low`) plus `message`. Checklist rules lean on this
rather than on per-script bespoke fields wherever possible.

**Scripts exposing a 0-100 `score`:** security_headers, social_meta, eeat_signal_checker,
freshness_checker, answer_block_scanner, citation_readiness, a11y_seo_checker,
topical_cluster_mapper, llms_txt_checker (`quality.score`), pagespeed (`performance_score`).

## Runtime (single page, cold)

| Script | Note |
|---|---|
| `duplicate_content.py` | ~55s — crawls 50 pages |
| `orphan_pages_from_sitemap.py` | ~49s — pulls the full sitemap |
| `pagespeed.py` | ~19s — external PageSpeed API |
| `anchor_text_audit.py` | ~12s — crawls 25 pages |
| `external_link_quality.py` | ~10s — checks every outbound link |
| `indexability_matrix.py`, `sitemap_checker.py`, `broken_links.py` | ~6-8s |
| everything else | < 1.5s |

Slow scripts must run first in the pool so they overlap the fast ones.

## Scripts needing extra required args

| Script | Missing | Handling |
|---|---|---|
| `robots_path_tester.py` | positional `paths` | registry passes `/search /cart /checkout /login` |
| `indexnow_checker.py` | `--key` | optional; `NO_DATA` unless key configured |
| `competitor_gap.py` | `--competitor` | LLM/user supplies competitor URL |
| `content_decay_detector.py` | crashes without input data | needs GSC export; `NO_DATA` otherwise |
| `validate_schema.py` | exits 0 with empty stdout | use `schema_required_props.py` instead |

---

## Per-script structure

### a11y_seo_checker.py

`url` — str
`score` — int
`checks.h1_count` — int
`checks.lang` — str
`checks.viewport` — bool
`checks.images_missing_alt` — int
`checks.form_controls` — int
`checks.labeled_controls` — int
`checks.landmarks.main` — int
`checks.landmarks.nav` — int
`checks.landmarks.header` — int
`checks.landmarks.footer` — int
`checks.inline_contrast_candidates` — int
`issues[]` — array
  - item keys: severity, message
`fetch_error` — NoneType

### ai_crawler_policy_matrix.py

`site` — str
`robots_url` — str
`robots_status` — int
`llms_txt_url` — str
`llms_txt_status` — int
`rows[]` — array
  - item keys: crawler, policy, paths, llms_txt_available, alignment

### anchor_text_audit.py

`start_url` — str
`pages_crawled` — int
`links_analyzed` — int
`summary.unique_targets` — int
`summary.empty_anchors` — int
`summary.generic_anchors` — int
`summary.nofollow_internal_links` — int
`summary.overused_exact_match_targets` — int
`summary.low_diversity_targets` — int
`top_anchor_texts[]` — array
  - item keys: anchor, count
`targets[]` — array
  - item keys: target, total_internal_links, unique_anchor_texts, diversity_ratio, top_anchor, top_anchor_count
`examples.empty_anchors[]` — array
  - item keys: source, target, anchor, rel, nofollow
`examples.generic_anchors[]` — array
`examples.nofollow_internal_links[]` — array
  - item keys: source, target, anchor, rel, nofollow
`examples.overused_exact_match_targets[]` — array
  - item keys: target, total_internal_links, unique_anchor_texts, diversity_ratio, top_anchor, top_anchor_count
`examples.low_diversity_targets[]` — array
  - item keys: target, total_internal_links, unique_anchor_texts, diversity_ratio, top_anchor, top_anchor_count
`issues[]` — array
  - item keys: severity, type, count, message
`fetch_errors[]` — array

### answer_block_scanner.py

`url` — str
`score` — int
`questions[]` — array
`direct_answers[]` — array
`definitions[]` — array
`lists[]` — array
  - item keys: type, items, sample
`tables[]` — array
`issues[]` — array
  - item keys: severity, message
`fetch_error` — NoneType

### article_seo.py

`url` — str
`cms_detected` — str
`title` — str
`meta_description` — str
`og_description` — str
`author` — str
`publish_date` — str
`labels[]` — array
`headings.h1[]` — array
`headings.h2[]` — array
`headings.h3[]` — array
`paragraphs[]` — array
`images[]` — array
  - item keys: src, alt, width, height, loading
`structured_data[]` — array
  - item keys: @type, @context, status, note, has_context, has_type, raw
`readability.flesch_reading_ease` — float
`readability.fkgl` — float
`readability.grade_label` — str
`readability.word_count` — int
`readability.sentence_count` — int
`readability.avg_sentence_length` — float
`readability.avg_syllables_per_word` — float
`target_keyword` — str
`extracted_keywords[]` — array
`related_keywords[]` — array
`seo_issues[]` — array
  - item keys: severity, area, finding, fix

### broken_links.py

`page_url` — str
`total_links` — int
`checked` — int
`broken[]` — array
  - item keys: url, anchor_text, is_internal, status, error, redirect, response_time_ms
`redirected[]` — array
  - item keys: url, anchor_text, is_internal, status, error, redirect, response_time_ms
`timeout[]` — array
`healthy` — int
`summary.total` — int
`summary.healthy` — int
`summary.broken` — int
`summary.redirected` — int
`summary.timeout` — int
`issues[]` — array
`error` — NoneType

### cache_compression_checker.py

`url` — str
`resources_checked` — int
`issues[]` — array
`resources[]` — array
  - item keys: url, status, content_type, content_encoding, cache_control, etag, vary, content_length, issues, error
`fetch_error` — NoneType

### canonical_checker.py

`count` — int
`rows[]` — array
  - item keys: url, status, final_url, canonical, verdict, issues
`issues[]` — array

### citation_readiness.py

`url` — str
`score` — int
`factual_claims` — int
`claim_samples[]` — array
`citation_signals.external_links` — int
`citation_signals.trusted_external_links` — int
`citation_signals.cite_or_blockquote_tags` — int
`citation_signals.footnote_links` — int
`entity_signals.types[]` — array
`entity_signals.names[]` — array
`entity_signals.sameAs[]` — array
`issues[]` — array
  - item keys: severity, message
`fetch_error` — NoneType

### collection_page_checker.py

`source` — str
`final_url` — str
`status` — int
`word_count` — int
`filter_parameters[]` — array
`product_links_detected` — int
`issues[]` — array
  - item keys: severity, message, url, evidence

### critical_request_chain.py

`url` — str
`critical_request_count` — int
`chain_count` — int
`issues[]` — array
  - item keys: severity, message, url
`chains[]` — array
  - item keys: type, url, blocking, preloaded, cross_origin, children
`fetch_error` — NoneType

### css_minify_check.py

`url` — str
`stylesheets[]` — array
  - item keys: href, bytes, minified (bool), ratio (float — bytes per line, the
    minification heuristic), status, error
`checked` — int
`unminified_count` — int
`wasted_bytes` — int
`issues[]` — array
`fetch_error` — str | null

Observed on plerdy: 5 stylesheets checked, 3 unminified, 51999 wasted bytes.

### detect_profile.py

Not run by the registry — the runner calls it in-process before the profile
question, and it is also a standalone CLI. Requires `offline`: it reads HTML you
already have (`--html`) or fetches one page.

`url` — str
`profile` — str, one of the profile names or `default`
`confidence` — str (`high` / `low` / `none`)
`scores` — object, one int per profile (`ecommerce`, `local`, `saas`, `blog`, `media`)
`signals` — object, one array of human-readable reasons per profile
`runner_up` — object | null — `{profile, score}` when the top two are close
`error` — str | null

`profile` is `default` with confidence `none` whenever the top score falls below
the threshold: thin evidence produces a refusal to narrow anything, not a guess.
`runner_up` is populated only when the margin is small, which is what turns the
suggestion from `high` to `low` confidence.

Observed on a lakeside resort: `local` at 8 (Restaurant schema, opening hours,
click-to-call), `ecommerce` at 2 (price markup), confidence `high`.

### domain_safety_check.py

`url` — str
`domain` — str
`uptime.checked` — bool
`uptime.reachable` — bool
`uptime.status` — int
`uptime.response_ms` — int
`uptime.error` — str | null
`safe_browsing.checked` — bool
`safe_browsing.error` — str
`whois.checked` — bool
`whois.created` — str (`YYYY-MM-DD`)
`whois.registrar` — str
`whois.queried` — str — the registrable domain actually queried, which is not the
  audited host: asking whois about `www.plerdy.com` returns the `.com` zone record
`whois.age_days` — int
`neighbors.checked` — bool
`neighbors.ip` — str
`issues[]` — array

Two fields are **never** populated without extra setup, and no rule should assume
them. `safe_browsing.matches` appears only when `GOOGLE_SAFE_BROWSING_KEY` is set —
unobserved, so do not write rules against its shape. `neighbors.suspicious` is
deliberately never fabricated, because enumerating co-hosted domains needs a paid
reverse-IP service. Both report `checked: false` with a reason instead.

### duplicate_content.py

`pages_analyzed` — int
`exact_duplicates[]` — array
  - item keys: type, severity, urls, finding, fix
`near_duplicates[]` — array
`thin_content[]` — array
  - item keys: type, severity, url, word_count, threshold, finding, fix
`summary.exact_duplicate_groups` — int
`summary.near_duplicate_pairs` — int
`summary.thin_pages` — int
`summary.avg_word_count` — int

### eeat_signal_checker.py

`url` — str
`score` — int
`signals.authors[]` — array
`signals.credential_markers[]` — array
`signals.first_hand_experience_markers[]` — array
`signals.policy_links[]` — array
  - editorial standards only: fact-checking, corrections, ethics. Not privacy.
`signals.privacy_links[]` — array
  - privacy, data protection, GDPR, cookie policy. CN-040 reads this; it used to
    read `policy_links`, which answered a different question in both directions.
`signals.trust_links[]` — array
  - the loosest of the three: anything institutional, an "About" page included.
  - item keys (all three arrays): href, text, rel
`signals.external_citations` — int
`issues[]` — array
  - item keys: severity, message
`fetch_error` — NoneType

### entity_checker.py

`url` — str
`entity_name` — str
`entities_in_schema[]` — array
  - item keys: type, name, url, sameAs, logo, description, identifier
`sameas_analysis.issues[]` — array
`sameas_analysis.total_found` — int
`sameas_analysis.total_missing_critical` — int
`wikidata.found` — bool
`wikidata.qid` — NoneType
`wikidata.url` — NoneType
`wikipedia.found` — bool
`wikipedia.url` — NoneType
`google_kg.checked` — bool
`google_kg.found` — bool
`google_kg.result` — NoneType
`nap_issues[]` — array
`issues[]` — array
  - item keys: severity, area, finding, fix
`summary.entities_found` — int
`summary.sameas_count` — int
`summary.sameas_missing_critical` — int
`summary.wikidata_found` — bool
`summary.wikipedia_found` — bool
`summary.google_kg_checked` — bool
`summary.google_kg_found` — bool
`summary.total_issues` — int

### external_link_quality.py

`sources[]` — array
`pages[]` — array
  - item keys: url, status, error
`summary.external_links_found` — int
`summary.unique_external_links` — int
`summary.checked_links` — int
`summary.broken_links` — int
`summary.redirecting_links` — int
`summary.low_trust_pattern_links` — int
`summary.commercial_rel_review` — int
`top_external_hosts[]` — array
  - item keys: host, count
`links[]` — array
  - item keys: source, url, anchor, rel, nofollow, sponsored, ugc, host, low_trust_pattern, status, final_url, redirect_chain
`issues[]` — array
  - item keys: severity, type, count, message
`errors[]` — array

### faceted_nav_audit.py

`count` — int
`rows[]` — array
  - item keys: url, path, params, facet_params, flags
`issues[]` — array

### font_audit.py

`url` — str
`font_file_count` — int
`font_face_count` — int
`preload_count` — int
`preconnect_count` — int
`issues[]` — array
`fonts[]` — array
`font_faces[]` — array
`fetch_error` — NoneType

### freshness_checker.py

`url` — str
`score` — int
`latest_date` — str
`age_days` — int
`dates[]` — array
  - item keys: source, raw, date
`old_years[]` — array
`stale_stat_sentences` — int
`schema_date_mismatch` — bool
`issues[]` — array
  - item keys: severity, message
`fetch_error` — NoneType

### ga4_tag_checker.py

`url` — str
`measurement_ids[]` — array of str (e.g. `G-15X5JYHSHC`)
`gtm_containers[]` — array of str
`ua_legacy[]` — array of str — retired `UA-` properties still on the page
`duplicates[]` — array — the same ID configured more than once
`loaders.gtag_js` — int
`loaders.gtm_js` — int
`issues[]` — array
`fetch_error` — str | null

### gsc_cannibalization.py

Requires `gsc` capability. Probed against `sc-domain:greenvalleymoletai.lt`.

`property` — str
`period.start` / `period.end` — str (`YYYY-MM-DD`)
`queries_analyzed` — int
`cannibalized[]` — array
  - item keys: query, pages[] (page, clicks, impressions, position), page_count,
    clicks, impressions, spread (float — max minus min position)
`branded.checked` — bool
`branded.query` / `branded.owner_page` / `branded.host` — str
`branded.position` — float
`branded.clicks` — int
`branded.owns_homepage` — bool
`branded.ranks_first` — bool
`summary.cannibalized_queries` — int
`summary.worst_spread` — float
`issues[]` — array
`error` — str | null

When the range holds no query data, `branded` collapses to
`{checked: false, reason: "..."}` and the sub-fields are absent — so rules on
`branded.*` yield `NO_DATA`, not a verdict.

### gsc_checker.py

Requires `gsc` capability.

`site_url` — str
`days` — int
`performance.period` — str (`YYYY-MM-DD to YYYY-MM-DD`)
`performance.total_rows` — int
`performance.data[]` — array
  - item keys: query, page, clicks, impressions, ctr, position
`opportunities[]` — array
  - item keys: type, severity, query, page, position, impressions, finding, fix
`top_pages[]` — array
  - item keys: page, clicks, impressions, ctr, position
`sitemaps[]` — array
  - item keys: path, type, last_submitted, last_downloaded, is_pending, errors,
    warnings, contents[]

**Severity here is capitalised** (`"High"`, not `"high"`) — unlike every other
script. `none_severity` lowercases both sides, so existing rules match; a rule
written with a raw string comparison would silently never fire.

### gsc_links_csv.py

Requires `offline` — it reads a file you exported, so even `archive` mode can use
it. Probed against a two-sheet export (top linking sites, top linking text).

`source` — str, absolute path of the export
`site` — str, whatever was passed as `--site`
`linking_domains` — int
`total_links` — int
`top_sites[]` / `anchors[]` / `top_linked_pages[]` — arrays, capped at 50
  - item keys: name, count
`anchor_profile.branded` / `.generic` / `.other` / `.classified` — int
`concentration.top1_share_pct` — float | null
`concentration.top10_share_pct` — float | null
`note` — str | null, set when a single unnamed CSV had to be guessed at
`issues[]` — array
`error` — str | null

The Links report has **no API** — not in v3, not in v1. This parses the UI export
and nothing else, which is why the incoming-link items report `NO_DATA` until
`--links-csv` is passed. Both `concentration` fields are null when the export
carried no linking-sites sheet, so rules on them stay undecided rather than
passing on an empty file.

### gsc_url_inspection.py

Requires `gsc` capability. Addresses a page, so it takes both the URL and the
property. Quota: 2000 inspections per property per day.

`inspected_url` / `property` — str
`verdict` — str (`PASS` / `NEUTRAL` / `FAIL`)
`coverage_state` — str — prose, not an enum (`"Submitted and indexed"`)
`indexing_state` — str (`INDEXING_ALLOWED`, `BLOCKED_BY_META_TAG`, …)
`robots_txt_state` — str (`ALLOWED` / `DISALLOWED`)
`page_fetch_state` — str (`SUCCESSFUL`, …)
`last_crawl_time` — str (ISO-8601 with `Z`)
`crawled_as` — str (`MOBILE` / `DESKTOP`)
`google_canonical` / `user_canonical` — str | null
`canonical_match` — bool | null
`indexed` — bool | null
`sitemaps[]` — array of str
`referring_urls` — int
`rich_results_verdict` — str | null
`issues[]` — array
`error` — str | null

Both tri-state fields are null on purpose. `canonical_match` is null when the page
declares no canonical — there is nothing to disagree with. `indexed` is null when
the coverage wording is unrecognised, because an unfamiliar string must not be read
as "not indexed". Either way the item lands on `NO_DATA`.

### hreflang_checker.py

`url` — str
`implementation_method` — str
`hreflang_tags_found` — int
`tags[]` — array
  - item keys: lang, raw_lang, url, raw_url
`sitemap.found` — bool
`sitemap.url` — str
`sitemap.has_xhtml_namespace` — bool
`sitemap.language_variants_found[]` — array
`sitemap.note` — str
`checks.self_reference.passed` — bool
`checks.self_reference.detail` — str
`checks.x_default.passed` — bool
`checks.x_default.detail` — str
`checks.protocol_consistency.passed` — bool
`checks.protocol_consistency.detail` — str
`checks.canonical_alignment.passed` — bool
`checks.canonical_alignment.detail` — str
`language_code_issues[]` — array
`return_tag_checks[]` — array
  - item keys: passed, severity, confidence, finding, fix, alternates
`summary.critical` — int
`summary.high` — int
`summary.medium` — int
`summary.low` — int
`summary.passed` — int

### html_validator.py

W3C Nu validator (`validator.w3.org/nu/`) — free, no key.

`url` — str
`summary.errors` — int
`summary.warnings` — int
`summary.info` — int
`messages[]` — array, capped at 40
  - item keys: type (`error`/`info`/`warning`), subType, message, line, extract
`issues[]` — array
`error` — str | null

Observed on plerdy: 484 errors, 0 warnings, 517 info. Counts in the hundreds are
normal for a WordPress theme, so rules should target `summary.errors` thresholds
rather than demanding zero.

### rendered_audit.py

Reads a JSON file of measurements taken from a rendered page (chrome-devtools MCP
`evaluate_script`); takes no URL and makes no request. Registry args:
`["{rendered_json}"]`, so without `--rendered-json` the placeholder is unresolved
and CN-034/035/051, MB-094 and MB-103 report NO_DATA.

`url` — str or null
`source` — str — `"unspecified"` when the file did not say
`viewport.width` — number — **required**; the file is refused without it
`viewport_class` — str — `mobile` when width ≤ 480, else `desktop`
`measured[]` / `missing[]` — arrays of str
`text_nodes_below_12px` — int — CN-034
`links_indistinct` — int — CN-035 (neither underlined, nor bolder, nor a different
  colour from the parent)
`overlays_covering_content` — int — CN-051 (fixed/sticky elements covering ≥25% of
  the viewport)
`tap_targets_below_48px` — int — MB-103, **mobile renders only**
`mobile_overlays_covering_content` — int — MB-094, **mobile renders only**; derived
  from `overlays_covering_content`

From a desktop render the two mobile keys are dropped rather than zeroed, and the
`missing[]` entry says how wide the render was. A desktop window cannot answer a
question about tap targets, and a 0 would be a verdict about a viewport nobody
looked at.

### cwv_metrics.py

Reads a JSON file written from a browser performance trace (chrome-devtools MCP);
takes no URL and makes no request. Registry args: `["{cwv_json}"]`, so without
`--cwv-json` the placeholder is unresolved and SP-214/215/216 report NO_DATA.

`url` — str or null (whatever the trace file recorded)
`source` — str — free text describing the trace; `"unspecified"` when absent
`measured[]` — array of str — which metrics the file carried
`missing[]` — array of str — which it did not
`lcp_ms` — int/float — **absent** when not measured
`cls` — float — absent when not measured
`tbt_ms` — int/float — absent when not measured
`<metric>_rating` — str — `good` | `needs_improvement` | `poor`
`all_good` — bool — over the measured metrics only

Absent rather than zero, deliberately: a metric nobody measured must not read as a
perfect score. Units live in the key names because a bare `lcp` of 2.1 could be
seconds or milliseconds, and guessing wrong turns a failing page into a passing
one — the script refuses the file instead.

### image_inventory.py

`url` — str
`count` — int
`missing_alt` — int
`summary.images` — int
`summary.lazy_lcp_candidates` — int — added for CN-054, which used to look for
  this by matching the issue text. Counted, so it cannot be reworded.
`issues[]` — array
  - item keys: severity, message, url
`images[]` — array
  - item keys: src, alt, has_alt, width, height, is_responsive_fill, loading, srcset, sizes, format, likely_lcp_candidate
`fetch_error` — NoneType

### image_weight_audit.py

`url` — str
`image_count` — int
`images_status_checked` — int — 0 unless `--fetch-images` was passed
`broken_image_count` — int — **absent** when `images_status_checked` is 0. MD-187
  asserts `eq: 0` on it, and an absent key is NO_DATA: reporting 0 because nothing
  was fetched would turn "we did not look" into "nothing is broken". `None` would
  be worse still — an equality assertion reads it as a failure.
`broken_images[]` — array of str — absent under the same condition
`known_image_bytes` — NoneType
`modern_format_count` — int — images the browser can obtain in avif or webp, counting
  a `<picture><source type="image/webp">` as well as an `img` whose own src is one.
  MB-097 reads this. Until 0.7.0 only the `img` was read, so the recommended pattern
  — modern format in a `<source>`, png fallback in the `<img>` — counted as no modern
  format at all and failed the item it exists to satisfy.
`responsive_count` — int — images with a `srcset`, on the `img` or on a `<source>`
  beside it. MB-096 reads this, and it was wrong in the same direction.
`modern_format_on_img_count` — int — the narrow count: `img` src only
`srcset_on_img_count` — int — the narrow count: `img` attribute only
`picture_count` — int — images wrapped in a `<picture>` carrying a `<source>`
`issues[]` — array
  - item keys: severity, message, url
`images[]` — array
  - item keys: src, format, width, height, loading, fetchpriority, srcset, sizes,
    picture_source_count, picture_srcset, picture_modern_formats, responsive,
    modern_format, likely_lcp_candidate, status, content_length, content_type
`fetch_error` — NoneType

### indexability_matrix.py

`site` — str
`count` — int
`rows[]` — array
  - item keys: url, final_url, status, robots_allowed, robots_rule, meta_robots, x_robots_tag, canonical, in_sitemap, redirects, verdict, blockers

### indexnow_checker.py

Requires `--key`; the registry passes `{indexnow_key}` and the item reports
`NO_DATA` when none is configured. IndexNow keys are self-issued — you invent the
string and prove ownership by serving `<key>.txt` from the site root.

`url` — str
`key` — str, truncated in the output (`0000...dead`)
`checks.key_file` / `checks.meta_tag` / `checks.robots_txt` — objects
  - keys: passed (bool | null), severity, finding, fix
`issues[]` — array
  - item keys: passed, severity, finding, fix
`summary.passed` / `summary.failed` / `summary.info` — int

**No `message` field, and severity is capitalised** (`"Critical"`, `"Info"`) — this
script predates the `issues[].severity` + `message` convention the rest follow.
`passed: null` means the check is informational, not that it failed.

### internal_links.py

`start_url` — str
`domain` — str
`pages_crawled` — int
`total_internal_links` — int
`unique_pages_found` — int
`max_depth_reached` — int
`pages.https://www.plerdy.com/.outgoing_links` — int
`pages.https://www.plerdy.com/.incoming_links` — int
`pages.https://www.plerdy.com/ab-testing-tool.outgoing_links` — int
`pages.https://www.plerdy.com/ab-testing-tool.incoming_links` — int
`pages.https://www.plerdy.com/user-session-recordings.outgoing_links` — int
`pages.https://www.plerdy.com/user-session-recordings.incoming_links` — int
`pages.https://www.plerdy.com/heatmap.outgoing_links` — int
`pages.https://www.plerdy.com/heatmap.incoming_links` — int
`pages.https://www.plerdy.com/smart-forms.outgoing_links` — int
`pages.https://www.plerdy.com/smart-forms.incoming_links` — int
`pages.https://www.plerdy.com/seo-checklist/.outgoing_links` — int
`pages.https://www.plerdy.com/seo-checklist/.incoming_links` — int
`anchor_texts.Website Heatmap Tool` — int
`anchor_texts.Session Replay Software` — int
`anchor_texts.Pop-Up Software` — int
`anchor_texts.A/B Testing Tool` — int
`anchor_texts.Website Feedback Tool` — int
`anchor_texts.Event Tracking Tools` — int
`anchor_texts.Website Funnel Analysis` — int
`anchor_texts.Ecommerce Analytics` — int
`anchor_texts.SEO Checker` — int
`anchor_texts.Error Tracking Tool` — int
`anchor_texts.SERP Checker` — int
`anchor_texts.Chrome SEO Analyzer` — int
`anchor_texts.Conversion Accelerator` — int
`anchor_texts.Pricing & Plans` — int
`anchor_texts.Digital marketing` — int
`anchor_texts.Content Marketing` — int
`anchor_texts.Ecommerce` — int
`anchor_texts.Business` — int
`anchor_texts.SEO` — int
`anchor_texts.Web Design` — int
`link_distribution.min` — int
`link_distribution.max` — int

### javascript_render_audit.py

`url` — str
`raw.title` — str
`raw.meta_description` — str
`raw.canonical` — str
`raw.h1_count` — int
`raw.internal_link_count` — int
`raw.schema_count` — int
`raw.word_count` — int
`rendered` — NoneType
`diffs[]` — array
`render_error` — str
`fetch_error` — NoneType

### lcp_subparts.py

`source` — str
`final_url` — str
`mode` — str
`lcp_ms` — NoneType
`lcp_element_url` — str
`subparts.ttfb_ms` — int
`subparts.resource_load_delay_ms` — NoneType
`subparts.resource_load_duration_ms` — NoneType
`subparts.element_render_delay_ms` — NoneType
`response_headers.date` — str
`response_headers.content-type` — str
`response_headers.transfer-encoding` — str
`response_headers.connection` — str
`response_headers.cf-ray` — str
`response_headers.cf-cache-status` — str
`response_headers.age` — str
`response_headers.last-modified` — str
`response_headers.link` — str
`response_headers.server` — str
`response_headers.strict-transport-security` — str
`response_headers.vary` — str
`response_headers.cf-apo-via` — str
`response_headers.alt-svc` — str
`response_headers.cf-edge-cache` — str
`response_headers.permissions-policy` — str
`response_headers.referrer-policy` — str
`response_headers.x-content-type-options` — str
`response_headers.x-frame-options` — str
`response_headers.speculation-rules` — str
`response_headers.server-timing` — str
`response_headers.report-to` — str
`response_headers.nel` — str
`response_headers.content-encoding` — str
`confidence` — str
`notes[]` — array
`error` — NoneType

### link_profile.py

`pages_crawled` — int
`total_internal_links` — int
`total_external_links` — int
`unique_internal_targets` — int
`unique_external_domains` — int
`avg_internal_links_per_page` — float
`orphan_pages.count` — int
`orphan_pages.urls[]` — array
`dead_end_pages.count` — int
`dead_end_pages.urls[]` — array
`top_linked_pages[]` — array
  - item keys: url, inbound_links
`top_external_domains[]` — array
  - item keys: domain, links
`issues[]` — array
`site_url` — str

### llms_txt_checker.py

`url` — str
`full_url` — str
`exists` — bool
`full_exists` — bool
`status` — int
`full_status` — int
`parsed.title` — NoneType
`parsed.description` — NoneType
`parsed.sections[]` — array
`parsed.links[]` — array
`quality.score` — int
`quality.issues[]` — array
`quality.suggestions[]` — array
`error` — NoneType

### local_seo_checker.py

`source` — str
`final_url` — str
`status` — int
`local_business_nodes` — int
`phones_detected[]` — array
`map_embeds` — int
`issues[]` — array
  - item keys: severity, message, url, evidence

### mobile_render_checker.py

`source` — str
`url` — str
`fetch.input_url` — str
`fetch.url` — str
`fetch.status` — int
`fetch.headers.date` — str
`fetch.headers.content-type` — str
`fetch.headers.transfer-encoding` — str
`fetch.headers.connection` — str
`fetch.headers.cf-ray` — str
`fetch.headers.cf-cache-status` — str
`fetch.headers.age` — str
`fetch.headers.last-modified` — str
`fetch.headers.link` — str
`fetch.headers.server` — str
`fetch.headers.strict-transport-security` — str
`fetch.headers.vary` — str
`fetch.headers.cf-apo-via` — str
`fetch.headers.alt-svc` — str
`fetch.headers.cf-edge-cache` — str
`fetch.headers.permissions-policy` — str
`fetch.headers.referrer-policy` — str
`fetch.headers.x-content-type-options` — str
`fetch.headers.x-frame-options` — str
`fetch.headers.speculation-rules` — str
`fetch.headers.server-timing` — str
`fetch.headers.report-to` — str
`fetch.headers.nel` — str
`fetch.headers.content-encoding` — str
`fetch.text` — str
`fetch.bytes` — int
`fetch.redirect_chain[]` — array
`fetch.error` — NoneType
`viewport_meta` — str
`fixed_width_values[]` — array
`sticky_position_count` — int
`rendered` — NoneType
`issues[]` — array
  - item keys: severity, finding, fix
`summary.issues` — int

### orphan_pages_from_sitemap.py

`site` — str
`summary.sitemaps_checked` — int
`summary.sitemap_urls` — int
`summary.reachable_pages` — int
`summary.orphan_pages` — int
`summary.discovered_not_in_sitemap` — int
`sitemaps_checked[]` — array
`orphan_pages[]` — array
`discovered_not_in_sitemap[]` — array
`reachable_pages[]` — array
  - item keys: url, status, final_url, depth, in_sitemap
`issues[]` — array
  - item keys: severity, type, count, message
`errors.sitemap[]` — array
`errors.crawl[]` — array

### pagespeed.py

`url` — str
`strategy` — str
`performance_score` — int
`metrics.LCP.value` — int
`metrics.LCP.unit` — str
`metrics.LCP.label` — str
`metrics.LCP.rating` — str  (good | needs-improvement | poor)
`metrics.LCP.crux_category` — str  (field data only: fast | average | slow)
`metrics.INP.value` — int
`metrics.INP.unit` — str
`metrics.INP.label` — str
`metrics.INP.rating` — str
`metrics.CLS.value` — int
`metrics.CLS.unit` — str
`metrics.CLS.label` — str
`metrics.CLS.rating` — str
`metrics.FCP.value` — int
`metrics.FCP.unit` — str
`metrics.FCP.label` — str
`metrics.FCP.rating` — str
`metrics.TTFB.value` — int
`metrics.TTFB.unit` — str
`metrics.TTFB.label` — str
`metrics.TTFB.rating` — str
`field_cwv.verdict` — str  (field data only: pass | fail; the key is absent when CrUX has no sample)
`field_cwv.measured[]` — array
`field_cwv.failing[]` — array
`opportunities[]` — array
  - item keys: title, savings_ms, description
`diagnostics[]` — array
  - item keys: title, score, display
`field_data_available` — bool
`error` — NoneType

### parse_html.py

`title` — str
`meta_description` — str
`meta_robots` — str
`meta_keywords` — NoneType
`x_robots_tag` — NoneType
`canonical` — str
`lang` — str
`charset` — str
`viewport` — str
`favicon` — str
`h1[]` — array
`h2[]` — array
`h3[]` — array
`h4[]` — array
`h5[]` — array
`h6[]` — array
`images[]` — array
  - item keys: src, alt, width, height, is_responsive_fill, loading
`links.internal[]` — array
  - item keys: href, text, rel
`links.external[]` — array
  - item keys: href, text, rel
`pagination.prev` — NoneType
`pagination.next` — NoneType
`resource_hints.preload[]` — array
`resource_hints.preconnect[]` — array
`resource_hints.dns-prefetch[]` — array
`resource_hints.prefetch[]` — array
`resource_hints.prerender[]` — array
`schema[]` — array
  - item keys: @type, @types, @id, @context, status, note, has_context, has_type, from_graph, raw
`open_graph.og:locale` — str
`open_graph.og:site_name` — str
`open_graph.og:type` — str
`open_graph.og:title` — str
`open_graph.og:description` — str
`open_graph.og:url` — str
`open_graph.og:image` — str
`open_graph.og:image:secure_url` — str
`open_graph.og:image:width` — str
`open_graph.og:image:height` — str

### product_schema_checker.py

`products` — int
`rows[]` — array
`issues[]` — array
`source` — str
`final_url` — str

### readability.py

`word_count` — int
`sentence_count` — int
`paragraph_count` — int
`syllable_count` — int
`avg_sentence_length` — float
`avg_paragraph_length` — float
`avg_syllables_per_word` — float
`flesch_reading_ease` — float
`flesch_kincaid_grade` — float
`reading_level` — str
`estimated_reading_time_min` — float
`complex_words` — int
`complex_word_pct` — float
`issues[]` — array
`recommendations[]` — array
`sentence_rewrites[]` — array
  - item keys: current, suggested, current_word_count, target_word_count

### redirect_checker.py

`url` — str
`final_url` — str
`chain[]` — array
  - item keys: step, url, status, time_ms, final
`total_hops` — int
`total_time_ms` — int
`has_loop` — bool
`has_mixed_protocol` — bool
`issues[]` — array
`error` — NoneType

### review_schema_checker.py

`reviews` — int
`aggregate_ratings` — int
`rows[]` — array
`issues[]` — array
`source` — str
`final_url` — str

### rich_results_guard.py

`nodes` — int
`rows[]` — array
  - item keys: path, types, issues
`issues[]` — array
`summary.errors` — int
`summary.warnings` — int
`source` — str
`final_url` — str

### robots_checker.py

`url` — str
`status` — int
`user_agents.*.allow[]` — array
`user_agents.*.disallow[]` — array
`sitemaps[]` — array
`ai_crawler_status.GPTBot` — str
`ai_crawler_status.ChatGPT-User` — str
`ai_crawler_status.ClaudeBot` — str
`ai_crawler_status.PerplexityBot` — str
`ai_crawler_status.Google-Extended` — str
`ai_crawler_status.Applebot-Extended` — str
`ai_crawler_status.Bytespider` — str
`ai_crawler_status.CCBot` — str
`ai_crawler_status.anthropic-ai` — str
`ai_crawler_status.FacebookBot` — str
`ai_crawler_status.Amazonbot` — str
`issues[]` — array
`error` — NoneType

### robots_path_tester.py

Takes positional paths after the URL. The registry uses it twice: CI-019 passes
`/search /cart /checkout /login`, and CI-013 passes representative asset paths
with `--agent Googlebot` to ask whether rendering resources are reachable. Rules
are matched, nothing is fetched, so the paths need not exist.

`site` — str
`robots_url` — str
`robots_status` — int
`allowed_urls[]` — array of str — every tested URL at least one agent may fetch.
  **Absent** when `robots_status` is neither 200 nor 404: a 500 or a timeout says
  nothing about what is allowed, and an empty list would read as "nothing is
  exposed". CI-019 asserts it is empty, CI-013 that it holds every asset path.
  Added because the previous assertion matched `allowed.*true` as text, and
  `allowed` and `true` never land in the same string of a nested dict — so it
  matched nothing and passed every site.
`rows[]` — array, one per path
  - item keys: url, decisions, allowed_for
  - `decisions.<agent>.allowed` — bool
  - `decisions.<agent>.rule` — str (`"no matching rule"` when nothing matched)
  - `allowed_for[]` — the agents allowed to fetch this URL
  - agents: Googlebot, Bingbot, GPTBot, ChatGPT-User, ClaudeBot, PerplexityBot, …

**No `issues[]` and no `summary`** — unlike almost every other script. Rules have
to walk `rows[].decisions` directly; there is no aggregate to assert against.

### schema_required_props.py

`schema_nodes` — int
`checked_type` — NoneType
`rows[]` — array
  - item keys: path, types, missing_required, missing_recommended, placeholder_properties
`issues[]` — array
  - item keys: severity, message, url, evidence
`summary.errors` — int
`summary.warnings` — int
`source` — str
`final_url` — str

### security_headers.py

`url` — str
`score` — int
`https` — bool
`headers_present.HSTS (Strict-Transport-Security)` — str
`headers_present.X-Frame-Options` — str
`headers_present.X-Content-Type-Options` — str
`headers_present.Referrer-Policy` — str
`headers_present.Permissions-Policy` — str
`headers_missing.Content-Security-Policy (CSP)` — str
`header_values.strict-transport-security` — str
`header_values.x-frame-options` — str
`header_values.x-content-type-options` — str
`header_values.referrer-policy` — str
`header_values.permissions-policy` — str
`issues[]` — array
`recommendations[]` — array
`error` — NoneType

### sitemap_checker.py

`site` — str
`sitemaps_checked[]` — array
  - item keys: url, status, final_url, redirects, type, url_count, sitemap_count, error
`urls[]` — array
  - item keys: url, lastmod, changefreq, priority, checks
`summary.sitemaps` — int
`summary.urls` — int
`summary.indexes` — int
`summary.issues` — int
`issues[]` — array
  - item keys: severity, message, url, evidence

### social_meta.py

`url` — str
`score` — int
`og_tags.og:locale` — str
`og_tags.og:site_name` — str
`og_tags.og:type` — str
`og_tags.og:title` — str
`og_tags.og:description` — str
`og_tags.og:url` — str
`og_tags.og:image` — str
`og_tags.og:image:secure_url` — str
`og_tags.og:image:width` — str
`og_tags.og:image:height` — str
`twitter_tags.twitter:card` — str
`twitter_tags.twitter:title` — str
`twitter_tags.twitter:description` — str
`twitter_tags.twitter:image` — str
`og_present[]` — array
`og_missing[]` — array
`twitter_present[]` — array
`twitter_missing[]` — array
`issues[]` — array
`recommendations[]` — array
`preview.title` — str
`preview.description` — str
`preview.image` — str
`preview.site_name` — str
`error` — NoneType

### third_party_script_audit.py

`url` — str
`script_count` — int
`third_party_count` — int
`blocking_third_party_count` — int
`third_party_bytes` — NoneType
`issues[]` — array
  - item keys: severity, message, url
`scripts[]` — array
  - item keys: src, inline, async, defer, type, third_party, known_tag, content_length, status, blocking
`fetch_error` — NoneType

### topical_cluster_mapper.py

`page_count` — int
`cluster_count` — int
`score` — int
`clusters.seo.page_count` — int
`clusters.seo.hub` — str
`clusters.seo.topics[]` — array
`clusters.seo.internal_edges[]` — array
`clusters.seo.missing_links[]` — array
`clusters.seo.orphan_candidates[]` — array
`issues[]` — array

### url_quality.py

`count` — int
`rows[]` — array
  - item keys: url, path, param_count, params, flags, score

### video_schema_checker.py

`videos` — int
`rows[]` — array
`issues[]` — array
`source` — str
`final_url` — str

### x_robots_header_checker.py

`count` — int
`rows[]` — array
  - item keys: url, status, final_url, x_robots_tag, directives, indexing_effect, follow_effect, archive_effect, snippet_rules, error

