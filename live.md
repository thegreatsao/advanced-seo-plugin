# SEO Checklist Audit

- **URL:** http://127.0.0.1:8000/
- **Mode:** `live`
- **Profile:** `default`
- **Run at:** 2026-08-04T14:44:04.950212+00:00
- **Registry:** `18b1b372a6ed`
- **Search Console:** not configured
- **Pages sampled:** 3

## Summary

> **What was audited** — The audited host is only reachable from the machine that ran this audit (--allow-private), so this describes a local or staging copy, not the site a visitor or a search engine sees. Anything that needs an outside service — PageSpeed, Search Console, index checks — could not be decided.

We checked 106 things on this site and 29 of them need work.
11 of those are quick fixes — a setting or a line of text, not a rebuild.
108 more could not be settled by measurement: they need a person's judgement, an account we do not have, or data that does not exist. They are listed, not hidden.

**SEO Score 77/100**

**Coverage 50%** — 106 / 214 (50% of the full registry, 214).

The two numbers are deliberately separate: a high score over thin coverage means little, and an item nobody could check is not evidence that the site failed it.

| Status | Count | Meaning |
|---|---|---|
| PASS | 77 | check passed |
| WARN | 3 | borderline, counts as half |
| FAIL | 26 | check failed — actionable |
| NO DATA | 37 | could not be determined (script error, missing credentials, missing field) |
| LLM | 36 | needs a language-model judgement — see LLM-QUEUE.md |
| MANUAL | 35 | needs a human — see the Manual section |

### By category

| Category | Score | Decided | Failed |
|---|---|---|---|
| Crawling & Indexing | 100/100 | 15 | 0 |
| Meta & Structured Data | 88/100 | 11 | 2 |
| Content | 64/100 | 14 | 6 |
| Keyword Analysis | 100/100 | 1 | 0 |
| Backlinks | 50/100 | 2 | 1 |
| Mobile | 79/100 | 9 | 3 |
| Speed | 75/100 | 2 | 0 |
| Security | 0/100 | 3 | 3 |
| International & Multilingual | 100/100 | 2 | 0 |
| Google | 57/100 | 8 | 3 |
| Website Architecture | 100/100 | 12 | 0 |
| Technical SEO Checks | 83/100 | 13 | 2 |
| Images / Video | 75/100 | 6 | 2 |
| Competition Analysis | — | 0 | 0 |
| Local SEO | 25/100 | 2 | 1 |
| GEO / AI Search | 50/100 | 6 | 3 |

## What to do first

Ordered by how much each matters against how much work it is — 11 of the 29 are quick.

### Security

*HTTPS, headers and the basics that keep a browser from warning your visitors. A warning screen costs the visit outright.*

**Force HTTPS Across the Site (Single Canonical Protocol)**  
`critical · low`  
Not found. Seen on 3 of 3 pages checked.  
What to do: Force HTTPS sitewide with a single canonical protocol

**Maintain a Valid TLS Certificate (HTTPS)**  
`critical · low`  
Not found. Seen on 3 of 3 pages checked.  
What to do: Maintain a valid TLS certificate

### Google

*What Google's own tools report about the site: indexing state, manual actions, the queries you actually rank for.*

**Optimize for AI Overviews & Zero-Click SERPs**  
`high · low`  
10, where at least 60 is expected. Seen on 2 of 3 pages checked.  
What to do: Optimize for AI Overviews and zero-click: citability, facts, sources

### Technical SEO Checks

*Configuration a visitor never sees but a crawler does: redirects, headers, sitemaps, structured-data validity.*

**Secure Pages & Eliminate Errors**  
`high · low`  
6, and no more than 3 is acceptable. Seen on 3 of 3 pages checked.  
What to do: Secure pages and eliminate errors

### GEO / AI Search

*Whether AI assistants and AI search can read, quote and attribute your content. A newer channel than Google, and it reads pages differently.*

**Content is citation-ready for AI search**  
`high · medium`  
10, where at least 60 is expected. Seen on 2 of 3 pages checked.  
What to do: Back factual claims with sources, add cite/blockquote, populate sameAs

### Meta & Structured Data

*The title and description Google shows in its results, plus the machine-readable markup behind them. This is what a searcher reads before deciding whether to click.*

**Avoid Overly Short Titles (<30 Characters)**  
`medium · low`  
5, where at least 30 is expected. Seen on 1 of 3 pages checked.  
What to do: Titles under 30 characters are usually too vague to match intent

**Add Social Preview Tags (Open Graph & Twitter Cards)**  
`medium · low`  
None found; at least 80 is expected. Seen on 2 of 3 pages checked.  
What to do: Fill in Open Graph and Twitter Card tags

### Security

*HTTPS, headers and the basics that keep a browser from warning your visitors. A warning screen costs the visit outright.*

**Harden Security Headers (CSP, Permissions-Policy, Referrer-Policy)**  
`medium · low`  
None found; at least 80 is expected. Seen on 3 of 3 pages checked.  
What to do: Configure CSP, Permissions-Policy and Referrer-Policy

### Google

*What Google's own tools report about the site: indexing state, manual actions, the queries you actually rank for.*

**Install & Configure Google Analytics 4**  
`medium · low`  
None found; at least 1 is expected. Seen on 2 of 3 pages checked.  
What to do: Install and configure Google Analytics 4

**Optimize for Featured Snippets**  
`medium · low`  
56, where at least 70 is expected. Seen on 2 of 3 pages checked.  
What to do: Optimize for featured snippets: direct answers, lists, tables

### Technical SEO Checks

