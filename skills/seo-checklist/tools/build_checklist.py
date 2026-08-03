#!/usr/bin/env python3
"""Generate resources/config/checklist.json — the checklist registry.

The registry is the single source of truth for audit coverage: every item
names who answers it (a bundled script, the LLM, Search Console, or a human)
and, for script-backed items, a declarative assert rule.

Assert rules are written against real script output captured in
resources/references/script-output-shapes.md. Regenerate that file with
tools/probe_shapes.py before changing rules here.

Usage:
    python3 tools/build_checklist.py [--out PATH] [--check]

--check exits non-zero if the generated registry differs from the one on
disk, so CI can catch a stale checklist.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
DEFAULT_OUT = os.path.join(SKILL_DIR, "resources", "config", "checklist.json")

# --------------------------------------------------------------------------
# Categories — mirror the 15 Plerdy sections, id-prefixed for stable item ids.
# --------------------------------------------------------------------------

CATEGORIES = [
    ("crawling_indexing", "CI", "Crawling & Indexing", (1, 19)),
    ("meta_structured", "MS", "Meta & Structured Data", (20, 33)),
    ("content", "CN", "Content", (34, 68)),
    ("keywords", "KW", "Keyword Analysis", (69, 77)),
    ("backlinks", "BL", "Backlinks", (78, 92)),
    ("mobile", "MB", "Mobile", (93, 106)),
    ("speed", "SP", "Speed", (107, 113)),
    ("security", "SE", "Security", (114, 120)),
    ("international", "IN", "International & Multilingual", (121, 130)),
    ("google", "GO", "Google", (131, 145)),
    ("architecture", "AR", "Website Architecture", (146, 164)),
    ("technical", "TE", "Technical SEO Checks", (165, 183)),
    ("media", "MD", "Images / Video", (184, 190)),
    ("competition", "CO", "Competition Analysis", (191, 195)),
    ("local", "LO", "Local SEO", (196, 200)),
]

# --------------------------------------------------------------------------
# Assert vocabulary (interpreted by checklist_runner.py):
#   eq / ne / gt / gte / lt / lte      scalar comparison
#   truthy / falsy                     boolean-ish
#   len_eq / len_gte / len_lte         length of list or string
#   len_between: [lo, hi]              inclusive length range
#   between: [lo, hi]                  inclusive numeric range
#   matches: "regex"                   regex search on str(value)
#   contains: "substr"                 substring / list membership
#   none_severity: ["critical","high"] no issues[] entry at those severities
#   none_matching: "regex"             no issues[] entry whose message matches
#   count_matching_lte: ["regex", n]   at most n matching issues
#   value_map: {value: pass|fail}      enumerate the script's own vocabulary for
#                                      a field; an unlisted value is NO_DATA.
#                                      Optional "field" projects a list of dicts.
# Prefer a counted field or value_map over a pattern. `none_matching` passes when
# nothing matches, so a pattern aimed at wording a script does not emit passes
# every site in silence — fifteen assertions here were doing exactly that. Run
# tools/audit_assertions.py after touching one; a test runs it too.
# `path` uses dots; `[]` is not needed — lists are handled by len_*/none_*.
# Optional "warn" block uses the same vocabulary; it is evaluated only when
# the main assert fails, turning FAIL into WARN.
# --------------------------------------------------------------------------

S = "script"
L = "llm"
G = "gsc"
M = "manual"

PAGE = ["{url}"]
HTMLARG = ["{html}", "--url", "{url}"]
# GSC scripts address a Search Console property, not the audited URL — the two
# differ whenever you audit a page on a property you access by domain.
GSCARG = ["{gsc_property}", "--credentials", "{gsc_credentials}"]
# The Links report has no API at all, so incoming links come from a CSV the user
# exports from the Search Console UI. Without --links-csv these items report
# NO_DATA with that instruction rather than guessing.
LINKSARG = ["{links_csv}", "--site", "{url}"]
# URL Inspection is the one GSC call that addresses a page rather than a
# property, so it needs both.
INSPECTARG = ["{url}", "--property", "{gsc_property}",
              "--credentials", "{gsc_credentials}"]

# What each script needs in order to produce an answer. The runner uses this to
# decide, per run mode, whether an item is answerable (run it), not applicable
# (N/A — never counted against the score), or blocked (NO_DATA).
#   offline   parses a local HTML file; works on an archive with no network
#   fetch     requests the single target URL
#   crawl     requests many URLs (slow; meaningless against a single file)
#   api       calls a third-party service (PageSpeed, W3C, Safe Browsing)
#   gsc       needs Google Search Console credentials
REQUIRES = {
    "parse_html.py": "offline",
    # Reads a file a trace already produced, so it needs no network of its own —
    # the measurement happened before the run, and the run must not pretend to be
    # taking it.
    "cwv_metrics.py": "offline",
    "readability.py": "offline",
    "pagespeed.py": "api",
    "html_validator.py": "api",
    "domain_safety_check.py": "api",
    "duplicate_content.py": "crawl",
    "internal_links.py": "crawl",
    "anchor_text_audit.py": "crawl",
    "orphan_pages_from_sitemap.py": "crawl",
    "link_profile.py": "crawl",
    "external_link_quality.py": "crawl",
    "broken_links.py": "crawl",
    "sitemap_checker.py": "crawl",
    "indexability_matrix.py": "crawl",
    "competitor_gap.py": "crawl",
    # Reads a file the user exported; no network, so even archive mode can use it.
    "gsc_links_csv.py": "offline",
    "gsc_checker.py": "gsc",
    "gsc_url_inspection.py": "gsc",
    "gsc_cannibalization.py": "gsc",
}
DEFAULT_REQUIRES = "fetch"

# How much work a fix costs, so that priority can weigh severity against effort
# instead of ranking by severity alone. These are per-category heuristics, not
# per-item estimates: a meta tag is a config edit, a rewrite is not, and an
# outreach campaign is not a code change at all. Anything finer would be a
# fabricated precision.
EFFORT_BY_CATEGORY = {
    "crawling_indexing": "low", "meta_structured": "low", "security": "low",
    "technical": "low", "google": "low",
    "mobile": "medium", "speed": "medium", "media": "medium", "keywords": "medium",
    "content": "high", "international": "high", "architecture": "high",
    "backlinks": "high", "competition": "high", "local": "high",
    "geo_ai": "medium",
}
# Outliers where the category default is plainly wrong for a specific item.
EFFORT_OVERRIDES = {
    "CN-047": "low",    # fix spelling
    "CN-064": "low",    # add a call to action
    "MS-031": "low",    # drop meta keywords
    "AR-160": "low",    # footer links
    "TE-176": "high",   # migrate to HTTP/2/3 — infrastructure, not a page edit
    "SP-107": "high",   # Core Web Vitals work is rarely a quick fix
    "SP-108": "high",
    "SP-109": "high",
}
# A human-facing task is never "low" no matter what its category says.
EFFORT_FLOOR_BY_SOURCE = {"manual": "high", "llm": "medium"}
EFFORT_RANK = {"low": 0, "medium": 1, "high": 2}


def effort_for(entry: dict) -> str:
    e = EFFORT_OVERRIDES.get(entry["id"]) or EFFORT_BY_CATEGORY.get(entry["category"], "medium")
    floor = EFFORT_FLOOR_BY_SOURCE.get(entry["source"])
    if floor and EFFORT_RANK[floor] > EFFORT_RANK[e]:
        e = floor
    return e


# ref -> (severity, source, script, args, assert_rule, fix, warn)
MAP: dict[int, tuple] = {}


def item(ref, sev, source, script=None, args=None, rule=None, fix="", warn=None):
    MAP[ref] = (sev, source, script, args, rule, fix, warn)


# --- 1. Crawling & Indexing -------------------------------------------------
item(1, "critical", S, "indexability_matrix.py", PAGE,
     {"path": "rows.0.robots_allowed", "truthy": True},
     "Remove noindex, allow crawling in robots.txt, add internal links, submit the URL in GSC")
item(2, "high", S, "sitemap_checker.py", PAGE,
     {"path": "summary.urls", "gte": 1},
     "Index only valuable templates: categories, product pages, articles")
item(3, "critical", S, "indexability_matrix.py", PAGE,
     {"path": "rows.0.status", "eq": 200},
     "Canonical URL must return 200 OK across all variants (http/https, www/non-www)")
item(4, "critical", S, "parse_html.py", HTMLARG,
     {"path": "meta_robots", "none_matching": "noindex", "missing_is": "pass"},
     "Indexable pages should be set to index, follow")
item(5, "critical", S, "indexability_matrix.py", PAGE,
     {"path": "rows.0.robots_allowed", "truthy": True},
     "Remove the blocking rule from robots.txt")
item(6, "medium", S, "robots_checker.py", PAGE,
     {"path": "sitemaps", "len_gte": 1},
     "Add a Sitemap: https://example.com/sitemap.xml line to robots.txt")
item(7, "medium", M, fix="Submit the sitemap in Google Search Console and Bing Webmaster Tools")
item(8, "high", S, "link_profile.py", PAGE,
     {"path": "orphan_pages.count", "eq": 0},
     "Eliminate orphan pages: add 1-2 contextual internal links to each")
item(9, "critical", S, "canonical_checker.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Self-canonical on the primary version, 301 from duplicates")
# A page can point rel=canonical at itself and still have Google pick another
# URL. Nothing in the page reveals the disagreement — only URL Inspection does.
# When the page declares no canonical there is nothing to compare, so the script
# leaves canonical_match null and the item stays NO_DATA.
item(10, "high", S, "gsc_url_inspection.py", INSPECTARG,
     {"path": "canonical_match", "truthy": True},
     "Align the declared canonical with the one Google selected, or work out why "
     "Google prefers a different URL")
item(11, "high", S, "canonical_checker.py", PAGE,
     # canonical_checker emits one of five verdicts and never the words
     # "mismatch" or "conflict", so the old pattern passed every page. Mapping
     # its actual vocabulary also fixes the other half: "unknown" means the
     # script could not tell, which is NO_DATA, not a pass.
     {"path": "rows", "field": "verdict",
      "value_map": {"self_canonical": "pass", "missing": "pass",
                    "canonicalized": "pass", "cross_host": "fail"}},
     "Do not combine noindex with a canonical pointing elsewhere")
item(12, "medium", S, "url_quality.py", PAGE,
     {"path": "rows.0.score", "gte": 70},
     "Keep URLs short, readable, lowercase, words separated by hyphens")
# robots_checker.py reports sitemaps and syntax; it never says anything about
# CSS, JS or images, so this critical item passed on every site ever audited —
# the pattern was matching the script's own module docstring, which mentions
# both. robots_path_tester answers it properly: ask whether Googlebot may fetch
# representative asset paths. The rules are matched, nothing is downloaded, so
# the paths need not exist. ASSET_PROBES and the len_gte below must agree.
ASSET_PROBES = ["/assets/app.css", "/static/app.js", "/images/hero.jpg"]
item(13, "critical", S, "robots_path_tester.py",
     ["{url}"] + ASSET_PROBES + ["--agent", "Googlebot"],
     {"path": "allowed_urls", "len_gte": len(ASSET_PROBES)},
     "Do not block critical CSS/JS/images in robots.txt - Google must be able to render the page")
item(14, "high", S, "redirect_checker.py", PAGE,
     {"path": "has_loop", "falsy": True},
     "Use 301/308 for permanent and 302/307 for temporary; remove chains and loops",
     {"path": "total_hops", "lte": 2})
item(15, "critical", S, "indexability_matrix.py", PAGE,
     {"path": "rows.0.status", "lt": 500},
     "Set up uptime and log alerts, resolve 5xx errors reported in GSC")
item(16, "high", S, "image_inventory.py", PAGE,
     {"path": "missing_alt", "eq": 0},
     "Descriptive alt on informative images, empty alt on decorative ones")
item(17, "medium", S, "html_validator.py", PAGE,
     {"path": "summary.errors", "eq": 0},
     "Fix W3C validation errors - they affect rendering and parsing")
item(18, "medium", M, fix="Analyze server logs for Googlebot UA: crawl frequency, 404s, parameterized URLs, crawl budget")
item(19, "high", S, "robots_path_tester.py", ["{url}", "/search", "/cart", "/checkout", "/login"],
     # `allowed` and `true` sit in different fields of a nested dict, so they
     # never appeared in one string and the pattern never fired. The script now
     # flattens the answer into `allowed_urls`, absent when robots.txt could not
     # be read at all.
     {"path": "allowed_urls", "len_lte": 0},
     "Set noindex,follow on internal search and system pages, exclude them from sitemaps")

# --- 2. Meta & Structured Data ---------------------------------------------
item(20, "high", S, "parse_html.py", HTMLARG,
     {"path": "title", "len_lte": 60},
     "Shorten the title so it is not truncated in the SERP (~60 characters)")
item(21, "medium", S, "parse_html.py", HTMLARG,
     {"path": "title", "len_gte": 30},
     "Titles under 30 characters are usually too vague to match intent")
item(22, "high", S, "duplicate_content.py", PAGE,
     {"path": "exact_duplicates", "len_eq": 0},
     "Crawl for duplicate titles, then differentiate or canonicalize them")
item(23, "high", S, "gsc_cannibalization.py", GSCARG,
     {"path": "summary.cannibalized_queries", "eq": 0},
     "Find queries in GSC where multiple URLs compete; pick the target and consolidate the rest",
     {"path": "summary.cannibalized_queries", "lte": 3})
item(24, "medium", L, fix="Lead the title with the main topic")
item(25, "medium", L, fix="The title must accurately describe the page content and intent")
item(26, "critical", S, "parse_html.py", HTMLARG,
     {"path": "title", "truthy": True},
     "Every page needs a title")
item(27, "high", S, "parse_html.py", HTMLARG,
     {"path": "meta_description", "truthy": True},
     "Write a unique description that reflects the page content")
item(28, "medium", S, "parse_html.py", HTMLARG,
     {"path": "meta_description", "truthy": True},
     "Fill in meta descriptions, high-value pages first")
item(29, "medium", S, "duplicate_content.py", PAGE,
     {"path": "summary.exact_duplicate_groups", "eq": 0},
     "Remove duplicate meta descriptions")
item(30, "low", S, "parse_html.py", HTMLARG,
     {"path": "meta_description", "len_between": [120, 165]},
     "Keep meta descriptions around 150-160 characters")
item(31, "low", S, "parse_html.py", HTMLARG,
     {"path": "meta_keywords", "falsy": True, "missing_is": "pass"},
     "Remove meta keywords - search engines ignore it")
item(32, "high", S, "schema_required_props.py", PAGE,
     {"path": "summary.errors", "eq": 0},
     "Add required schema properties and validate with the Rich Results Test",
     {"path": "summary.warnings", "lte": 3})
item(33, "medium", S, "social_meta.py", PAGE,
     {"path": "score", "gte": 80},
     "Fill in Open Graph and Twitter Card tags")

# --- 3. Content -------------------------------------------------------------
# a11y_seo_checker.py checks H1 count, lang, viewport, alt text, labels,
# landmarks and generic link text — it has never looked at font size, link
# styling or tap targets. The three items that asked it to were matching wording
# it cannot emit, so they passed on every site. Rendered type size and hit areas
# need the layout lens, which reads the CSS and the markup together.
item(34, "medium", L, fix="Readable font size across all breakpoints")
item(35, "medium", L, fix="Links must be visually distinct from body text")
item(36, "medium", S, "a11y_seo_checker.py", PAGE,
     {"path": "checks.inline_contrast_candidates", "eq": 0},
     "Text contrast at WCAG AA or better (4.5:1)")
item(37, "low", L, fix="Separate primary from supplementary content visually and semantically")
item(38, "medium", S, "freshness_checker.py", PAGE,
     {"path": "score", "gte": 70},
     "Refresh evergreen material and balance it with new content")
item(39, "high", S, "duplicate_content.py", PAGE,
     {"path": "summary.thin_pages", "eq": 0},
     "Consolidate or expand thin pages",
     {"path": "summary.thin_pages", "lte": 5})
item(40, "medium", S, "eeat_signal_checker.py", PAGE,
     {"path": "signals.policy_links", "len_gte": 1},
     "Publish an up-to-date privacy policy and link to it")
item(41, "high", S, "duplicate_content.py", PAGE,
     {"path": "summary.exact_duplicate_groups", "eq": 0},
     "Eliminate internal duplicates: consolidate or canonicalize")
item(42, "medium", L, fix="Review external duplicates and syndication, agree on a canonical to the source")
item(43, "high", L, fix="Remove scraped or lightly-rewritten third-party content")
item(44, "medium", S, "eeat_signal_checker.py", PAGE,
     {"path": "signals.trust_links", "len_gte": 1},
     "Provide a clear, easy-to-find contact page")
item(45, "medium", M, fix="Run a content gap analysis against competitors")
item(46, "medium", L, fix="Review copy quality and content classification")
item(47, "medium", L, fix="Check grammar and spelling")
item(48, "high", S, "parse_html.py", HTMLARG,
     {"path": "h2", "len_gte": 1},
     "Use hierarchical headings and semantic HTML")
item(49, "medium", L, fix="Target topics and queries, not isolated keywords")
item(50, "high", L, fix="Follow Google Search Essentials - quality and spam policies")
# mobile_render_checker.py reports viewport, fixed widths and sticky
# positioning. It says nothing about interstitials, and the two items asking it
# for them matched nothing. Whether a dialog is *intrusive* is a judgement about
# what covers the content, which is the layout lens.
item(51, "high", L, fix="Remove intrusive interstitials, especially on mobile")
item(52, "medium", L, fix="Limit heavy advertising above the fold")
item(53, "medium", S, "javascript_render_audit.py", PAGE,
     {"path": "raw.word_count", "gte": 300},
     "Do not hide critical content inside iframes")
item(54, "high", S, "image_inventory.py", PAGE,
     # The script does detect this, and says "Likely LCP image is lazy-loaded" —
     # LCP before lazy, so a pattern requiring lazy first never matched. Counting
     # the flag the script already computes needs no wording at all.
     {"path": "summary.lazy_lcp_candidates", "eq": 0},
     "Lazy-loaded content must remain discoverable by crawlers")
item(55, "medium", S, "parse_html.py", HTMLARG,
     {"path": "pagination.next", "truthy": True},
     "Make infinite scroll crawlable via paginated URLs")
item(56, "medium", S, "freshness_checker.py", PAGE,
     {"path": "dates", "len_gte": 1},
     "Show publication and updated dates")
item(57, "high", S, "eeat_signal_checker.py", PAGE,
     {"path": "signals.authors", "len_gte": 1},
     "Show author and publisher clearly")
item(58, "low", L, fix="Check whether the content risks being flagged by SafeSearch")
item(59, "high", L, fix="Remove hidden text added to manipulate rankings")
item(60, "critical", L, fix="Do not serve different content to crawlers and users (cloaking)")
item(61, "high", L, fix="Remove doorway pages - query-targeted pages with no standalone value")
item(62, "medium", L, fix="Reduce ad density")
item(63, "medium", L, fix="Do not overuse pop-ups")
item(64, "low", L, fix="Use clear, explicit calls to action")
item(65, "critical", S, "parse_html.py", HTMLARG,
     {"path": "h1", "len_eq": 1},
     "Exactly one H1 per page")
item(66, "medium", S, "parse_html.py", HTMLARG,
     {"path": "h2", "len_gte": 2},
     "Structure the copy with H2 subheadings")
item(67, "high", L, fix="Publish people-first content; AI assistance is fine when the result helps a human")
item(68, "high", S, "eeat_signal_checker.py", PAGE,
     {"path": "score", "gte": 60},
     "Strengthen authorship and E-E-A-T: author, credentials, first-hand experience, sourced claims")

# --- 4. Keyword analysis ----------------------------------------------------
item(69, "high", M, fix="Run keyword research and set position benchmarks")
item(70, "high", S, "gsc_cannibalization.py", GSCARG,
     {"path": "branded.owns_homepage", "truthy": True},
     "Confirm the homepage ranks first for the branded query")
item(71, "high", S, "gsc_cannibalization.py", GSCARG,
     {"path": "summary.worst_spread", "lte": 3},
     "Find keyword overuse and duplication across URLs")
item(72, "high", S, "article_seo.py", PAGE,
     {"path": "seo_issues", "none_matching": "(?i)title.*keyword"},
     "Put the primary topic in the title")
item(73, "high", S, "article_seo.py", PAGE,
     {"path": "seo_issues", "none_matching": "(?i)h1.*keyword"},
     "Include the primary keyword in the H1")
# article_seo.py advises on title and H1 keywords but emits nothing about
# keywords in an H2 or in the meta description, so both items passed unread.
# Judging a "close variant" is a copy question anyway — a regex cannot see that
# "running shoes" and "shoes for runners" are the same intent.
item(74, "medium", L, fix="Include the primary keyword or a close variant in an H2")
item(75, "medium", L,
     fix="Include the primary keyword in the meta description - it affects CTR")
item(76, "medium", S, "article_seo.py", PAGE,
     {"path": "target_keyword", "truthy": True},
     "The primary keyword should appear naturally in body copy")
item(77, "medium", L, fix="Include the primary keyword in the opening paragraph")

# --- 5. Backlinks -----------------------------------------------------------
item(78, "high", M, fix="Assess backlink quality and authority (needs an external service or a GSC CSV export)")
item(79, "high", M, fix="Identify spammy referring domains")
item(80, "medium", M, fix="Disavow only on clear spam - not as routine hygiene")
item(81, "medium", S, "anchor_text_audit.py", PAGE,
     {"path": "summary.overused_exact_match_targets", "eq": 0},
     "Diversify anchors, remove exact-match over-optimization",
     {"path": "summary.overused_exact_match_targets", "lte": 10})
item(82, "medium", M, fix="Monitor and reclaim lost backlinks")
item(83, "medium", S, "external_link_quality.py", PAGE,
     {"path": "summary.broken_links", "eq": 0},
     "Fix broken links: update the URL or add a redirect")
item(84, "medium", S, "gsc_links_csv.py", LINKSARG,
     {"path": "concentration.top1_share_pct", "lte": 50},
     "Diversify referrers: one domain supplying most links makes rankings hostage "
     "to a single relationship",
     {"path": "concentration.top1_share_pct", "lte": 65})
item(85, "low", M, fix="Do not optimize for domain age - it is not a ranking factor")
item(86, "low", S, "gsc_links_csv.py", LINKSARG,
     {"path": "total_links", "gte": 1},
     "Export Search Console -> Links periodically so the trend is visible; the "
     "count matters far less than who the links come from")
item(87, "medium", S, "gsc_links_csv.py", LINKSARG,
     {"path": "linking_domains", "gte": 5},
     "Grow the number of distinct referring domains — root domains move rankings, "
     "repeat links from the same site much less")
item(88, "high", M, fix="Earn topically relevant backlinks to the target URL")
item(89, "high", M, fix="Verify the disavow file does not contain valuable links")
item(90, "low", M, fix="Create and maintain social profiles where the audience actually is")
item(91, "low", M, fix="Publish LinkedIn articles and maintain the company page")
item(92, "low", M, fix="Pitch and appear on relevant podcasts")

# --- 6. Mobile --------------------------------------------------------------
item(93, "critical", S, "parse_html.py", HTMLARG,
     {"path": "viewport", "truthy": True},
     "Responsive, mobile-first layout")
item(94, "high", L, fix="Remove intrusive interstitials on mobile")
item(95, "medium", S, "image_weight_audit.py", PAGE,
     {"path": "issues", "count_matching_lte": ["(?i)large|oversize|weight", 5]},
     "Reduce mobile page weight")
item(96, "medium", S, "image_weight_audit.py", PAGE,
     {"path": "responsive_count", "gte": 1},
     "Use srcset/sizes for responsive images")
item(97, "medium", S, "image_weight_audit.py", PAGE,
     {"path": "modern_format_count", "gte": 1},
     "Move to WebP/AVIF and compress images")
item(98, "medium", S, "image_weight_audit.py", PAGE,
     {"path": "issues", "count_matching_lte": ["(?i)size|dimension", 10]},
     "Serve properly sized images")
item(99, "medium", G, fix="Review mobile signals in Google Search Console")
item(100, "medium", S, "mobile_render_checker.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Fix mobile UX issues")
item(101, "low", L, fix="Keep mobile navigation within thumb reach")
item(102, "low", S, "video_schema_checker.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Optimize video for mobile")
item(103, "medium", L, fix="Increase tap targets to 48x48 CSS pixels")
item(104, "low", S, "parse_html.py", HTMLARG,
     {"path": "favicon", "truthy": True},
     "Add a favicon - it shows in mobile SERPs")
item(105, "high", S, "javascript_render_audit.py", PAGE,
     {"path": "diffs", "len_eq": 0},
     "Content, meta and directives must match between mobile and desktop")
item(106, "medium", M, fix="Test on real devices before and after release")

# --- 7. Speed ---------------------------------------------------------------
item(107, "high", S, "pagespeed.py", ["{url}", "--strategy", "mobile"],
     {"path": "metrics.FCP.rating", "eq": "fast"},
     "Speed up above-the-fold rendering")
item(108, "critical", S, "pagespeed.py", ["{url}", "--strategy", "mobile"],
     {"path": "field_data_available", "truthy": True},
     "Collect CrUX field data; fall back to lab data when it is unavailable")
item(109, "medium", S, "third_party_script_audit.py", PAGE,
     {"path": "blocking_third_party_count", "eq": 0},
     "Remove render-blocking third-party scripts",
     {"path": "blocking_third_party_count", "lte": 2})
item(110, "medium", S, "critical_request_chain.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Shorten the critical request chain")
item(111, "high", S, "pagespeed.py", ["{url}", "--strategy", "desktop"],
     {"path": "performance_score", "gte": 90},
     "Bring desktop Core Web Vitals into the green",
     {"path": "performance_score", "gte": 50})
item(112, "high", S, "pagespeed.py", ["{url}", "--strategy", "mobile"],
     {"path": "performance_score", "gte": 90},
     "Bring mobile Core Web Vitals into the green",
     {"path": "performance_score", "gte": 50})
item(113, "critical", S, "pagespeed.py", ["{url}", "--strategy", "mobile"],
     {"path": "metrics.LCP.rating", "eq": "fast"},
     "LCP < 2.5s, INP < 200ms, CLS < 0.1")

# --- 8. Security ------------------------------------------------------------
item(114, "critical", S, "domain_safety_check.py", PAGE,
     {"path": "safe_browsing.threats", "len_eq": 0},
     "Scan the site for malicious code via Safe Browsing")
item(115, "medium", S, "security_headers.py", PAGE,
     {"path": "header_values.strict-transport-security", "truthy": True},
     "Enable HSTS")
item(116, "critical", S, "domain_safety_check.py", PAGE,
     {"path": "safe_browsing.clean", "truthy": True},
     "Confirm there is no hacked content or malware")
item(117, "critical", S, "security_headers.py", PAGE,
     {"path": "https", "truthy": True},
     "Force HTTPS sitewide with a single canonical protocol")
item(118, "critical", S, "security_headers.py", PAGE,
     {"path": "https", "truthy": True},
     "Maintain a valid TLS certificate")
item(119, "medium", S, "pagespeed.py", ["{url}", "--strategy", "mobile"],
     {"path": "metrics.CLS.rating", "eq": "fast"},
     "The cookie banner must not cause layout shift")
item(120, "medium", S, "security_headers.py", PAGE,
     {"path": "score", "gte": 80},
     "Configure CSP, Permissions-Policy and Referrer-Policy")

# --- 9. International -------------------------------------------------------
item(121, "medium", S, "hreflang_checker.py", PAGE,
     {"path": "checks.x_default.passed", "truthy": True},
     "Configure geo-targeting signals, including x-default")
item(122, "high", S, "hreflang_checker.py", PAGE,
     {"path": "summary.critical", "eq": 0},
     "Valid hreflang with return tags")
item(123, "medium", S, "parse_html.py", HTMLARG,
     {"path": "lang", "truthy": True},
     "Declare the page language in html lang")
# redirect_checker.py reports loops, chains and missing Location headers. A
# forced geo redirect only shows itself to a request from another country, which
# no single fetch from one machine can produce — so this is a human with a VPN,
# not a script and not a language model reading one page.
item(124, "medium", M, fix="Do not force geo or language redirects")
item(125, "low", M, fix="Define target international markets and audiences")
item(126, "medium", L, fix="Translations must be high quality and human-reviewed")
item(127, "medium", S, "hreflang_checker.py", PAGE,
     {"path": "checks.protocol_consistency.passed", "truthy": True},
     "Use a clear international URL structure")
item(128, "medium", S, "hreflang_checker.py", PAGE,
     {"path": "checks.self_reference.passed", "truthy": True},
     "Serve the correct localized page")
item(129, "low", M, fix="Earn local backlinks in target markets")
item(130, "low", L, fix="Clarify the site type: multilingual, multiregional, or both")

# --- 10. Google -------------------------------------------------------------
item(131, "medium", S, "ga4_tag_checker.py", PAGE,
     {"path": "measurement_ids", "len_gte": 1},
     "Install and configure Google Analytics 4")
item(132, "medium", S, "ga4_tag_checker.py", PAGE,
     {"path": "duplicates", "len_eq": 0},
     "Remove duplicate GA4/GTM tags")
item(133, "high", M, fix="Set up Google Search Console as a domain property")
item(134, "high", S, "gsc_checker.py", GSCARG,
     {"path": "opportunities", "none_severity": ["critical", "high"]},
     "Resolve the issues Search Console reports")
item(135, "medium", S, "gsc_url_inspection.py", INSPECTARG,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Resolve what URL Inspection reports: blocked indexing, failed fetch, or a "
     "coverage state that keeps the page out of the index")
item(136, "high", S, "sitemap_checker.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Keep XML sitemaps clean")
item(137, "medium", S, "orphan_pages_from_sitemap.py", PAGE,
     {"path": "summary.orphan_pages", "eq": 0},
     "Reconcile indexed pages against sitemap contents",
     {"path": "summary.orphan_pages", "lte": 50})
item(138, "medium", S, "sitemap_checker.py", PAGE,
     {"path": "issues", "none_matching": "(?i)404|redirect|noindex"},
     "Remove invalid URLs from sitemaps")
item(139, "low", S, "gsc_cannibalization.py", GSCARG,
     {"path": "branded.ranks_first", "truthy": True},
     "Monitor and improve the brand SERP")
item(140, "low", M, fix="Add a Google News sitemap if the site qualifies")
item(141, "critical", G, fix="Check for manual actions in Search Console")
item(142, "high", G, fix="Resolve crawl and indexing issues")
item(143, "low", S, "schema_required_props.py", PAGE,
     {"path": "issues", "none_matching": "(?i)WebSite|SearchAction"},
     "Optimize for sitelinks and the Sitelinks Search Box")
item(144, "medium", S, "answer_block_scanner.py", PAGE,
     {"path": "score", "gte": 70},
     "Optimize for featured snippets: direct answers, lists, tables")
item(145, "high", S, "citation_readiness.py", PAGE,
     {"path": "score", "gte": 60},
     "Optimize for AI Overviews and zero-click: citability, facts, sources")

# --- 11. Website Architecture ----------------------------------------------
item(146, "medium", S, "parse_html.py", HTMLARG,
     {"path": "pagination", "truthy": True},
     "Verify pagination is correct")
item(147, "medium", S, "url_quality.py", PAGE,
     {"path": "rows.0.param_count", "lte": 2},
     "Short descriptive URLs without excess parameters")
item(148, "low", M, fix="Visualize the site architecture")
item(149, "medium", S, "internal_links.py", PAGE,
     {"path": "pages", "truthy": True},
     "Remove internal links that pass through a redirect")
item(150, "high", S, "redirect_checker.py", PAGE,
     {"path": "total_hops", "lte": 1},
     "Remove redirect chains and loops")
item(151, "high", S, "robots_checker.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Correct robots.txt")
item(152, "medium", S, "robots_checker.py", PAGE,
     {"path": "user_agents", "truthy": True},
     "Block low-value sections from crawling deliberately")
item(153, "medium", S, "topical_cluster_mapper.py", PAGE,
     {"path": "score", "gte": 70},
     "Build topic hubs (silos)")
item(154, "medium", S, "collection_page_checker.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Optimize e-commerce category pages")
item(155, "low", S, "url_quality.py", PAGE,
     {"path": "rows.0.flags", "len_eq": 0},
     "Consistent, descriptive URL slugs")
item(156, "medium", M, fix="Helpful 404 page with navigation and search")
item(157, "low", L, fix="Use tag pages deliberately rather than generating duplicates")
item(158, "medium", S, "schema_required_props.py", PAGE,
     {"path": "issues", "none_matching": "(?i)BreadcrumbList"},
     "Breadcrumbs in the UI and as BreadcrumbList markup")
item(159, "low", L, fix="Simplify primary navigation")
item(160, "low", L, fix="Optimize footer navigation")
item(161, "medium", L, fix="Clear header and mobile menus")
item(162, "high", S, "link_profile.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Strengthen internal linking, remove orphans")
item(163, "medium", S, "faceted_nav_audit.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Control faceted navigation: canonical, noindex, robots")
item(164, "medium", M, fix="Handle out-of-stock products via 301/410 plus clear UX")

# --- 12. Technical SEO Checks ----------------------------------------------
item(165, "low", L, fix="Choose subdomains or subdirectories deliberately")
item(166, "low", S, "parse_html.py", HTMLARG,
     {"path": "favicon", "truthy": True},
     "Add a favicon")
item(167, "medium", S, "domain_safety_check.py", PAGE,
     {"path": "uptime.reachable", "truthy": True},
     "Set up uptime monitoring")
item(168, "high", S, "broken_links.py", PAGE,
     {"path": "summary.broken", "eq": 0},
     "Fix broken and redirected links",
     {"path": "summary.broken", "lte": 3})
item(169, "high", S, "javascript_render_audit.py", PAGE,
     {"path": "raw.internal_link_count", "gte": 1},
     "Ensure crawlability under JavaScript rendering")
item(170, "medium", S, "cache_compression_checker.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Configure server rewrites and cache/compression headers")
item(171, "critical", S, "domain_safety_check.py", PAGE,
     {"path": "safe_browsing.clean", "truthy": True},
     "Check the domain against blocklists and Safe Browsing")
item(172, "high", S, "rich_results_guard.py", PAGE,
     {"path": "summary.errors", "eq": 0},
     "Implement structured data correctly, JSON-LD only")
item(173, "medium", M, fix="Fix browser console errors (chrome-devtools MCP: list_console_messages)")
item(174, "low", S, "css_minify_check.py", PAGE,
     {"path": "unminified_count", "eq": 0},
     "Minify and optimize CSS")
item(175, "high", S, "security_headers.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Secure pages and eliminate errors")
item(176, "high", S, "canonical_checker.py", PAGE,
     {"path": "issues", "len_eq": 0},
     "Fix canonicalization issues")
item(177, "medium", S, "javascript_render_audit.py", PAGE,
     {"path": "raw.title", "truthy": True},
     "Content must be reachable without executing JavaScript")
item(178, "low", S, "domain_safety_check.py", PAGE,
     {"path": "neighbors.suspicious", "len_eq": 0},
     "Audit neighboring sites on the same server IP")
item(179, "low", S, "domain_safety_check.py", PAGE,
     {"path": "whois.age_days", "gte": 90},
     "Review domain history and reputation")
item(180, "medium", S, "a11y_seo_checker.py", PAGE,
     {"path": "score", "gte": 80},
     "Meet WCAG accessibility basics")
item(181, "medium", S, "html_validator.py", PAGE,
     {"path": "summary.errors", "eq": 0},
     "Pass W3C validation")
item(182, "low", M, fix="Show a compliant cookie banner")
item(183, "high", M, fix="Handle migrations, parameters and status codes correctly")

# --- 13. Images / Video -----------------------------------------------------
item(184, "medium", S, "image_inventory.py", PAGE,
     {"path": "count", "gte": 1},
     "Audit sitewide image usage")
item(185, "medium", S, "image_weight_audit.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Optimize images")
item(186, "high", S, "image_inventory.py", PAGE,
     {"path": "missing_alt", "eq": 0},
     "Meaningful alt text on informative images")
item(187, "high", S, "image_weight_audit.py",
     # Broken images cannot be found without asking for each one, so this item
     # pays for the HEAD requests. `broken_image_count` is absent when no status
     # was collected, which the runner reads as NO_DATA rather than "none broken".
     ["{url}", "--fetch-images"],
     {"path": "broken_image_count", "eq": 0},
     "Fix broken images")
item(188, "low", L, fix="Use original contextual images, limit stock photography")
item(189, "medium", S, "image_weight_audit.py", PAGE,
     {"path": "modern_format_count", "gte": 1},
     "Modern formats and responsive images")
item(190, "medium", S, "video_schema_checker.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Implement video SEO essentials: VideoObject, thumbnail, transcript")

# --- 14. Competition --------------------------------------------------------
item(191, "medium", L, fix="Identify the top 3-5 competitors in the SERP")
item(192, "medium", M, fix="Benchmark yourself against competitors on key metrics")
item(193, "medium", M, fix="Document each competitor's top 10 keywords")
item(194, "low", M, fix="Track competitors' average positions")
item(195, "medium", M, fix="List top-ranking keywords across all players")

# --- 15. Local SEO ----------------------------------------------------------
item(196, "medium", L, fix="Determine whether the site needs local traffic")
# local_seo_checker.py reports LocalBusiness schema, map embeds, review links
# and phone consistency — never the title tag. Whether a title is localised for
# its city and service is a market judgement.
item(197, "medium", L, fix="Localized title tags")
item(198, "high", S, "local_seo_checker.py", PAGE,
     {"path": "local_business_nodes", "gte": 1},
     "Implement LocalBusiness structured data")
item(199, "high", M, fix="Create and optimize the Google Business Profile — follow resources/playbooks/local-seo.md")
item(200, "high", S, "local_seo_checker.py", PAGE,
     {"path": "issues", "none_severity": ["critical", "high"]},
     "Local SEO fundamentals: NAP, GBP, reviews")

# --------------------------------------------------------------------------
# Beyond Plerdy — what the toolkit checks that the 200-point list does not.
# --------------------------------------------------------------------------

EXTRA = [
    ("GEO-001", "geo_ai", "llms.txt present and well-formed", "high", S,
     "llms_txt_checker.py", PAGE, {"path": "exists", "truthy": True},
     "Publish /llms.txt describing the site and mapping its key sections"),
    ("GEO-002", "geo_ai", "llms.txt quality score", "medium", S,
     "llms_txt_checker.py", PAGE, {"path": "quality.score", "gte": 60},
     "Flesh out llms.txt: title, description, sections, links"),
    ("GEO-003", "geo_ai", "AI crawler policy is explicit", "medium", S,
     "ai_crawler_policy_matrix.py", PAGE,
     # The matrix reports an `alignment` per crawler and never the words "not
     # managed". Allowing everything while publishing no llms.txt is precisely
     # the policy this item calls inexplicit.
     {"path": "rows", "field": "alignment",
      "value_map": {"documented": "pass", "robots_only": "pass",
                    "allowed_without_llms_txt": "fail"}},
     "Declare explicit rules for GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot"),
    ("GEO-004", "geo_ai", "Answer blocks present for AEO", "medium", S,
     "answer_block_scanner.py", PAGE, {"path": "score", "gte": 70},
     "Add direct answers, definitions, lists and tables for featured snippets"),
    ("GEO-005", "geo_ai", "Content is citation-ready for AI search", "high", S,
     "citation_readiness.py", PAGE, {"path": "score", "gte": 60},
     "Back factual claims with sources, add cite/blockquote, populate sameAs"),
    ("GEO-006", "geo_ai", "Entity is resolvable (Wikidata / KG)", "medium", S,
     "entity_checker.py", PAGE, {"path": "summary.sameas_missing_critical", "eq": 0},
     "Populate sameAs with key profiles and establish a Wikidata link"),
    ("GEO-007", "geo_ai", "IndexNow configured", "low", S,
     "indexnow_checker.py", ["{url}", "--key", "{indexnow_key}"],
     {"path": "key_valid", "truthy": True},
     "Configure IndexNow for instant reindexing in Bing/Yandex"),
    ("TECH-001", "technical", "Modern schema types only (no HowTo/FAQ misuse)", "high", S,
     "rich_results_guard.py", PAGE, {"path": "summary.warnings", "eq": 0},
     "Remove HowTo (deprecated) and FAQPage outside gov/health sites"),
    ("TECH-002", "technical", "Font loading does not block render", "low", S,
     "font_audit.py", PAGE, {"path": "issues", "none_severity": ["critical", "high"]},
     "Preload key fonts, use font-display: swap"),
    ("TECH-003", "technical", "LCP subparts within budget", "medium", S,
     "lcp_subparts.py", PAGE, {"path": "subparts.ttfb_ms", "lte": 800},
     "Reduce TTFB and LCP resource load delay"),
    ("CONT-001", "content", "No content decay on key pages", "medium", M,
     None, None, None,
     "Track pages losing traffic (requires a GSC export)"),
    # Lab Core Web Vitals from a local browser trace, kept apart from the CrUX
    # field data pagespeed.py reports (SP-108, SP-113). Field data is the better
    # evidence and wins whenever it exists — it just does not exist for
    # low-traffic URLs, which is when a controlled run is the only measurement
    # available. One number made out of both claims is the conflation this
    # registry refuses. Without --cwv-json the file placeholder is unresolved and
    # all three report NO_DATA with that as the reason.
    ("SP-214", "speed", "LCP within budget in a local trace (lab)", "medium", S,
     "cwv_metrics.py", ["{cwv_json}"], {"path": "lcp_ms", "lte": 2500},
     "Reduce the largest contentful paint below 2.5s: server response, render-blocking "
     "resources, image weight"),
    ("SP-215", "speed", "CLS within budget in a local trace (lab)", "medium", S,
     "cwv_metrics.py", ["{cwv_json}"], {"path": "cls", "lte": 0.1},
     "Reserve space for images, ads and embeds; avoid inserting content above existing "
     "content"),
    ("SP-216", "speed", "Main thread not blocked in a local trace (TBT, lab proxy for INP)",
     "medium", S, "cwv_metrics.py", ["{cwv_json}"], {"path": "tbt_ms", "lte": 200},
     "Break up long tasks and defer third-party JavaScript. INP needs a real "
     "interaction and cannot be measured from a page load, so TBT stands in for it"),
]


def load_titles() -> dict[int, str]:
    """Read item titles from the extracted Plerdy checklist titles file."""
    path = os.path.join(SKILL_DIR, "resources", "config", "plerdy-titles.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return {int(k): v for k, v in json.load(f).items()}
    return {}


# Which evidence answers an LLM item, which is not the same question as which
# checklist category it sits in. Grouping by lens lets one agent read one slice
# of the page once; grouping by category would make four agents re-read the same
# body copy. Every llm item must appear here — main() refuses to build otherwise,
# so a new item cannot silently fall out of the dispatch.
LENS = {
    "copy": ["MS-024", "MS-025", "CN-037", "CN-042", "CN-043", "CN-046",
             "CN-047", "CN-049", "CN-050", "CN-058", "CN-064", "CN-067",
             "KW-074", "KW-075", "KW-077", "MD-188"],
    "layout": ["CN-034", "CN-035", "CN-051", "CN-052", "CN-059", "CN-060",
               "CN-061", "CN-062", "CN-063", "MB-094", "MB-101", "MB-103",
               "AR-157", "AR-159", "AR-160", "AR-161"],
    # TE-165 (subdomain vs subdirectory) is filed under technical, but the
    # decision is almost always driven by language/region targeting.
    "locale": ["IN-126", "IN-130", "TE-165"],
    "market": ["CO-191", "LO-196", "LO-197"],
}
LENS_OF = {eid: lens for lens, ids in LENS.items() for eid in ids}


def build() -> list[dict]:
    titles = load_titles()
    out: list[dict] = []
    for key, prefix, label, (lo, hi) in CATEGORIES:
        for ref in range(lo, hi + 1):
            sev, source, script, args, rule, fix, warn = MAP.get(
                ref, ("medium", M, None, None, None, "", None))
            entry = {
                "id": f"{prefix}-{ref:03d}",
                "plerdy_ref": ref,
                "category": key,
                "category_label": label,
                "title": titles.get(ref, f"Item {ref}"),
                "severity": sev,
                "source": source,
            }
            if source == S:
                entry["check"] = {
                    "script": script,
                    "args": args,
                    "requires": REQUIRES.get(script, DEFAULT_REQUIRES),
                    "assert": rule,
                }
                if warn:
                    entry["check"]["warn"] = warn
            if source == L:
                entry["lens"] = LENS_OF.get(entry["id"], "")
            entry["effort"] = effort_for(entry)
            entry["fix"] = fix
            out.append(entry)

    for eid, cat, title, sev, source, script, args, rule, fix in EXTRA:
        label = "GEO / AI Search" if cat == "geo_ai" else next(
            (l for k, _p, l, _r in CATEGORIES if k == cat), "Beyond Plerdy")
        entry = {
            "id": eid,
            "plerdy_ref": None,
            "category": cat,
            "category_label": label,
            "title": title,
            "severity": sev,
            "source": source,
        }
        if source == S:
            entry["check"] = {
                "script": script,
                "args": args,
                "requires": REQUIRES.get(script, DEFAULT_REQUIRES),
                "assert": rule,
            }
        if source == L:
            entry["lens"] = LENS_OF.get(entry["id"], "")
        entry["effort"] = effort_for(entry)
        entry["fix"] = fix
        out.append(entry)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the SEO checklist registry")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--check", action="store_true",
                    help="Exit 1 if the on-disk registry is stale")
    a = ap.parse_args()

    items = build()
    unlensed = [i["id"] for i in items if i["source"] == L and not i.get("lens")]
    if unlensed:
        print(f"LLM items with no lens: {', '.join(unlensed)} — add them to LENS, "
              "otherwise no agent is responsible for answering them",
              file=sys.stderr)
        return 1
    # A content hash of the items, so a result file can say which registry it was
    # produced from. Without it, two runs whose item sets differ silently compare
    # as if they measured the same thing.
    registry_version = hashlib.sha256(
        json.dumps(items, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    payload = {
        "version": 1,
        "registry_version": registry_version,
        "item_count": len(items),
        "source": "Plerdy SEO Checklist (200) + 11 beyond-Plerdy checks",
        "categories": [{"key": k, "prefix": p, "label": l} for k, p, l, _ in CATEGORIES]
                      + [{"key": "geo_ai", "prefix": "GEO", "label": "GEO / AI Search"}],
        "items": items,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if a.check:
        if not os.path.exists(a.out):
            print("checklist.json missing — run without --check", file=sys.stderr)
            return 1
        with open(a.out, encoding="utf-8") as f:
            if f.read() != text:
                print("checklist.json is stale — regenerate it", file=sys.stderr)
                return 1
        print("checklist.json up to date")
        return 0

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)

    by_source: dict[str, int] = {}
    for i in items:
        by_source[i["source"]] = by_source.get(i["source"], 0) + 1
    scripts = {i["check"]["script"] for i in items if i.get("check")}
    print(f"Wrote {a.out}")
    print(f"  items: {len(items)}")
    for k in sorted(by_source):
        print(f"  {k:<7} {by_source[k]}")
    print(f"  unique scripts referenced: {len(scripts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
