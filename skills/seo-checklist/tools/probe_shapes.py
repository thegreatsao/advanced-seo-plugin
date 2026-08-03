#!/usr/bin/env python3
"""Probe the real JSON shape of the checklist evidence scripts.

Runs each script exactly the way checklist_runner.run_script() does
(argv + --json), then emits a compact structural skeleton so the
checklist assert rules can be written against reality, not guesses.
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
PY = os.environ.get("PROBE_PYTHON", sys.executable)

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.plerdy.com/seo-checklist/"
HTML = sys.argv[2] if len(sys.argv) > 2 else ""

# (script, args) — mirrors what the checklist registry will need.
JOBS = [
    ("robots_checker.py", [URL]),
    ("robots_path_tester.py", [URL]),
    ("x_robots_header_checker.py", [URL]),
    ("security_headers.py", [URL]),
    ("social_meta.py", [URL]),
    ("redirect_checker.py", [URL]),
    ("canonical_checker.py", [URL]),
    ("indexability_matrix.py", [URL]),
    ("sitemap_checker.py", [URL]),
    ("url_quality.py", [URL]),
    ("llms_txt_checker.py", [URL]),
    ("indexnow_checker.py", [URL]),
    ("ai_crawler_policy_matrix.py", [URL]),
    ("entity_checker.py", [URL]),
    ("hreflang_checker.py", [URL]),
    ("duplicate_content.py", [URL]),
    ("eeat_signal_checker.py", [URL]),
    ("freshness_checker.py", [URL]),
    ("answer_block_scanner.py", [URL]),
    ("citation_readiness.py", [URL]),
    ("local_seo_checker.py", [URL]),
    ("image_inventory.py", [URL]),
    ("image_weight_audit.py", [URL]),
    ("a11y_seo_checker.py", [URL]),
    ("font_audit.py", [URL]),
    ("third_party_script_audit.py", [URL]),
    ("cache_compression_checker.py", [URL]),
    ("javascript_render_audit.py", [URL]),
    ("mobile_render_checker.py", [URL]),
    ("faceted_nav_audit.py", [URL]),
    ("collection_page_checker.py", [URL]),
    ("external_link_quality.py", [URL]),
    ("anchor_text_audit.py", [URL]),
    ("link_profile.py", [URL, "--max-pages", "5"]),
    ("internal_links.py", [URL, "--depth", "1", "--max-pages", "5"]),
    ("broken_links.py", [URL, "--workers", "5", "--timeout", "8"]),
    ("orphan_pages_from_sitemap.py", [URL]),
    ("article_seo.py", [URL]),
    ("pagespeed.py", [URL, "--strategy", "mobile"]),
    ("lcp_subparts.py", [URL]),
    ("critical_request_chain.py", [URL]),
    ("content_decay_detector.py", [URL]),
    ("topical_cluster_mapper.py", [URL]),
    ("competitor_gap.py", [URL]),
    ("schema_required_props.py", [URL]),
    ("rich_results_guard.py", [URL]),
    ("product_schema_checker.py", [URL]),
    ("review_schema_checker.py", [URL]),
    ("video_schema_checker.py", [URL]),
    ("html_validator.py", [URL]),
    ("ga4_tag_checker.py", [URL]),
    ("css_minify_check.py", [URL]),
    ("domain_safety_check.py", [URL]),
]
if HTML:
    JOBS += [
        ("parse_html.py", [HTML, "--url", URL]),
        ("readability.py", [HTML]),
        ("validate_schema.py", [HTML]),
    ]

# Search Console scripts address a property the caller has access to, which is
# not derivable from the audited URL — probe them only when one is named.
GSC_PROPERTY = os.environ.get("PROBE_GSC_PROPERTY", "")
GSC_CREDENTIALS = (os.environ.get("GSC_CREDENTIALS_PATH")
                   or os.environ.get("GV_SA_KEY")
                   or os.path.expanduser("~/.config/gcloud/gsc-service-account.json"))
if GSC_PROPERTY:
    _creds = ["--credentials", GSC_CREDENTIALS]
    JOBS += [
        ("gsc_checker.py", [GSC_PROPERTY] + _creds),
        ("gsc_cannibalization.py", [GSC_PROPERTY] + _creds),
        ("gsc_url_inspection.py", [URL, "--property", GSC_PROPERTY] + _creds),
    ]

# Probing every script costs a minute of wall clock and a lot of traffic, so
# allow narrowing to the ones whose output contract actually changed.
ONLY = {s.strip() for s in os.environ.get("PROBE_ONLY", "").split(",") if s.strip()}
if ONLY:
    JOBS = [j for j in JOBS if j[0] in ONLY]


def skeleton(obj, depth=0, max_depth=3):
    """Compact structural summary: keys and types, arrays collapsed to first element."""
    pad = "  " * depth
    if depth > max_depth:
        return f"{pad}..."
    if isinstance(obj, dict):
        if not obj:
            return f"{pad}{{}}"
        lines = []
        for k, v in list(obj.items())[:25]:
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}:")
                lines.append(skeleton(v, depth + 1, max_depth))
            else:
                val = repr(v)
                if len(val) > 70:
                    val = val[:70] + "…"
                lines.append(f"{pad}{k} = {val}")
        if len(obj) > 25:
            lines.append(f"{pad}… +{len(obj) - 25} more keys")
        return "\n".join(lines)
    if isinstance(obj, list):
        if not obj:
            return f"{pad}[] (empty)"
        return f"{pad}[{len(obj)} items] first:\n" + skeleton(obj[0], depth + 1, max_depth)
    return f"{pad}{obj!r}"


def run(job):
    script, args = job
    path = os.path.join(SCRIPT_DIR, script)
    if not os.path.exists(path):
        return script, {"__missing__": True}, 0.0
    start = time.time()
    try:
        r = subprocess.run([PY, path] + args + ["--json"],
                           capture_output=True, text=True, timeout=180, cwd=SCRIPT_DIR)
        elapsed = round(time.time() - start, 1)
        if r.returncode == 0 and r.stdout.strip():
            try:
                return script, json.loads(r.stdout), elapsed
            except json.JSONDecodeError:
                return script, {"__badjson__": r.stdout[:300]}, elapsed
        return script, {"__error__": (r.stderr.strip() or f"exit {r.returncode}")[:300]}, elapsed
    except subprocess.TimeoutExpired:
        return script, {"__timeout__": True}, round(time.time() - start, 1)


results = {}
with ThreadPoolExecutor(max_workers=8) as ex:
    for script, payload, elapsed in ex.map(run, JOBS):
        results[script] = payload
        flag = next((k for k in ("__missing__", "__error__", "__timeout__", "__badjson__") if k in payload), None)
        print(f"[{'FAIL' if flag else ' ok '}] {script:<34} {elapsed:>5}s {flag or ''}", file=sys.stderr)

out = []
for script, payload in results.items():
    out.append("=" * 78)
    out.append(script)
    out.append("=" * 78)
    out.append(skeleton(payload))
    out.append("")
print("\n".join(out))

with open("probe-raw.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