*Configuration a visitor never sees but a crawler does: redirects, headers, sitemaps, structured-data validity.*

**Configure Server Rewrites & Headers**  
`medium · low`  
No critical/high/medium issues reported. Seen on 3 of 3 pages checked.  
What to do: Configure server rewrites and cache/compression headers

### Content

*Whether each page says something substantial, once, in a way a reader and a search engine can both follow. Thin or duplicated pages compete with your own better ones.*

**Show Author and Publisher Clearly**  
`high · high`  
None found; at least 1 is expected. Seen on 2 of 3 pages checked.  
What to do: Show author and publisher clearly

**Strengthen Authorship & E-E-A-T Signals**  
`high · high`  
None found; at least 60 is expected. Seen on 2 of 3 pages checked.  
What to do: Strengthen authorship and E-E-A-T: author, credentials, first-hand experience, sourced claims

### Local SEO

*Everything that makes a business findable in its own town: address, opening hours, map, reviews, and the markup that ties them together.*

**Implement Local Business Structured Data**  
`high · high`  
None found; at least 1 is expected. Seen on 2 of 3 pages checked.  
What to do: Implement LocalBusiness structured data

**Apply Local SEO Fundamentals (NAP, GBP, Reviews)**  
`high · high`  
No critical/high/medium issues reported. Seen on 2 of 3 pages checked.  
What to do: Local SEO fundamentals: NAP, GBP, reviews

### Mobile

*How the site behaves on a phone, which is what Google measures and where most visitors arrive.*

**Use Responsive Images**  
`medium · medium`  
None found; at least 1 is expected. Seen on 2 of 3 pages checked.  
What to do: Use srcset/sizes for responsive images

**Optimize Image Formats & Compression**  
`medium · medium`  
None found; at least 1 is expected. Seen on 2 of 3 pages checked.  
What to do: Move to WebP/AVIF and compress images

### Speed

*How quickly the page becomes usable. Slow pages lose visitors before they read anything, and speed is a ranking factor in its own right.*

**Run a Comprehensive Speed Audit**  
`medium · medium`  
No critical/high/medium issues reported. Seen on 2 of 3 pages checked.  
What to do: Shorten the critical request chain

### Images / Video

*Images and video: their weight, their alt text and their markup. Usually the heaviest thing on a page and the easiest to fix.*

**Audit Sitewide Image Usage**  
`medium · medium`  
None found; at least 1 is expected. Seen on 2 of 3 pages checked.  
What to do: Audit sitewide image usage

**Use Modern Formats & Responsive Images**  
`medium · medium`  
None found; at least 1 is expected. Seen on 2 of 3 pages checked.  
What to do: Modern formats and responsive images

### GEO / AI Search

*Whether AI assistants and AI search can read, quote and attribute your content. A newer channel than Google, and it reads pages differently.*

**Answer blocks present for AEO**  
`medium · medium`  
56, where at least 70 is expected. Seen on 2 of 3 pages checked.  
What to do: Add direct answers, definitions, lists and tables for featured snippets

**Entity is resolvable (Wikidata / KG)**  
`medium · medium`  
Found 4; there should be none. Seen on 3 of 3 pages checked.  
What to do: Populate sameAs with key profiles and establish a Wikidata link

### Technical SEO Checks

*Configuration a visitor never sees but a crawler does: redirects, headers, sitemaps, structured-data validity.*

**Add a Favicon**  
`low · low`  
Not found. Seen on 1 of 3 pages checked.  
What to do: Add a favicon

### Content

*Whether each page says something substantial, once, in a way a reader and a search engine can both follow. Thin or duplicated pages compete with your own better ones.*

**Balance Evergreen and Fresh Content**  
`medium · high`  
65, where at least 70 is expected. Seen on 1 of 3 pages checked.  
What to do: Refresh evergreen material and balance it with new content

**Publish an Up-to-Date Privacy Policy**  
`medium · high`  
None found; at least 1 is expected. Seen on 2 of 3 pages checked.  
What to do: Publish an up-to-date privacy policy and link to it

**Provide a Clear, Easy-to-Find Contact Page**  
`medium · high`  
None found; at least 1 is expected. Seen on 1 of 3 pages checked.  
What to do: Provide a clear, easy-to-find contact page

**Show Publication and Updated Dates**  
`medium · high`  
None found; at least 1 is expected. Seen on 1 of 3 pages checked.  
What to do: Show publication and updated dates

### Backlinks

*Who links to you from elsewhere. Links remain one of the strongest ranking signals, and judging their quality needs a link index this audit does not have — most of these items are for a human.*

**Fix Broken Backlinks (Redirect or Update Link)**  
`medium · high`  
Found 3; there should be none.  
What to do: Fix broken links: update the URL or add a redirect

### Mobile

*How the site behaves on a phone, which is what Google measures and where most visitors arrive.*

**Ensure Favicon Displays in Mobile SERPs**  
`low · medium`  
Not found. Seen on 1 of 3 pages checked.  
What to do: Add a favicon - it shows in mobile SERPs


## Full checklist

