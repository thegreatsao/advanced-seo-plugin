#!/usr/bin/env python3
"""Run the checklist registry against a URL and produce per-item statuses.

Coverage is a contract, not a side effect: every item in
resources/config/checklist.json gets a status, and items nobody could answer
are reported as NO_DATA rather than silently dropped.

Each unique (script, args) pair executes exactly once no matter how many
checklist items depend on it — 211 items collapse to ~45 process launches.

Usage:
    python3 checklist_runner.py https://example.com
    python3 checklist_runner.py https://example.com --json results.json
    python3 checklist_runner.py https://example.com --diff
    python3 checklist_runner.py https://example.com --only crawling_indexing,speed
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
REGISTRY = os.path.join(SKILL_DIR, "resources", "config", "checklist.json")

sys.path.insert(0, SCRIPT_DIR)


def run_script(script_name: str, args: list, timeout: int = 120) -> dict:
    """Run an evidence script and capture its JSON output.

    A script that fails is reported, never silently dropped: the caller turns an
    `error` key into NO_DATA with the reason attached, so a broken check is
    visibly undecided rather than quietly absent.
    """
    script_path = os.path.join(SCRIPT_DIR, script_name)
    if not os.path.exists(script_path):
        return {"error": f"Script {script_name} not found"}

    cmd = [sys.executable, script_path] + args + ["--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        err_msg = result.stderr.strip() or f"Exit code {result.returncode}"
        return {"error": f"[{script_name}] {err_msg}"}
    except subprocess.TimeoutExpired:
        return {"error": f"Script timed out after {timeout}s"}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON output from script"}
    except Exception as e:  # noqa: BLE001 - surfaced to the caller as NO_DATA
        return {"error": str(e)}


def fetch_page(url: str) -> tuple[str, str]:
    """Fetch page HTML to a temp file. Returns (path, error) — exactly one is set.

    The reason a fetch failed is returned rather than swallowed, because the
    caller has to distinguish "this page could not be read" from "this page is
    fine": the first must make every check that reads the site undecided, and it
    can only say so if it knows.

    `safe_get` does not raise on 4xx/5xx, so the status is checked here. A 403
    challenge page and a 404 both return perfectly valid HTML that describes
    something other than the site being audited.
    """
    try:
        from lib.safe_http import safe_get
    except ImportError:
        from scripts.lib.safe_http import safe_get
    try:
        resp = safe_get(url, timeout=15)
    except Exception as e:  # noqa: BLE001 — the reason travels to the caller
        # The exception type carries the diagnosis (ConnectionError, SSLError,
        # Timeout); requests' message carries a nested urllib3 trace that is
        # mostly noise. Keep the type, trim the rest at a word boundary so the
        # report does not print half an identifier.
        detail = " ".join(str(e).split())
        if len(detail) > 120:
            detail = detail[:120].rsplit(" ", 1)[0] + "…"
        return "", f"{type(e).__name__}: {detail}" if detail else type(e).__name__

    code = getattr(resp, "status_code", 200)
    if code >= 400:
        return "", f"HTTP {code}"
    ctype = (getattr(resp, "headers", {}) or {}).get("Content-Type", "")
    if ctype and not any(t in ctype.lower() for t in ("html", "xml", "text/plain")):
        return "", f"not a page: Content-Type {ctype.split(';')[0]}"
    html = resp.text
    # An empty or non-markup body is not a page either. This catches a server
    # answering 200 with nothing; it does not catch a bot-protection challenge,
    # which is real HTML and indistinguishable from the site at this level.
    if "<" not in html:
        return "", f"no HTML in a {len(html)}-byte 200 response"

    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                      mode="w", encoding="utf-8")
    tmp.write(html)
    tmp.close()
    return tmp.name, ""

# Statuses
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
NO_DATA, MANUAL, LLM_PENDING, NA = "NO_DATA", "MANUAL", "LLM_PENDING", "N/A"

SEVERITY_WEIGHT = {"critical": 10, "high": 6, "medium": 3, "low": 1}

# Why a `source: gsc` item stays undecided even with working credentials. None
# of these is missing wiring: the Search Console API has no endpoint for manual
# actions, the Index Coverage report, or mobile-usability signals — the last was
# withdrawn in December 2023. They exist only in the web UI, and calling that
# "not wired yet" would misreport a hard API limit as unfinished work.
GSC_UNAVAILABLE = {
    "GO-141": "Search Console API exposes no manual-actions endpoint — check the UI",
    "GO-142": "Search Console API exposes no Index Coverage endpoint — check the UI",
    "MB-099": "Search Console API exposes no mobile-usability endpoint — check the UI",
}

# Which script capabilities each run mode can satisfy. Anything a mode cannot
# satisfy is reported N/A — excluded from both the score and the coverage
# denominator, because "we did not crawl" is not the same as "the site failed".
MODE_CAPS = {
    "live": {"offline", "fetch", "crawl", "api"},
    "page": {"offline", "fetch", "api"},
    "archive": {"offline"},
}
MODE_HELP = {
    "live": "full audit of a live site (fetch + crawl + external APIs)",
    "page": "single live page, no crawling",
    "archive": "local copy of the site, no network at all",
}

# Scripts that dominate wall-clock; scheduled first so they overlap the rest.
SLOW_FIRST = [
    "duplicate_content.py", "orphan_pages_from_sitemap.py", "pagespeed.py",
    "anchor_text_audit.py", "external_link_quality.py", "sitemap_checker.py",
    "indexability_matrix.py", "broken_links.py",
]


class _Missing:
    def __repr__(self):
        return "<missing>"


_MISSING = _Missing()


# ---------------------------------------------------------------------------
# Assert evaluation
# ---------------------------------------------------------------------------

def resolve(data, path: str):
    """Walk a dotted path. Numeric segments index into lists. Returns _MISSING
    when any segment is absent, so 'key exists but is None' stays distinct
    from 'key not present'."""
    cur = data
    for seg in path.split("."):
        if isinstance(cur, dict):
            if seg not in cur:
                return _MISSING
            cur = cur[seg]
        elif isinstance(cur, list):
            if not seg.isdigit() or int(seg) >= len(cur):
                return _MISSING
            cur = cur[int(seg)]
        else:
            return _MISSING
    return cur


def _texts(value) -> list[str]:
    """Flatten a value into searchable strings — used by none_matching and
    none_severity, which operate over issues[]-style arrays."""
    if value is _MISSING or value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [json.dumps(value, ensure_ascii=False)]
    if isinstance(value, list):
        out = []
        for v in value:
            out.append(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v))
        return out
    return [str(value)]


def _length(value):
    if isinstance(value, (list, dict, str)):
        return len(value)
    return None


def evaluate(rule: dict, data: dict) -> tuple[bool | None, str]:
    """Return (passed, evidence). passed is None when the data needed to
    decide is absent — the caller turns that into NO_DATA, never a false PASS.

    A rule may set "missing_is": "pass" | "fail" when the absence of the field
    is itself the answer. Without it, absence stays undecided: a parser that
    never emits a key must not be read as the site being clean."""
    value = resolve(data, rule["path"])

    if value is _MISSING and "missing_is" in rule:
        verdict = rule["missing_is"] == "pass"
        return verdict, f"{rule['path']} absent (treated as {rule['missing_is']})"

    if "none_severity" in rule:
        levels = {s.lower() for s in rule["none_severity"]}
        if value is _MISSING:
            return None, f"{rule['path']} missing"
        hits = [it for it in (value if isinstance(value, list) else [])
                if isinstance(it, dict) and str(it.get("severity", "")).lower() in levels]
        if hits:
            msg = hits[0].get("message") or hits[0].get("finding") or ""
            return False, f"{len(hits)} issue(s) at {'/'.join(sorted(levels))}: {msg[:120]}"
        return True, f"no {'/'.join(sorted(levels))} issues"

    if "none_matching" in rule:
        if value is _MISSING:
            return None, f"{rule['path']} missing"
        rx = re.compile(rule["none_matching"])
        hits = [t for t in _texts(value) if rx.search(t)]
        if hits:
            return False, f"matched {rule['none_matching']!r}: {hits[0][:120]}"
        return True, f"no match for {rule['none_matching']!r}"

    if "count_matching_lte" in rule:
        pattern, limit = rule["count_matching_lte"]
        if value is _MISSING:
            return None, f"{rule['path']} missing"
        rx = re.compile(pattern)
        n = sum(1 for t in _texts(value) if rx.search(t))
        return n <= limit, f"{n} match(es) for {pattern!r}, limit {limit}"

    if value is _MISSING:
        return None, f"{rule['path']} missing"

    ev = repr(value)[:120]

    if "truthy" in rule:
        return bool(value), f"{rule['path']} = {ev}"
    if "falsy" in rule:
        return not value, f"{rule['path']} = {ev}"
    if "eq" in rule:
        return value == rule["eq"], f"{rule['path']} = {ev} (want {rule['eq']!r})"
    if "ne" in rule:
        return value != rule["ne"], f"{rule['path']} = {ev}"
    if "contains" in rule:
        texts = _texts(value)
        return (rule["contains"] in texts[0]) if texts else False, f"{rule['path']} = {ev}"
    if "matches" in rule:
        return bool(re.search(rule["matches"], str(value))), f"{rule['path']} = {ev}"

    for op, cmp in (("gte", lambda a, b: a >= b), ("lte", lambda a, b: a <= b),
                    ("gt", lambda a, b: a > b), ("lt", lambda a, b: a < b)):
        if op in rule:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return None, f"{rule['path']} = {ev} (not numeric)"
            return cmp(value, rule[op]), f"{rule['path']} = {value} (want {op} {rule[op]})"

    if "between" in rule:
        lo, hi = rule["between"]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None, f"{rule['path']} = {ev} (not numeric)"
        return lo <= value <= hi, f"{rule['path']} = {value} (want {lo}-{hi})"

    for op, cmp in (("len_eq", lambda a, b: a == b), ("len_gte", lambda a, b: a >= b),
                    ("len_lte", lambda a, b: a <= b)):
        if op in rule:
            n = _length(value)
            if n is None:
                return None, f"{rule['path']} = {ev} (no length)"
            return cmp(n, rule[op]), f"len({rule['path']}) = {n} (want {op.split('_')[1]} {rule[op]})"

    if "len_between" in rule:
        lo, hi = rule["len_between"]
        n = _length(value)
        if n is None:
            return None, f"{rule['path']} = {ev} (no length)"
        return lo <= n <= hi, f"len({rule['path']}) = {n} (want {lo}-{hi})"

    return None, f"unknown assert: {list(rule)}"


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def build_plan(items: list[dict], ctx: dict, caps: set[str], mode: str,
               preskip: dict[str, tuple[str, str]] | None = None,
               has_gsc: bool = False
               ) -> tuple[dict[tuple, list[str]], dict[str, tuple[str, str]]]:
    """Map each unique (script, args) to the item ids that depend on it.

    Returns (plan, skipped) where skipped maps item id -> (status, reason) for
    checks this run cannot perform. Capability gaps become N/A; missing inputs
    become NO_DATA — the difference decides whether an item counts against
    coverage or is simply out of scope for the mode."""
    plan: dict[tuple, list[str]] = {}
    skipped: dict[str, tuple[str, str]] = dict(preskip or {})
    for it in items:
        if it["id"] in skipped:
            continue
        chk = it.get("check")
        if not chk or not chk.get("script"):
            continue
        need = chk.get("requires", "fetch")
        # Search Console is the one capability that can be absent for two
        # different reasons, and they are not interchangeable. A mode that makes
        # no network calls puts the item genuinely out of scope: N/A. A mode that
        # could have asked but has no key did not manage to decide it: NO_DATA.
        # Reporting the second as N/A drops it out of the coverage denominator
        # and quietly raises coverage exactly where the audit is thinnest.
        if need == "gsc":
            if "api" not in caps:
                skipped[it["id"]] = (NA, f"Search Console needs network access; "
                                         f"{mode} mode makes none")
            elif not has_gsc:
                skipped[it["id"]] = (NO_DATA, "no Search Console credentials — "
                                              "set GSC_CREDENTIALS_PATH")
            if it["id"] in skipped:
                continue
        elif need not in caps:
            skipped[it["id"]] = (NA, f"needs '{need}'; not available in {mode} mode")
            continue
        args = []
        missing_key = ""
        for a in (chk.get("args") or []):
            if isinstance(a, str) and a.startswith("{") and a.endswith("}"):
                key = a[1:-1]
                if key not in ctx:
                    missing_key = key
                    break
                args.append(ctx[key])
            else:
                args.append(a)
        if missing_key:
            skipped[it["id"]] = (NO_DATA, f"missing input '{missing_key}'")
            continue
        plan.setdefault((chk["script"], tuple(args)), []).append(it["id"])
    return plan, skipped


def _timed(key: tuple, timeout: int) -> dict:
    script, args = key
    start = time.time()
    out = run_script(script, list(args), timeout=timeout)
    elapsed = round(time.time() - start, 1)
    if isinstance(out, dict) and out.get("error"):
        return {"__error__": str(out["error"])[:300], "__elapsed__": elapsed}
    payload = out if isinstance(out, dict) else {"__value__": out}
    payload["__elapsed__"] = elapsed
    return payload


def execute(plan: dict[tuple, list[str]], workers: int, timeout: int, quiet: bool) -> dict:
    """Run every unique job once. Slow jobs are submitted first so they
    overlap the fast ones instead of trailing the pool."""
    order = sorted(plan, key=lambda k: (k[0] not in SLOW_FIRST,
                                        SLOW_FIRST.index(k[0]) if k[0] in SLOW_FIRST else 0))
    results: dict[tuple, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_timed, key, timeout): key for key in order}
        done = 0
        for fut in as_completed(futures):
            key = futures[fut]
            results[key] = fut.result()
            done += 1
            if not quiet:
                mark = "!" if results[key].get("__error__") else "."
                print(f"  [{done}/{len(order)}] {mark} {key[0]}"
                      f" ({results[key]['__elapsed__']}s)", file=sys.stderr)
    return results


def grade(items: list[dict], plan: dict, results: dict, skipped: dict,
          has_gsc: bool) -> list[dict]:
    key_for = {}
    for key, ids in plan.items():
        for i in ids:
            key_for[i] = key

    graded = []
    for it in items:
        row = {k: it[k] for k in ("id", "plerdy_ref", "category", "category_label",
                                  "title", "severity", "source")}
        row["fix"] = it.get("fix", "")
        src = it["source"]

        if it["id"] in skipped and skipped[it["id"]][0] == NA:
            row.update(status=NA, evidence=skipped[it["id"]][1])
        elif src == "manual":
            row.update(status=MANUAL, evidence="requires a human")
        elif src == "llm":
            row["lens"] = it.get("lens", "")
            row.update(status=LLM_PENDING, evidence="awaiting LLM judgement")
        elif src == "gsc":
            # The reason these are undecided does not depend on credentials, so
            # neither does the message. Telling someone without a key to go set
            # GSC_CREDENTIALS_PATH sends them to configure something that cannot
            # help: the API has no endpoint for any of these three.
            row.update(status=NO_DATA,
                       evidence=GSC_UNAVAILABLE.get(it["id"]) or (
                           "needs Search Console" if has_gsc else
                           "no GSC credentials — set GSC_CREDENTIALS_PATH"))
        elif it["id"] in skipped:
            st, why = skipped[it["id"]]
            row.update(status=st, evidence=why)
            if it.get("check"):
                row["script"] = it["check"]["script"]
        else:
            key = key_for.get(it["id"])
            if key is None:
                row.update(status=NO_DATA, evidence="check not runnable")
            else:
                data = results.get(key, {})
                row["script"] = key[0]
                if "__error__" in data:
                    row.update(status=NO_DATA,
                               evidence=f"script failed: {data['__error__'][:160]}")
                else:
                    ok, ev = evaluate(it["check"]["assert"], data)
                    if ok is None:
                        row.update(status=NO_DATA, evidence=ev)
                    elif ok:
                        row.update(status=PASS, evidence=ev)
                    else:
                        warn_rule = it["check"].get("warn")
                        w_ok = False
                        w_ev = ""
                        if warn_rule:
                            w_ok, w_ev = evaluate(warn_rule, data)
                        if w_ok:
                            row.update(status=WARN,
                                       evidence=f"{ev}; within warn range ({w_ev})")
                        else:
                            row.update(status=FAIL, evidence=ev)
        graded.append(row)
    return graded


def score(graded: list[dict]) -> dict:
    """SEO Score counts only items that were actually decided. Coverage says
    how many of the registry we could decide at all — reporting one without
    the other turns 'we could not check it' into 'it is broken'."""
    scored = [g for g in graded if g["status"] in (PASS, FAIL, WARN)]
    applicable = [g for g in graded if g["status"] != NA]
    earned = sum(SEVERITY_WEIGHT[g["severity"]] * (1.0 if g["status"] == PASS else
                                                   0.5 if g["status"] == WARN else 0.0)
                 for g in scored)
    total = sum(SEVERITY_WEIGHT[g["severity"]] for g in scored)

    by_cat: dict[str, dict] = {}
    for g in graded:
        c = by_cat.setdefault(g["category"], {"label": g["category_label"], "counts": {}})
        c["counts"][g["status"]] = c["counts"].get(g["status"], 0) + 1
    for c in by_cat.values():
        cs = c["counts"]
        dec = cs.get(PASS, 0) + cs.get(FAIL, 0) + cs.get(WARN, 0)
        c["decided"] = dec
        c["score"] = round(100 * (cs.get(PASS, 0) + 0.5 * cs.get(WARN, 0)) / dec) if dec else None

    counts: dict[str, int] = {}
    for g in graded:
        counts[g["status"]] = counts.get(g["status"], 0) + 1

    return {
        "seo_score": round(100 * earned / total) if total else None,
        "coverage_pct": round(100 * len(scored) / len(applicable)) if applicable else 0,
        "coverage_of_registry_pct": round(100 * len(scored) / len(graded)) if graded else 0,
        "decided": len(scored),
        "applicable": len(applicable),
        "total_items": len(graded),
        "status_counts": counts,
        "by_category": by_cat,
    }


# Context values that must never reach a file. checklist-results.json and
# everything under .seo-runs/ is what gets shared — with a client, in a ticket,
# in a repo — and the run log is built from each script's argv, so a key passed
# as an argument lands in it verbatim. Paths are not secrets and stay readable;
# the key material does not.
SECRET_CTX_KEYS = ("indexnow_key", "pagespeed_key")
REDACTED = "<redacted>"


def redact(value, secrets: tuple[str, ...]):
    """Replace every secret value anywhere in a JSON-serialisable structure.

    Applied to the whole payload rather than to the run log alone: a script that
    echoes its arguments into an error message leaks the same key by a different
    route, and there is no way to enumerate those routes in advance."""
    if not secrets:
        return value
    if isinstance(value, str):
        for s in secrets:
            if s:
                value = value.replace(s, REDACTED)
        return value
    if isinstance(value, dict):
        return {redact(k, secrets): redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    return value


# What an unreachable entry page makes undecidable. `gsc` is deliberately absent:
# Search Console serves Google's stored history, which is still answerable when
# the site is down right now. Everything else here reads the live site — directly
# (fetch, crawl) or through an API that fetches it for us (PageSpeed, W3C).
NEEDS_A_LIVE_SITE = {"fetch", "crawl", "api"}


def unreachable_skips(items: list[dict], reason: str) -> dict[str, tuple[str, str]]:
    """Mark every check that reads the live site as undecided.

    Without this the audit grades a site it never saw. Most evidence scripts exit
    0 with a well-formed empty result when they cannot fetch anything, and an
    empty result satisfies exactly the assertions this registry is full of —
    `errors = 0`, `duplicates = 0`, no match for a warning pattern. Against a
    host that does not resolve, 29 of 42 scripts returned success and the run
    scored 61/100 on 40 fabricated passes. `missing_is` cannot catch it: the key
    is present, and its value is zero.
    """
    out = {}
    for it in items:
        need = (it.get("check") or {}).get("requires", "fetch")
        if need in NEEDS_A_LIVE_SITE:
            out[it["id"]] = (NO_DATA, f"entry page unreachable ({reason})")
    return out


def history_path(domain: str, stamp: str) -> str:
    d = os.path.join(os.getcwd(), ".seo-runs", domain)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{stamp}.json")


def previous_run(domain: str, exclude: str) -> dict | None:
    d = os.path.join(os.getcwd(), ".seo-runs", domain)
    if not os.path.isdir(d):
        return None
    skip = os.path.basename(exclude) if exclude else ""
    files = sorted(f for f in os.listdir(d) if f.endswith(".json") and f != skip)
    if not files:
        return None
    with open(os.path.join(d, files[-1]), encoding="utf-8") as f:
        return json.load(f)


def diff_runs(prev: dict, cur: dict) -> tuple[list[dict], str]:
    """Status changes between two runs, plus a warning when the runs are not
    comparable. Only the intersection of the two item sets can be compared, so
    a `--only` run against a full one, or `page` against `live`, would otherwise
    report "no status changes" while saying nothing about everything it dropped
    — silence that reads as reassurance."""
    old = {i["id"]: i["status"] for i in prev.get("items", [])}
    out = []
    for i in cur["items"]:
        was = old.get(i["id"])
        if was and was != i["status"]:
            out.append({"id": i["id"], "title": i["title"], "from": was,
                        "to": i["status"], "evidence": i.get("evidence", "")})

    note = ""
    pv, cv = prev.get("registry_version"), cur.get("registry_version")
    if pv and cv and pv != cv:
        note = (f"previous run used registry {pv}, this one {cv}; the item set "
                f"itself changed, so differences may be edits to the checklist "
                f"rather than to the site. ")
    dropped = len(set(old) - {i["id"] for i in cur["items"]})
    if dropped:
        note += (f"{dropped} item(s) from the previous run are not in this one; "
                 f"the diff covers only the {len(old) - dropped} they share")
    if prev.get("profile") and prev["profile"] != cur.get("profile"):
        note += (f"previous run used --profile {prev['profile']}, this one "
                 f"{cur.get('profile')}; scope differs. ")
    if prev.get("mode") and prev["mode"] != cur.get("mode"):
        note = (note + f"previous run used --mode {prev['mode']}, this one {cur.get('mode')}; "
                f"status changes may reflect the mode, not the site"
                + (f". {note}" if note else ""))
    return out, note


# Portable default first; the second entry is one machine's pre-existing key and
# is kept only so that setup keeps working. Anyone else should use the generic
# path or set GSC_CREDENTIALS_PATH — nothing here is specific to an account.
GSC_FALLBACKS = [
    "~/.config/gcloud/gsc-service-account.json",
    "~/.config/gcloud/gv-sa-key.json",
]


PROFILES = os.path.join(SKILL_DIR, "resources", "config", "profiles.json")


def load_profile(name: str) -> dict:
    """Read one site profile. An unknown name is an error rather than a silent
    fallback to `default`: quietly auditing an online store as a blog would drop
    the storefront checks and raise the score for the wrong reason."""
    with open(PROFILES, encoding="utf-8") as f:
        profiles = json.load(f)["profiles"]
    if name not in profiles:
        raise KeyError(f"unknown profile {name!r}; known: {', '.join(sorted(profiles))}")
    return profiles[name]


def all_profiles() -> dict:
    with open(PROFILES, encoding="utf-8") as f:
        return json.load(f)["profiles"]


def detect_profile(html_path: str, url: str) -> dict:
    """Pre-run guess at the site type, used only to pre-fill the question."""
    empty = {"profile": "default", "confidence": "none", "signals": {}, "scores": {}}
    if not html_path or not os.path.exists(html_path):
        return empty
    try:
        from detect_profile import detect
        with open(html_path, encoding="utf-8", errors="replace") as f:
            return detect(f.read(), url)
    except Exception:  # noqa: BLE001 — a failed guess must never stop the audit
        return empty


def describe_detection(d: dict) -> str:
    why = ", ".join(d.get("signals", {}).get(d["profile"], [])[:3])
    return f"{d['profile']} ({d['confidence']} confidence" + (f": {why})" if why else ")")


def choose_profile(explicit: str, interactive: bool, detected: dict | None = None) -> str:
    """Resolve which profile to run under.

    An explicit --profile always wins; `--profile auto` accepts the detector's
    suggestion without asking, which is the one way detection is allowed to
    narrow scope on its own — because passing it is a decision.

    Otherwise ask, but only when there is a person at the terminal to answer:
    prompting unconditionally would hang CI, cron and every backgrounded run on a
    question nobody can see. Without a terminal the run proceeds under `default`
    — the full registry — and says so. Detection never silently narrows anything:
    a heuristic that drops checks and lifts the score, with nobody deciding to,
    is the exact failure this registry exists to prevent.
    """
    profiles = all_profiles()
    names = list(profiles)
    detected = detected or {"profile": "default", "confidence": "none", "signals": {}}

    if explicit == "auto":
        print(f"  profile: {describe_detection(detected)} — detected, --profile auto",
              file=sys.stderr)
        return detected["profile"]
    if explicit:
        return explicit
    if not interactive or not sys.stdin.isatty():
        note = (f" Detection suggests {describe_detection(detected)}; pass "
                f"--profile auto to accept it."
                if detected["profile"] != "default" else "")
        print("  profile: default (not specified; no terminal to ask)." + note,
              file=sys.stderr)
        return "default"

    print("\nWhich kind of site is this? The profile decides which checks apply;"
          "\nanything out of scope is reported N/A instead of counting against you.\n",
          file=sys.stderr)
    suggested = detected["profile"]
    for n, name in enumerate(names, 1):
        p = profiles[name]
        mark = " <- detected" if name == suggested and suggested != "default" else ""
        print(f"  {n}. {name:<10} {p['label']} — {p['note']}{mark}", file=sys.stderr)
    if suggested != "default":
        why = ", ".join(detected.get("signals", {}).get(suggested, [])[:4])
        print(f"\n  Detected: {suggested} ({detected['confidence']} confidence)"
              + (f" from {why}" if why else ""), file=sys.stderr)
        if detected.get("runner_up"):
            print(f"  Close second: {detected['runner_up']['profile']} — the guess "
                  f"is not clear-cut, check it.", file=sys.stderr)
        default_label = f"Enter for {suggested}"
    else:
        print("\n  Detected: nothing conclusive; the evidence was too thin to "
              "narrow anything.", file=sys.stderr)
        default_label = "Enter for default"
    print(file=sys.stderr)

    for _ in range(3):
        try:
            raw = input(f"Profile [number, name, or {default_label}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n  profile: {suggested}", file=sys.stderr)
            return suggested
        if not raw:
            return suggested
        if raw.isdigit() and 1 <= int(raw) <= len(names):
            return names[int(raw) - 1]
        if raw in profiles:
            return raw
        print(f"  {raw!r} is not one of: {', '.join(names)}", file=sys.stderr)
    print(f"  profile: {suggested}", file=sys.stderr)
    return suggested


def profile_excludes(items: list[dict], profile: dict) -> dict[str, str]:
    """item id -> why the profile puts it out of scope."""
    cats = set(profile.get("exclude_categories", []))
    scripts = set(profile.get("exclude_scripts", []))
    ids = set(profile.get("exclude_items", []))
    out = {}
    for it in items:
        script = (it.get("check") or {}).get("script")
        if it["id"] in ids:
            out[it["id"]] = "excluded by profile"
        elif it["category"] in cats:
            out[it["id"]] = f"category {it['category']} does not apply to this site type"
        elif script and script in scripts:
            out[it["id"]] = f"{script} does not apply to this site type"
    return out


SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml")

# Extensions that are certainly not pages. A stylesheet or a PDF sampled as a
# page fails every page-level check, and because sampling aggregates on the
# worst verdict, one asset in the sample condemns the whole site.
ASSET_EXTENSIONS = {
    ".css", ".js", ".mjs", ".json", ".xml", ".rss", ".atom", ".txt", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico", ".bmp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv",
    ".zip", ".gz", ".tar", ".rar", ".7z", ".dmg", ".exe", ".apk",
    ".mp3", ".mp4", ".webm", ".avi", ".mov", ".wav", ".ogg", ".m4a",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
}

# Anchors only. The old pattern matched every `href=` in the document, which
# includes <link rel="stylesheet">, <link rel="icon"> and every preload hint —
# so the sample filled up with assets before reaching a single real page.
ANCHOR_RE = re.compile(r'<a\b[^>]*?\bhref\s*=\s*["\']([^"\']+)["\']', re.I)
LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")


def looks_like_a_page(url: str) -> bool:
    """Reject by extension only. The authoritative check is the Content-Type on
    fetch; this just avoids spending a request to learn what the path already
    says."""
    path = urlparse(url).path
    dot = path.rfind(".")
    slash = path.rfind("/")
    if dot < 0 or dot < slash:  # no extension at all
        return True
    return path[dot:].lower() not in ASSET_EXTENSIONS


def discover_urls(base_url: str, limit: int) -> list[str]:
    """Pick up to `limit` same-host URLs to sample, sitemap first, on-page links
    second. Returns [] when neither source yields anything — the caller then
    audits the single entry URL and says so, rather than pretending to sample."""
    try:
        from lib.safe_http import safe_get
    except ImportError:
        from scripts.lib.safe_http import safe_get
    host = urlparse(base_url).netloc
    found: list[str] = []

    def same_host(u: str) -> bool:
        return urlparse(u).netloc == host

    for path in SITEMAP_PATHS:
        if len(found) >= limit:
            break
        try:
            xml = safe_get(f"{urlparse(base_url).scheme}://{host}{path}", timeout=15).text
        except Exception:
            continue
        locs = LOC_RE.findall(xml)
        # A sitemap index points at more sitemaps; follow one level.
        nested = [u for u in locs if u.endswith(".xml")]
        pages = [u for u in locs if not u.endswith(".xml")]
        for n in nested[:3]:
            try:
                pages += LOC_RE.findall(safe_get(n, timeout=15).text)
            except Exception:
                pass
        # Sitemaps list PDFs and images too — the same extension filter applies.
        found += [u for u in pages if same_host(u) and looks_like_a_page(u)]

    if not found:
        try:
            html = safe_get(base_url, timeout=15).text
            for h in ANCHOR_RE.findall(html):
                # Drop the fragment, keep the query: `?id=7` is usually what
                # makes the URL a distinct page, and cutting it produced a
                # different address that frequently 404s.
                h = h.split("#", 1)[0].strip()
                if not h or h.startswith(("mailto:", "tel:", "javascript:", "data:")):
                    continue
                u = h if h.startswith("http") else urljoin(base_url, h)
                if same_host(u) and looks_like_a_page(u):
                    found.append(u)
        except Exception:
            pass

    seen, out = set(), []
    for u in [base_url] + found:
        u = u.rstrip("/") or u
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= limit:
            break
    return out


PAGE_LEVEL = {"offline", "fetch"}


def is_page_level(item: dict) -> bool:
    """True when the check judges one page rather than the whole site."""
    return (item.get("check") or {}).get("requires", "fetch") in PAGE_LEVEL


STATUS_RANK = {FAIL: 3, WARN: 2, PASS: 1}


def aggregate_pages(primary: list[dict], per_page: list[list[dict]]) -> list[dict]:
    """Fold per-page verdicts into one row per item.

    The worst verdict wins, because a check that fails on any sampled page fails
    for the site — but the evidence always carries the count, so "3 of 8 pages"
    never reads the same as "every page". Site-level items keep the primary
    run's verdict untouched."""
    by_id: dict[str, list[dict]] = {}
    for page in per_page:
        for row in page:
            by_id.setdefault(row["id"], []).append(row)

    out = []
    for row in primary:
        runs = by_id.get(row["id"], [])
        if not is_page_level(row) or len(runs) < 2:
            out.append(row)
            continue
        decided = [r for r in runs if r["status"] in STATUS_RANK]
        if not decided:
            row = dict(row, pages_checked=len(runs))
            out.append(row)
            continue
        worst = max(decided, key=lambda r: STATUS_RANK[r["status"]])
        bad = [r for r in decided if r["status"] == worst["status"]]
        row = dict(row, status=worst["status"],
                   evidence=(f"{len(bad)}/{len(decided)} pages: {worst['evidence']}"),
                   pages_checked=len(runs),
                   pages_decided=len(decided),
                   pages_matching=len(bad))
        out.append(row)
    return out


