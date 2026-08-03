# Credits and third-party notices

This plugin is self-contained by design: everything an audit needs is bundled, so
it runs the same on any machine without depending on other plugins being
installed. That means some material here came from elsewhere. This file records
what, from where, and under which licence.

## Checklist

The 200-point checklist the registry is built on is
[Plerdy's](https://www.plerdy.com/check/). The 11 additional items (GEO/AI
search, `llms.txt`, AI-crawler policy, IndexNow, schema guards) are new here.

## Evidence scripts

48 of the 58 scripts in `skills/seo-checklist/scripts/` come from
[Agentic-SEO-Skill](https://github.com/Bhanunamikaze/Agentic-SEO-Skill) (MIT),
as do both files in `scripts/lib/`, with three bug fixes applied:

- `article_seo.py` crashed on JSON-LD in array or `@graph` form
- `lib/safe_http.py` exited the process at import when `requests` was absent
- `validate_skill_inventory.py` had a regex that never matched, so the check it
  performed silently validated nothing

New in this plugin: `checklist_runner.py`, `checklist_report.py`,
`detect_profile.py`, `gsc_cannibalization.py`, `gsc_url_inspection.py`,
`gsc_links_csv.py`, `html_validator.py`, `domain_safety_check.py`,
`ga4_tag_checker.py`, `css_minify_check.py`, plus the registry, its generator and
the four judgement agents.

## Bundled playbooks

`skills/seo-checklist/resources/playbooks/local-seo.md` is adapted from the
`rank-local` skill written by this plugin's author.

`skills/seo-checklist/resources/playbooks/competitor-research.md` and
`skills/seo-checklist/resources/references/client-report-structure.md` are
adapted from the `deep-research` and `competitive-report-structure` skills in
[Everything Claude Code](https://github.com/affaan-m/ECC).

Both were rewritten to address this plugin's checklist items and status
vocabulary rather than copied verbatim, but the structure and much of the
substance are theirs.

---

## MIT License — Everything Claude Code

Copyright (c) 2026 Affaan Mustafa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## MIT License — Agentic-SEO-Skill

The evidence scripts are distributed under the MIT licence of their upstream
project, [Agentic-SEO-Skill](https://github.com/Bhanunamikaze/Agentic-SEO-Skill).
This plugin adds no further restrictions. Its licence, reproduced in full as the
licence requires:

Copyright (c) 2026 Bhanu Namikaze
Copyright (c) 2026 agricidaniel

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