### Crawling & Indexing

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| PASS | critical | CI-001 | Ensure URL Is Indexed | all 1 verdict value(s) acceptable |
| PASS | critical | CI-003 | Page Returns 200 (OK) Status Code | rows.0.status = 200 (want 200) |
| PASS | critical | CI-004 | Allow Indexing via Meta Robots / X-Robots-Tag | 3/3 pages: no match for 'noindex' |
| PASS | critical | CI-005 | Do Not Block the URL in robots.txt | rows.0.robots_allowed = True |
| PASS | critical | CI-009 | Serve Content at a Single Canonical URL | 3/3 pages: all 1 verdict value(s) acceptable |
| PASS | critical | CI-013 | Do Not Block Critical CSS/JS/Images in robots.txt | 3/3 pages: len(allowed_urls) = 3 (want gte 3) |
| PASS | critical | CI-015 | Eliminate 5xx Server Errors | rows.0.status = 200 (want lt 500) |
| PASS | high | CI-002 | Ensure Important Content Is Indexed | summary.urls = 6 (want gte 1) |
| PASS | high | CI-008 | Make the URL Discoverable via Internal Links/Navigation | orphan_pages.count = 0 (want 0) |
| NO DATA | high | CI-010 | Align Google-Selected and Declared Canonical | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| PASS | high | CI-011 | Avoid Canonical/Indexing Mixed Signals | 3/3 pages: all 1 verdict value(s) acceptable |
| PASS | high | CI-014 | Use Correct Redirect Codes (No Chains/Loops) | 3/3 pages: has_loop = False |
| PASS | high | CI-016 | Provide Meaningful Image Alt Text | 3/3 pages: missing_alt = 0 (want 0) |
| PASS | high | CI-019 | Noindex System & Search Pages (/search, /cart, /checkout, /login) | 3/3 pages: len(allowed_urls) = 0 (want lte 0) |
| PASS | medium | CI-006 | Declare Sitemap Location in robots.txt | 3/3 pages: len(sitemaps) = 1 (want gte 1) |
| MANUAL | medium | CI-007 | Submit Sitemap to Search Engines | requires a human |
| PASS | medium | CI-012 | Use a Friendly URL Structure | 3/3 pages: rows.0.score = 100 (want gte 70) |
| NO DATA | medium | CI-017 | Validate HTML (W3C) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| MANUAL | medium | CI-018 | Analyze Logs & Manage Crawl Budget | requires a human |

### Meta & Structured Data

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | medium | MS-021 | Avoid Overly Short Titles (<30 Characters) | 1/3 pages: len(title) = 5 (want gte 30) |
| FAIL | medium | MS-033 | Add Social Preview Tags (Open Graph & Twitter Cards) | 2/3 pages: score = 0 (want gte 80) |
| PASS | critical | MS-026 | Ensure Every Page Has a Title | 3/3 pages: title = 'Fixture Bakery â\x80\x94 fresh bread in Vilnius' |
| PASS | high | MS-020 | Keep Page Titles Concise (Avoid SERP Truncation) | 3/3 pages: len(title) = 41 (want lte 60) |
| PASS | high | MS-022 | Remove Duplicate Page Titles (Handle Canonical/Pagination Correctly) | len(exact_duplicates) = 0 (want eq 0) |
| NO DATA | high | MS-023 | Detect & Resolve Keyword Cannibalization | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| PASS | high | MS-027 | Write Unique, Compelling Meta Descriptions | 3/3 pages: meta_description = 'A small fixture site used to exercise the SEO checklist end to end: six pages, a sitemap, a robots.txt with something i |
| PASS | high | MS-032 | Implement & Validate Structured Data (Where Relevant) | 3/3 pages: summary.errors = 0 (want 0) |
| LLM | medium | MS-024 | Place Primary Keyword Early in the Title | awaiting LLM judgement |
| LLM | medium | MS-025 | Make Titles Accurately Describe the Content | awaiting LLM judgement |
| PASS | medium | MS-028 | Fill Missing Meta Descriptions (High-Value Pages First) | 3/3 pages: meta_description = 'A small fixture site used to exercise the SEO checklist end to end: six pages, a sitemap, a robots.txt with something i |
| PASS | medium | MS-029 | Eliminate Duplicate Meta Descriptions | summary.exact_duplicate_groups = 0 (want 0) |
| PASS | low | MS-030 | Keep Meta Descriptions ~150–160 Characters (Clear & Relevant) | 3/3 pages: len(meta_description) = 145 (want 120-165) |
| PASS | low | MS-031 | Do Not Use Meta Keywords | 3/3 pages: meta_keywords = None |