def registrable_domain(host: str) -> str:
    """Reduce a hostname to the domain a Search Console property is keyed on:
    `www.example.com` is not a `sc-domain:` property, `example.com` is."""
    labels = host.split(":")[0].strip(".").split(".")
    if len(labels) <= 2:
        return ".".join(labels)
    second_level = {"co", "com", "net", "org", "gov", "edu", "ac"}
    keep = 3 if labels[-2] in second_level else 2
    return ".".join(labels[-keep:])


def find_gsc_credentials(explicit: str) -> str:
    """Locate a Search Console service account key. Checked in order: the flag,
    GSC_CREDENTIALS_PATH, GV_SA_KEY, then known local defaults. Returns "" when
    none exists, which downgrades GSC items to NO_DATA rather than failing."""
    for cand in (explicit, os.environ.get("GSC_CREDENTIALS_PATH", ""),
                 os.environ.get("GV_SA_KEY", ""), *GSC_FALLBACKS):
        if cand and os.path.isfile(os.path.expanduser(cand)):
            return os.path.expanduser(cand)
    return ""


def archive_entry(archive_dir: str, entry: str) -> str:
    """Pick the HTML file to analyse inside a local site copy."""
    root = os.path.expanduser(archive_dir)
    if not os.path.isdir(root):
        return ""
    if entry:
        p = entry if os.path.isabs(entry) else os.path.join(root, entry)
        return p if os.path.isfile(p) else ""
    for name in ("index.html", "index.htm"):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            return p
    for dirpath, _dirs, files in os.walk(root):
        for f in sorted(files):
            if f.lower().endswith((".html", ".htm")):
                return os.path.join(dirpath, f)
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the SEO checklist registry against a URL")
    ap.add_argument("url")
    ap.add_argument("--registry", default=REGISTRY)
    ap.add_argument("--json", dest="json_out", default="checklist-results.json")
    ap.add_argument("--only", default="", help="comma-separated category keys")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--diff", action="store_true", help="compare against the previous run")
    ap.add_argument("--no-history", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--mode", choices=sorted(MODE_CAPS), default="",
                    help="; ".join(f"{k}: {v}" for k, v in MODE_HELP.items())
                         + " (default: archive when --archive is given, else live)")
    ap.add_argument("--archive", default="",
                    help="directory holding a local copy of the site")
    ap.add_argument("--entry", default="",
                    help="entry HTML inside --archive (default: index.html, else first *.html)")
    ap.add_argument("--gsc-credentials", default="",
                    help="service account JSON; falls back to GSC_CREDENTIALS_PATH, "
                         "GV_SA_KEY, then ~/.config/gcloud/gsc-service-account.json")
    ap.add_argument("--links-csv", default="",
                    help="Search Console Links report export (ZIP or CSV). The "
                         "Links report has no API, so incoming-link items stay "
                         "NO_DATA without it.")
    ap.add_argument("--profile", default="",
                    help="site profile: default, local, ecommerce, saas, blog, "
                         "media, or 'auto' to accept the detector's suggestion. "
                         "Asked interactively when omitted and a terminal is "
                         "attached; otherwise default (the full registry).")
    ap.add_argument("--no-prompt", action="store_true",
                    help="never ask for a profile, even on a terminal")
    ap.add_argument("--sample", type=int, default=1, metavar="N",
                    help="audit N pages instead of one; page-level checks are "
                         "aggregated across them, site-level checks run once")
    ap.add_argument("--gsc-property", default="",
                    help="Search Console property (default: sc-domain:<registrable domain>). "
                         "Must be one the service account can read — it is not always the "
                         "same string as the audited URL.")
    a = ap.parse_args()

    mode = a.mode or ("archive" if a.archive else "live")
    if a.archive and mode != "archive":
        print(f"--archive given but --mode {mode}: archive files will be ignored",
              file=sys.stderr)
    caps = set(MODE_CAPS[mode])

    gsc_path = find_gsc_credentials(a.gsc_credentials)
    gsc_property = a.gsc_property or f"sc-domain:{registrable_domain(urlparse(a.url).netloc)}"
    # Search Console is an external API, so it is offered only by modes allowed
    # to reach external services at all. Without this gate a key that merely
    # happens to sit on disk pulls `archive` — documented as making no network
    # calls whatsoever — into querying Google about the audited property.
    if gsc_path and "api" not in caps:
        if not a.quiet:
            print(f"  GSC credentials found, but {mode} mode makes no network "
                  f"calls; Search Console items report N/A", file=sys.stderr)
        gsc_path = ""

    with open(a.registry, encoding="utf-8") as f:
        registry = json.load(f)
    items = registry["items"]
    registry_version = registry.get("registry_version", "unknown")
    if a.only:
        keep = {c.strip() for c in a.only.split(",") if c.strip()}
        items = [i for i in items if i["category"] in keep]
        if not items:
            print(f"No items match --only {a.only}", file=sys.stderr)
            return 2

    domain = urlparse(a.url).netloc or "unknown"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if not a.quiet:
        print(f"Checklist audit: {a.url}", file=sys.stderr)
        print(f"  mode: {mode} — {MODE_HELP[mode]}", file=sys.stderr)
        print(f"  GSC: {gsc_path or 'no credentials found'}"
              f"{f' -> {gsc_property}' if gsc_path else ''}", file=sys.stderr)
        print(f"  registry: {len(items)} items "
              f"(version {registry_version})", file=sys.stderr)

    # The entry page is fetched before the profile is settled so detection can
    # read it — one request, not two, and archive mode gets the same treatment.
    temp_html = ""
    entry_error = ""
    if mode == "archive":
        html_path = archive_entry(a.archive, a.entry)
        if not html_path:
            print(f"No HTML entry point found in {a.archive!r}", file=sys.stderr)
            return 2
        if not a.quiet:
            print(f"  entry: {html_path}", file=sys.stderr)
    else:
        html_path, entry_error = fetch_page(a.url)
        temp_html = html_path
        if entry_error:
            print(f"\n  ENTRY PAGE UNREACHABLE: {entry_error}\n"
                  f"  Every check that reads the live site reports NO_DATA. "
                  f"Nothing about this site was measured.", file=sys.stderr)

    # Only worth parsing while the answer is still open: an explicit --profile
    # other than `auto` has already decided.
    detected = detect_profile(html_path, a.url) if a.profile in ("", "auto") else {}
    try:
        a.profile = choose_profile(a.profile, not (a.no_prompt or a.quiet), detected)
        profile = load_profile(a.profile)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        if temp_html and os.path.exists(temp_html):
            os.unlink(temp_html)
        return 2
    excluded = profile_excludes(items, profile)
    preskip = {i: (NA, f"{why} ({a.profile})") for i, why in excluded.items()}
    # A profile exclusion is a scoping decision and outranks reachability: an
    # item that does not apply to this site type is N/A whether or not the page
    # loaded. Everything else the live site would have answered is undecided.
    if entry_error:
        for item_id, skip in unreachable_skips(items, entry_error).items():
            preskip.setdefault(item_id, skip)
    if not a.quiet and excluded:
        print(f"  profile: {a.profile} — {profile['label']}; "
              f"{len(excluded)} item(s) out of scope", file=sys.stderr)

    ctx = {"url": a.url}
    if html_path:
        ctx["html"] = html_path
    if gsc_path:
        ctx["gsc_credentials"] = gsc_path
        ctx["gsc_property"] = gsc_property
    if a.links_csv:
        ctx["links_csv"] = os.path.expanduser(a.links_csv)
    for k, env in (("indexnow_key", "INDEXNOW_KEY"), ("pagespeed_key", "PAGESPEED_API_KEY")):
        if os.environ.get(env):
            ctx[k] = os.environ[env]

    plan, skipped = build_plan(items, ctx, caps, mode, preskip, bool(gsc_path))
    if not a.quiet:
        script_backed = sum(1 for i in items if i["source"] == "script")
        print(f"  {script_backed} script-backed items -> {len(plan)} unique runs"
              f" ({len(skipped)} skipped in this mode)", file=sys.stderr)

    results = execute(plan, a.workers, a.timeout, a.quiet)

    if temp_html and os.path.exists(temp_html):
        os.unlink(temp_html)

    graded = grade(items, plan, results, skipped, bool(gsc_path))

    sampled_urls: list[str] = []
    if a.sample > 1:
        if mode == "archive":
            print("  --sample ignored: archive mode audits the files you point it at",
                  file=sys.stderr)
        elif entry_error:
            print("  --sample skipped: the entry page could not be read, so there "
                  "is nothing to discover URLs from", file=sys.stderr)
        else:
            sampled_urls = discover_urls(a.url, a.sample)
            if len(sampled_urls) < 2:
                print("  --sample found no other URLs (no sitemap, no internal "
                      "links); auditing the single page", file=sys.stderr)
                sampled_urls = []

    if sampled_urls:
        page_items = [i for i in items if is_page_level(i)]
        per_page = []
        if not a.quiet:
            print(f"  sampling {len(sampled_urls)} pages for "
                  f"{len(page_items)} page-level checks", file=sys.stderr)
        for n, page_url in enumerate(sampled_urls, 1):
            page_html, page_err = fetch_page(page_url)
            if page_err:
                # Dropped rather than graded. A sampled URL that turns out to be
                # an asset or an error page would otherwise fail every
                # page-level check, and the worst verdict wins.
                print(f"  [{n}/{len(sampled_urls)}] skipped {page_url} — {page_err}",
                      file=sys.stderr)
                continue
            pctx = dict(ctx, url=page_url, html=page_html)
            pplan, pskip = build_plan(page_items, pctx, caps, mode, preskip, bool(gsc_path))
            presults = execute(pplan, a.workers, a.timeout, True)
            per_page.append(grade(page_items, pplan, presults, pskip, bool(gsc_path)))
            if os.path.exists(page_html):
                os.unlink(page_html)
            if not a.quiet:
                print(f"  [{n}/{len(sampled_urls)}] {page_url}", file=sys.stderr)
        if per_page:
            graded = aggregate_pages(graded, per_page)

    payload = {
        "url": a.url,
        "domain": domain,
        "mode": mode,
        "archive": os.path.expanduser(a.archive) if mode == "archive" else None,
        "gsc_credentials_found": bool(gsc_path),
        "gsc_property": gsc_property if gsc_path else None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "registry_schema": registry.get("version"),
        "registry_version": registry_version,
        "profile": a.profile,
        # Which slice of the registry this run covered. Without it a `--only`
        # run is indistinguishable in .seo-runs/ from a full one, and its score
        # — computed over a handful of categories — reads as a collapse.
        "only": sorted(keep) if a.only else None,
        "entry_reachable": not entry_error,
        "entry_error": entry_error or None,
        "sample": a.sample,
        "sampled_urls": sampled_urls,
        "scores": score(graded),
        "runs": {f"{k[0]} {' '.join(str(x) for x in k[1][1:])}".strip():
                 {"elapsed": v.get("__elapsed__"), "error": v.get("__error__")}
                 for k, v in results.items()},
        "items": graded,
    }

    payload = redact(payload, tuple(ctx[k] for k in SECRET_CTX_KEYS if ctx.get(k)))

    hist = ""
    if not a.no_history:
        hist = history_path(domain, stamp)
        with open(hist, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    diff_note = ""
    if a.diff:
        prev = previous_run(domain, hist)
        if prev:
            payload["diff"], diff_note = diff_runs(prev, payload)
            payload["diff_note"] = diff_note
        else:
            payload["diff"] = None

    with open(a.json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    s = payload["scores"]
    print(f"\nMode: {mode}   GSC: {'yes' if gsc_path else 'no'}")
    if entry_error:
        print(f"UNREACHABLE: {a.url} could not be read — {entry_error}.")
        print(f"No score: nothing about this site was measured. "
              f"{s['decided']}/{s['applicable']} items decided.")
    else:
        print(f"SEO Score: {s['seo_score']}/100   Coverage: {s['coverage_pct']}% "
              f"({s['decided']}/{s['applicable']} applicable items decided; "
              f"{s['coverage_of_registry_pct']}% of the full {s['total_items']}-item registry)")
    for st in (PASS, WARN, FAIL, NO_DATA, LLM_PENDING, MANUAL, NA):
        if s["status_counts"].get(st):
            print(f"  {st:<12} {s['status_counts'][st]}")
    print(f"\nResults: {os.path.abspath(a.json_out)}")
    if hist:
        print(f"History: {hist}")
    if a.diff:
        d = payload.get("diff")
        if d is None:
            print("Diff: no previous run for this domain")
        elif not d:
            print("Diff: no status changes since the previous run")
        else:
            print(f"\nChanged since previous run ({len(d)}):")
            for c in d:
                print(f"  {c['from']} -> {c['to']}  {c['id']} {c['title']}")
        if diff_note:
            print(f"Diff scope: {diff_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