### Content

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | high | CN-057 | Show Author and Publisher Clearly | 2/3 pages: len(signals.authors) = 0 (want gte 1) |
| FAIL | high | CN-068 | Strengthen Authorship & E-E-A-T Signals | 2/3 pages: score = 0 (want gte 60) |
| FAIL | medium | CN-038 | Balance Evergreen and Fresh Content | 1/3 pages: score = 65 (want gte 70) |
| FAIL | medium | CN-040 | Publish an Up-to-Date Privacy Policy | 2/3 pages: len(signals.privacy_links) = 0 (want gte 1) |
| FAIL | medium | CN-044 | Provide a Clear, Easy-to-Find Contact Page | 1/3 pages: len(signals.trust_links) = 0 (want gte 1) |
| FAIL | medium | CN-056 | Show Publication and Updated Dates | 1/3 pages: len(dates) = 0 (want gte 1) |
| LLM | critical | CN-060 | Do Not Cloak | awaiting LLM judgement |
| PASS | critical | CN-065 | Use a Clear H1 Per Page | 3/3 pages: len(h1) = 1 (want eq 1) |
| PASS | high | CN-039 | Eliminate Low-Value/Thin Pages | summary.thin_pages = 0 (want 0) |
| PASS | high | CN-041 | Eliminate Internal Duplicate Content | summary.exact_duplicate_groups = 0 (want 0) |
| LLM | high | CN-043 | Avoid Scraped/Plagiarized Content | awaiting LLM judgement |
| PASS | high | CN-048 | Use Hierarchical Headings and Semantic HTML | 3/3 pages: len(h2) = 5 (want gte 1) |
| LLM | high | CN-050 | Follow Google Search Essentials (Quality/Spam Policies) | awaiting LLM judgement |
| NO DATA | high | CN-051 | Avoid Intrusive Interstitials (Especially on Mobile) | missing input 'rendered_json' |
| PASS | high | CN-054 | Ensure Lazy-Loaded Content Is Discoverable | 3/3 pages: summary.lazy_lcp_candidates = 0 (want 0) |
| LLM | high | CN-059 | Avoid Hidden Text Meant to Manipulate | awaiting LLM judgement |
| LLM | high | CN-061 | Avoid Doorway Pages | awaiting LLM judgement |
| LLM | high | CN-067 | Publish People-First Content (AI-Assisted Is Fine) | awaiting LLM judgement |
| NO DATA | medium | CN-034 | Ensure Readable Font Sizes | missing input 'rendered_json' |
| NO DATA | medium | CN-035 | Make Hyperlinks Clear and Distinct | missing input 'rendered_json' |
| PASS | medium | CN-036 | Ensure Sufficient Text Contrast | 3/3 pages: checks.inline_contrast_candidates = 0 (want 0) |
| LLM | medium | CN-042 | Address External Duplicates/Syndication | awaiting LLM judgement |
| MANUAL | medium | CN-045 | Run Content Gap Analysis | requires a human |
| LLM | medium | CN-046 | Review Copy Quality and Content Classification | awaiting LLM judgement |
| LLM | medium | CN-047 | Check Grammar and Spelling | awaiting LLM judgement |
| LLM | medium | CN-049 | Target Topics and Queries (Not Just Keywords) | awaiting LLM judgement |
| LLM | medium | CN-052 | Limit Heavy Above-the-Fold Ads | awaiting LLM judgement |
| PASS | medium | CN-053 | Avoid Critical Content in iFrames | 3/3 pages: raw.word_count = 409 (want gte 300) |
| LLM | medium | CN-055 | Make Infinite Scroll Crawlable (Paginated URLs) | awaiting LLM judgement |
| LLM | medium | CN-062 | Avoid Excessive Ad Density | awaiting LLM judgement |
| LLM | medium | CN-063 | Do Not Overuse Pop-Ups | awaiting LLM judgement |
| PASS | medium | CN-066 | Use H2 Subheadings for Structure | 3/3 pages: len(h2) = 5 (want gte 2) |
| MANUAL | medium | CONT-001 | No content decay on key pages | requires a human |
| LLM | low | CN-037 | Differentiate Primary vs. Supplementary Content | awaiting LLM judgement |
| LLM | low | CN-058 | Avoid Content Flagged by SafeSearch | awaiting LLM judgement |
| LLM | low | CN-064 | Use Clear Calls to Action | awaiting LLM judgement |

### Keyword Analysis

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| MANUAL | high | KW-069 | Do Keyword Research and Set Benchmarks | requires a human |
| NO DATA | high | KW-070 | Own Your Branded Query (Homepage Ranks #1) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| NO DATA | high | KW-071 | Is there evidence of keyword duplication or overuse? | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| LLM | high | KW-072 | Use the Primary Topic in the Title | awaiting LLM judgement |
| LLM | high | KW-073 | Include the Primary Keyword in the H1 | awaiting LLM judgement |
| LLM | medium | KW-074 | Include the Primary Keyword (or Close Variant) in an H2 | awaiting LLM judgement |
| LLM | medium | KW-075 | Include the Primary Keyword in the Meta Description (for CTR) | awaiting LLM judgement |
| PASS | medium | KW-076 | Include the Primary Keyword in Body Copy | 3/3 pages: target_keyword = 'acidity slows' |
| LLM | medium | KW-077 | Include the Primary Keyword in the Opening Paragraph | awaiting LLM judgement |

### Backlinks

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | medium | BL-083 | Fix Broken Backlinks (Redirect or Update Link) | summary.broken_links = 3 (want 0) |
| MANUAL | high | BL-078 | Assess Backlink Health & Authority | requires a human |
| MANUAL | high | BL-079 | Identify Spammy Referring Domains | requires a human |
| MANUAL | high | BL-088 | Earn Topically Relevant Backlinks to the URL | requires a human |
| MANUAL | high | BL-089 | Ensure the Disavow File Doesn’t Include Valuable Links | requires a human |
| MANUAL | medium | BL-080 | Use a Disavow File Only When Necessary | requires a human |
| PASS | medium | BL-081 | Keep Anchor Text Natural and Varied | summary.overused_exact_match_targets = 0 (want 0) |
| MANUAL | medium | BL-082 | Monitor and Reclaim Lost Backlinks | requires a human |
| NO DATA | medium | BL-084 | Check for Unnatural Link Concentration from Single Domains | missing input 'links_csv' |
| NO DATA | medium | BL-087 | Track Total Linking Root Domains | missing input 'links_csv' |
| MANUAL | low | BL-085 | Do Not Optimize for Domain Age | requires a human |
| NO DATA | low | BL-086 | Track Total Backlinks (Quality Over Quantity) | missing input 'links_csv' |
| MANUAL | low | BL-090 | Create and Optimize Social Profiles Where Your Audience Is | requires a human |
| MANUAL | low | BL-091 | Publish on LinkedIn Articles (and Company Page) | requires a human |
| MANUAL | low | BL-092 | Pitch and Appear on Relevant Podcasts | requires a human |

### Mobile

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | medium | MB-096 | Use Responsive Images | 2/3 pages: responsive_count = 0 (want gte 1) |
| FAIL | medium | MB-097 | Optimize Image Formats & Compression | 2/3 pages: modern_format_count = 0 (want gte 1) |
| FAIL | low | MB-104 | Ensure Favicon Displays in Mobile SERPs | 1/3 pages: favicon = None |
| PASS | critical | MB-093 | Ensure Responsive Layout (Mobile-First) | 3/3 pages: viewport = 'width=device-width, initial-scale=1' |
| NO DATA | high | MB-094 | Avoid Intrusive Interstitials on Mobile | missing input 'rendered_json' |
| PASS | high | MB-105 | Ensure Parity: Content, Meta & Directives Match Desktop | 3/3 pages: len(diffs) = 0 (want eq 0) |
| PASS | medium | MB-095 | Keep Mobile Page Weight Light | 3/3 pages: 0 match(es) for '(?i)large\|oversize\|weight', limit 5 |
| PASS | medium | MB-098 | Serve Properly Sized Images | 3/3 pages: 0 match(es) for '(?i)size\|dimension', limit 10 |
| MANUAL | medium | MB-099 | Check Google Search Console (Mobile Signals) | Search Console API exposes no mobile-usability endpoint — check the UI |
| PASS | medium | MB-100 | Fix Mobile UX Issues (see UX) | 3/3 pages: no critical/high issues |
| NO DATA | medium | MB-103 | Make Tap Targets Easy to Click | missing input 'rendered_json' |
| MANUAL | medium | MB-106 | Test on Real Devices (Pre-/Post-Release) | requires a human |
| LLM | low | MB-101 | Make Mobile Navigation Thumb-Friendly | awaiting LLM judgement |
| PASS | low | MB-102 | Optimize Video for Mobile | 3/3 pages: no critical/high/medium issues |

### Speed

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| NO DATA | critical | SP-108 | Pass Core Web Vitals (Field Data) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| NO DATA | critical | SP-113 | Meet Core Web Vitals Thresholds | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| NO DATA | high | SP-107 | Load Content Fast (Prioritize Above-the-Fold) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| NO DATA | high | SP-111 | Check Core Web Vitals (Desktop) in Search Console | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| NO DATA | high | SP-112 | Check Core Web Vitals (Mobile) in Search Console | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| PASS | medium | SP-109 | Fix Common Speed Traps | 3/3 pages: blocking_third_party_count = 0 (want 0) |
| WARN | medium | SP-110 | Run a Comprehensive Speed Audit | 2/3 pages: 1 issue(s) at critical/high/medium: Render-blocking stylesheet; within warn range (no critical/high issues) |
| NO DATA | medium | SP-214 | LCP within budget in a local trace (lab) | missing input 'cwv_json' |
| NO DATA | medium | SP-215 | CLS within budget in a local trace (lab) | missing input 'cwv_json' |
| NO DATA | medium | SP-216 | Main thread not blocked in a local trace (TBT, lab proxy for INP) | missing input 'cwv_json' |

### Security

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | critical | SE-117 | Force HTTPS Across the Site (Single Canonical Protocol) | 3/3 pages: https = False |
| FAIL | critical | SE-118 | Maintain a Valid TLS Certificate (HTTPS) | 3/3 pages: https = False |
| FAIL | medium | SE-120 | Harden Security Headers (CSP, Permissions-Policy, Referrer-Policy) | 3/3 pages: score = 0 (want gte 80) |
| NO DATA | critical | SE-114 | Run Malware & Security Checks | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| NO DATA | critical | SE-116 | Ensure No Hacked Content or Malware | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| NO DATA | medium | SE-115 | Enable HSTS (HTTP Strict Transport Security) | header_values.strict-transport-security missing |
| NO DATA | medium | SE-119 | Make Cookie Banners Lightweight (No CLS) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |

### International & Multilingual

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| PASS | high | IN-122 | Implement Valid hreflang (With Return Tags) | 3/3 pages: summary.critical = 0 (want 0) |
| NO DATA | medium | IN-121 | Configure Geo-Targeting Signals | checks.x_default.passed missing |
| PASS | medium | IN-123 | Make Page Language Obvious | 3/3 pages: lang = 'en' |
| MANUAL | medium | IN-124 | Avoid Forced Geo/Language Redirects | requires a human |
| LLM | medium | IN-126 | Provide High-Quality, Human-Reviewed Translations | awaiting LLM judgement |
| NO DATA | medium | IN-127 | Use a Clear International URL Structure | checks.protocol_consistency.passed missing |
| NO DATA | medium | IN-128 | Serve the Correct Localized Page | checks.self_reference.passed missing |
| MANUAL | low | IN-125 | Define International Audiences and Markets | requires a human |
| MANUAL | low | IN-129 | Earn Local Backlinks in Target Markets | requires a human |
| LLM | low | IN-130 | Clarify Site Type: Multilingual, Multiregional, or Both | awaiting LLM judgement |

### Google

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | high | GO-145 | Optimize for AI Overviews & Zero-Click SERPs | 2/3 pages: score = 10 (want gte 60) |
| FAIL | medium | GO-131 | Install & Configure Google Analytics 4 | 2/3 pages: len(measurement_ids) = 0 (want gte 1) |
| FAIL | medium | GO-144 | Optimize for Featured Snippets | 2/3 pages: score = 56 (want gte 70) |
| MANUAL | critical | GO-141 | Check for Manual Actions | Search Console API exposes no manual-actions endpoint — check the UI |
| MANUAL | high | GO-133 | Set Up Google Search Console (Domain Property) | requires a human |
| NO DATA | high | GO-134 | Resolve Search Console Issues | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| PASS | high | GO-136 | Provide Clean XML Sitemaps | no critical/high/medium issues |
| MANUAL | high | GO-142 | Fix Crawl & Indexing Issues | Search Console API exposes no Index Coverage endpoint — check the UI |
| PASS | medium | GO-132 | Prevent GA4 Tag Duplication | 3/3 pages: len(duplicates) = 0 (want eq 0) |
| NO DATA | medium | GO-135 | Use URL Inspection & Rendered HTML | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| PASS | medium | GO-137 | Reconcile Indexed Pages vs. Sitemaps | summary.orphan_pages = 0 (want 0) |
| PASS | medium | GO-138 | Remove Invalid URLs from Sitemaps | no match for '(?i)404\|redirect\|noindex' |
| NO DATA | low | GO-139 | Monitor & Improve Brand SERPs | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| MANUAL | low | GO-140 | Provide a Google News Sitemap (If Eligible) | requires a human |
| PASS | low | GO-143 | Optimize for Sitelinks & Sitelinks Search Box | 3/3 pages: no match for '(?i)WebSite\|SearchAction' |

### Website Architecture

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| PASS | high | AR-150 | Remove Redirect Chains and Loops | 3/3 pages: total_hops = 0 (want lte 1) |
| PASS | high | AR-151 | Provide a Correct robots.txt | 3/3 pages: status = 200 (want 200) |
| PASS | high | AR-162 | Strengthen Internal Links and Remove Orphans | no critical/high issues |
| PASS | medium | AR-146 | Check Pagination | 3/3 pages: no critical/high issues |
| PASS | medium | AR-147 | Use Short, Descriptive URLs | 3/3 pages: rows.0.param_count = 0 (want lte 2) |
| PASS | medium | AR-149 | Eliminate Internal Redirects | summary.internal_redirects = 0 (want 0) |
| PASS | medium | AR-152 | Block Crawl Strategically with robots.txt | 3/3 pages: user_agents = {'*': {'allow': [], 'disallow': ['/private/', '/search', '/cart', '/checkout', '/login']}} |
| PASS | medium | AR-153 | Design Clear Topic Hubs (Silos) | 3/3 pages: score = 100 (want gte 70) |
| PASS | medium | AR-154 | Optimize E-commerce Category Pages | 3/3 pages: no critical/high/medium issues |
| MANUAL | medium | AR-156 | Provide Helpful 404 Pages | requires a human |
| PASS | medium | AR-158 | Implement Breadcrumbs (UI + Schema) | 3/3 pages: no match for '(?i)BreadcrumbList' |
| LLM | medium | AR-161 | Design Clear Menus (Header & Mobile) | awaiting LLM judgement |
| PASS | medium | AR-163 | Control Faceted Navigation (E-commerce) | 3/3 pages: no critical/high/medium issues |
| MANUAL | medium | AR-164 | Handle Out-of-Stock/Discontinued Products (301/410 + UX) | requires a human |
| MANUAL | low | AR-148 | Visualize Site Architecture | requires a human |
| PASS | low | AR-155 | Use Consistent, Descriptive URL Slugs | 3/3 pages: len(rows.0.flags) = 0 (want eq 0) |
| LLM | low | AR-157 | Use Tag Pages Strategically | awaiting LLM judgement |
| LLM | low | AR-159 | Simplify Primary Navigation | awaiting LLM judgement |
| LLM | low | AR-160 | Optimize Footer Navigation | awaiting LLM judgement |

### Technical SEO Checks

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | high | TE-175 | Secure Pages & Eliminate Errors | 3/3 pages: len(headers_missing) = 6 (want lte 3) |
| FAIL | low | TE-166 | Add a Favicon | 1/3 pages: favicon = None |
| NO DATA | critical | TE-171 | Run Blocklist & Safe-Browsing Checks | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| PASS | high | TE-168 | Fix Broken & Redirected Links | summary.broken = 0 (want 0) |
| PASS | high | TE-169 | Optimize JavaScript Rendering & Crawlability | 3/3 pages: raw.internal_link_count = 9 (want gte 1) |
| PASS | high | TE-172 | Implement Structured Data Correctly | 3/3 pages: summary.errors = 0 (want 0) |
| PASS | high | TE-176 | Fix Canonicalization Issues | 3/3 pages: len(issues) = 0 (want eq 0) |
| MANUAL | high | TE-183 | Handle Migrations, Parameters & Status Codes | requires a human |
| PASS | high | TECH-001 | Modern schema types only (no HowTo/FAQ misuse) | 3/3 pages: summary.warnings = 0 (want 0) |
| NO DATA | medium | TE-167 | Monitor Site Uptime | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| WARN | medium | TE-170 | Configure Server Rewrites & Headers | 3/3 pages: 1 issue(s) at critical/high/medium: Compressible response is not Brotli/gzip encoded; within warn range (no critical/high issues) |
| MANUAL | medium | TE-173 | Fix Console Errors | requires a human |
| PASS | medium | TE-177 | Ensure No-JS Access & Crawlability | 3/3 pages: raw.title = 'Fixture Bakery â\x80\x94 fresh bread in Vilnius' |
| PASS | medium | TE-180 | Meet Accessibility (WCAG) Basics | 3/3 pages: score = 100 (want gte 80) |
| NO DATA | medium | TE-181 | Validate HTML (W3C) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| PASS | medium | TECH-003 | LCP subparts within budget | 3/3 pages: subparts.ttfb_ms = 1 (want lte 800) |
| LLM | low | TE-165 | Choose Subdomains or Subdirectories | awaiting LLM judgement |
| PASS | low | TE-174 | Minify & Optimize CSS | 3/3 pages: unminified_count = 0 (want 0) |
| NO DATA | low | TE-178 | Audit Neighboring Sites on the Server | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| NO DATA | low | TE-179 | Review Domain History & Reputation | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| MANUAL | low | TE-182 | Show a Compliant Cookie Banner | requires a human |
| PASS | low | TECH-002 | Font loading does not block render | 3/3 pages: no critical/high/medium issues |

### Images / Video

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | medium | MD-184 | Audit Sitewide Image Usage | 2/3 pages: count = 0 (want gte 1) |
| FAIL | medium | MD-189 | Use Modern Formats & Responsive Images | 2/3 pages: modern_format_count = 0 (want gte 1) |
| PASS | high | MD-186 | Provide Meaningful Alt Text | 3/3 pages: missing_alt = 0 (want 0) |
| PASS | high | MD-187 | Fix Broken Images | 1/1 pages: broken_image_count = 0 (want 0) |
| PASS | medium | MD-185 | Optimize Images | 3/3 pages: no critical/high/medium issues |
| PASS | medium | MD-190 | Implement Video SEO Essentials | 3/3 pages: no critical/high/medium issues |
| LLM | low | MD-188 | Use Original, Contextual Images (Limit Stock) | awaiting LLM judgement |

### Competition Analysis

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| LLM | medium | CO-191 | Identify Top 3–5 Competitors | awaiting LLM judgement |
| MANUAL | medium | CO-192 | Benchmark Competitors | requires a human |
| MANUAL | medium | CO-193 | Document Each Competitor’s Top 10 Keywords | requires a human |
| MANUAL | medium | CO-195 | List Top-Ranking Keywords (All Players) | requires a human |
| MANUAL | low | CO-194 | Track Competitors’ Average Positions | requires a human |

### Local SEO

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | high | LO-198 | Implement Local Business Structured Data | 2/3 pages: local_business_nodes = 0 (want gte 1) |
| MANUAL | high | LO-199 | Set Up & Optimize Google Business Profile | requires a human |
| WARN | high | LO-200 | Apply Local SEO Fundamentals (NAP, GBP, Reviews) | 2/3 pages: 1 issue(s) at critical/high/medium: No LocalBusiness JSON-LD found (nor any of its subtypes); within warn range (no critical/high issues) |
| LLM | medium | LO-196 | Confirm Local Traffic Need | awaiting LLM judgement |
| LLM | medium | LO-197 | Use Localized Title Tags | awaiting LLM judgement |

### GEO / AI Search

| Status | Sev | ID | Item | Evidence |
|---|---|---|---|---|
| FAIL | high | GEO-005 | Content is citation-ready for AI search | 2/3 pages: score = 10 (want gte 60) |
| FAIL | medium | GEO-004 | Answer blocks present for AEO | 2/3 pages: score = 56 (want gte 70) |
| FAIL | medium | GEO-006 | Entity is resolvable (Wikidata / KG) | 3/3 pages: summary.sameas_missing_critical = 4 (want 0) |
| PASS | high | GEO-001 | llms.txt present and well-formed | 3/3 pages: exists = True |
| PASS | medium | GEO-002 | llms.txt quality score | 3/3 pages: quality.score = 85 (want gte 60) |
| PASS | medium | GEO-003 | AI crawler policy is explicit | 3/3 pages: all 9 alignment value(s) acceptable |
| NO DATA | low | GEO-007 | IndexNow configured | missing input 'indexnow_key' |

## Requires a human

These cannot be scripted. Nothing here counts against the score.

- [ ] **GO-141** (critical) Check for Manual Actions — Check for manual actions in Search Console
- [ ] **KW-069** (high) Do Keyword Research and Set Benchmarks — Run keyword research and set position benchmarks
- [ ] **BL-078** (high) Assess Backlink Health & Authority — Assess backlink quality and authority (needs an external service or a GSC CSV export)
- [ ] **BL-079** (high) Identify Spammy Referring Domains — Identify spammy referring domains
- [ ] **BL-088** (high) Earn Topically Relevant Backlinks to the URL — Earn topically relevant backlinks to the target URL
- [ ] **BL-089** (high) Ensure the Disavow File Doesn’t Include Valuable Links — Verify the disavow file does not contain valuable links
- [ ] **GO-133** (high) Set Up Google Search Console (Domain Property) — Set up Google Search Console as a domain property
- [ ] **GO-142** (high) Fix Crawl & Indexing Issues — Resolve crawl and indexing issues
- [ ] **TE-183** (high) Handle Migrations, Parameters & Status Codes — Handle migrations, parameters and status codes correctly
- [ ] **LO-199** (high) Set Up & Optimize Google Business Profile — Create and optimize the Google Business Profile — follow resources/playbooks/local-seo.md
- [ ] **CI-007** (medium) Submit Sitemap to Search Engines — Submit the sitemap in Google Search Console and Bing Webmaster Tools
- [ ] **CI-018** (medium) Analyze Logs & Manage Crawl Budget — Analyze server logs for Googlebot UA: crawl frequency, 404s, parameterized URLs, crawl budget
- [ ] **CN-045** (medium) Run Content Gap Analysis — Run a content gap analysis against competitors
- [ ] **BL-080** (medium) Use a Disavow File Only When Necessary — Disavow only on clear spam - not as routine hygiene
- [ ] **BL-082** (medium) Monitor and Reclaim Lost Backlinks — Monitor and reclaim lost backlinks
- [ ] **MB-099** (medium) Check Google Search Console (Mobile Signals) — Review mobile signals in Google Search Console
- [ ] **MB-106** (medium) Test on Real Devices (Pre-/Post-Release) — Test on real devices before and after release
- [ ] **IN-124** (medium) Avoid Forced Geo/Language Redirects — Do not force geo or language redirects
- [ ] **AR-156** (medium) Provide Helpful 404 Pages — Helpful 404 page with navigation and search
- [ ] **AR-164** (medium) Handle Out-of-Stock/Discontinued Products (301/410 + UX) — Handle out-of-stock products via 301/410 plus clear UX
- [ ] **TE-173** (medium) Fix Console Errors — Fix browser console errors (chrome-devtools MCP: list_console_messages)
- [ ] **CO-192** (medium) Benchmark Competitors — Benchmark yourself against competitors on key metrics
- [ ] **CO-193** (medium) Document Each Competitor’s Top 10 Keywords — Document each competitor's top 10 keywords
- [ ] **CO-195** (medium) List Top-Ranking Keywords (All Players) — List top-ranking keywords across all players
- [ ] **CONT-001** (medium) No content decay on key pages — Track pages losing traffic (requires a GSC export)
- [ ] **BL-085** (low) Do Not Optimize for Domain Age — Do not optimize for domain age - it is not a ranking factor
- [ ] **BL-090** (low) Create and Optimize Social Profiles Where Your Audience Is — Create and maintain social profiles where the audience actually is
- [ ] **BL-091** (low) Publish on LinkedIn Articles (and Company Page) — Publish LinkedIn articles and maintain the company page
- [ ] **BL-092** (low) Pitch and Appear on Relevant Podcasts — Pitch and appear on relevant podcasts
- [ ] **IN-125** (low) Define International Audiences and Markets — Define target international markets and audiences
- [ ] **IN-129** (low) Earn Local Backlinks in Target Markets — Earn local backlinks in target markets
- [ ] **GO-140** (low) Provide a Google News Sitemap (If Eligible) — Add a Google News sitemap if the site qualifies
- [ ] **AR-148** (low) Visualize Site Architecture — Visualize the site architecture
- [ ] **TE-182** (low) Show a Compliant Cookie Banner — Show a compliant cookie banner
- [ ] **CO-194** (low) Track Competitors’ Average Positions — Track competitors' average positions

## Undetermined

Checks that ran but could not produce a verdict. Each one lowers coverage; none of them lowers the score.

| ID | Item | Why |
|---|---|---|
| CI-010 | Align Google-Selected and Declared Canonical | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| CI-017 | Validate HTML (W3C) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| MS-023 | Detect & Resolve Keyword Cannibalization | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| CN-034 | Ensure Readable Font Sizes | missing input 'rendered_json' |
| CN-035 | Make Hyperlinks Clear and Distinct | missing input 'rendered_json' |
| CN-051 | Avoid Intrusive Interstitials (Especially on Mobile) | missing input 'rendered_json' |
| KW-070 | Own Your Branded Query (Homepage Ranks #1) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| KW-071 | Is there evidence of keyword duplication or overuse? | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| BL-084 | Check for Unnatural Link Concentration from Single Domains | missing input 'links_csv' |
| BL-086 | Track Total Backlinks (Quality Over Quantity) | missing input 'links_csv' |
| BL-087 | Track Total Linking Root Domains | missing input 'links_csv' |
| MB-094 | Avoid Intrusive Interstitials on Mobile | missing input 'rendered_json' |
| MB-103 | Make Tap Targets Easy to Click | missing input 'rendered_json' |
| SP-107 | Load Content Fast (Prioritize Above-the-Fold) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| SP-108 | Pass Core Web Vitals (Field Data) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| SP-111 | Check Core Web Vitals (Desktop) in Search Console | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| SP-112 | Check Core Web Vitals (Mobile) in Search Console | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| SP-113 | Meet Core Web Vitals Thresholds | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| SE-114 | Run Malware & Security Checks | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| SE-115 | Enable HSTS (HTTP Strict Transport Security) | header_values.strict-transport-security missing |
| SE-116 | Ensure No Hacked Content or Malware | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| SE-119 | Make Cookie Banners Lightweight (No CLS) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| IN-121 | Configure Geo-Targeting Signals | checks.x_default.passed missing |
| IN-127 | Use a Clear International URL Structure | checks.protocol_consistency.passed missing |
| IN-128 | Serve the Correct Localized Page | checks.self_reference.passed missing |
| GO-134 | Resolve Search Console Issues | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| GO-135 | Use URL Inspection & Rendered HTML | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| GO-139 | Monitor & Improve Brand SERPs | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| TE-167 | Monitor Site Uptime | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| TE-171 | Run Blocklist & Safe-Browsing Checks | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| TE-178 | Audit Neighboring Sites on the Server | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| TE-179 | Review Domain History & Reputation | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| TE-181 | Validate HTML (W3C) | 127.0.0.1:8000 is only reachable from here, so no external service can measure it or hold history for it |
| GEO-007 | IndexNow configured | missing input 'indexnow_key' |
| SP-214 | LCP within budget in a local trace (lab) | missing input 'cwv_json' |
| SP-215 | CLS within budget in a local trace (lab) | missing input 'cwv_json' |
| SP-216 | Main thread not blocked in a local trace (TBT, lab proxy for INP) | missing input 'cwv_json' |

