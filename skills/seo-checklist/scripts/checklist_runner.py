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
from typing import NamedTuple
from urllib.parse import urljoin, urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
REGISTRY = os.path.join(SKILL_DIR, "resources", "config", "checklist.json")

sys.path.insert(0, SCRIPT_DIR)


# How an evidence script failed. All four end as NO_DATA — the item is undecided
# either way — but they are not the same problem and the report must not pretend
# they are: a timeout is a run that needed more time, a crash is a defect in the
# script or its arguments. Only one of the two is worth retrying, and a reader
# who cannot tell which one happened cannot know whether to raise --timeout or
# open the script.
FAILURE_LABEL = {
    "timeout": "script timed out",
    "crash": "script failed",
    "missing": "script not found",
    "bad_output": "script returned unusable output",
}


def run_script(script_name: str, args: list, timeout: int = 120) -> dict:
    """Run an evidence script and capture its JSON output.

    A script that fails is reported, never silently dropped: the caller turns an
    `error` key into NO_DATA with the reason attached, so a broken check is
    visibly undecided rather than quietly absent. `error_kind` travels with it so
    the reason survives into the report — see FAILURE_LABEL.
    """
    script_path = os.path.join(SCRIPT_DIR, script_name)
    if not os.path.exists(script_path):
        return {"error": f"{script_name} is not in {SCRIPT_DIR}",
                "error_kind": "missing"}

    cmd = [sys.executable, script_path] + args + ["--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        err_msg = result.stderr.strip() or f"exit code {result.returncode}"
        return {"error": f"[{script_name}] {err_msg}", "error_kind": "crash"}
    except subprocess.TimeoutExpired:
        # Retryable, and worth saying so: the default is a compromise between a
        # slow site and a run that never ends, not a verdict about the site.
        return {"error": f"no result after {timeout}s; retryable with a longer "
                         f"--timeout or fewer --workers",
                "error_kind": "timeout"}
    except json.JSONDecodeError:
        return {"error": f"[{script_name}] stdout is not JSON",
                "error_kind": "bad_output"}
    except Exception as e:  # noqa: BLE001 - surfaced to the caller as NO_DATA
        return {"error": f"[{script_name}] {type(e).__name__}: {e}",
                "error_kind": "crash"}


# ---------------------------------------------------------------------------
# Is a 200 response actually the page that was asked for?
# ---------------------------------------------------------------------------

# Fingerprints of an interstitial: a bot-protection challenge, a CAPTCHA wall or
# a WAF block page. Each string belongs to the product that serves the challenge,
# not to the site being audited.
#
# Split by *where* the string legitimately appears, which is what separates a
# challenge from an article about challenges. On a challenge page the vendor
# string is machinery — a script src, a form action, an element id — so it lives
# inside a tag. In an article it is prose, inside the text. Searching the whole
# document for `cdn-cgi/challenge-platform` flags every page that explains how
# Cloudflare works, and refusing to audit those is the mirror image of the bug
# this guards against.
CHALLENGE_MARKUP_MARKERS = (
    ("cdn-cgi/challenge-platform", "Cloudflare"),
    ("cf_chl_opt", "Cloudflare"),
    ("cf-browser-verification", "Cloudflare"),
    ("_incapsula_resource", "Imperva Incapsula"),
    ("px-captcha", "PerimeterX"),
    ("captcha.px-cdn.net", "PerimeterX"),
    ("ct.datado.me", "DataDome"),
    ("token.awswaf.com", "AWS WAF"),
    ("sucuri_cloudproxy_js", "Sucuri"),
    ("errors.edgesuite.net", "Akamai"),
    ("distil_r_captcha", "Distil Networks"),
)

# The vendors that name themselves in the visible text of a block page.
CHALLENGE_TEXT_MARKERS = (
    ("incapsula incident id", "Imperva Incapsula"),
    ("sucuri website firewall", "Sucuri"),
    ("generated by cloudfront", "CloudFront"),
)

# Titles an interstitial announces itself with when no vendor string is present.
# Same word-count condition applies.
CHALLENGE_TITLES = (
    "just a moment", "attention required", "checking your browser",
    "access denied", "security check", "are you a robot", "one more step",
    "verify you are human", "please verify you are a human",
    "human verification", "bot verification", "client challenge",
    "ddos protection",
)

# Above this many words of visible prose, a page has content and is not an
# interstitial no matter what strings it contains.
CHALLENGE_MAX_WORDS = 120

# A soft 404 is a 200 response whose own title says it is an error page. Matched
# by equality against a normalized title segment, never by substring: "404"
# appears in the title of every article ever written about broken links, and an
# audit that refuses to run on those is its own kind of wrong.
NOT_FOUND_PHRASES = frozenset({
    "404 error", "error 404", "404 not found", "not found", "page not found",
    "404 page not found", "page not found 404", "this page could not be found",
    "this page does not exist", "page does not exist", "page doesnt exist",
    "nothing found", "no page found", "page unavailable", "file not found",
    "oops that page cant be found", "oops that page can not be found",
    "seite nicht gefunden", "page introuvable", "pagina niet gevonden",
    "pagina no encontrada", "pagina non trovata",
    "страница не найдена", "ошибка 404",
})
# Accepted only as the entire title, because a lone number is also a room, a
# model, a year and a chapter.
NOT_FOUND_EXACT = frozenset({"404", "410", "error", "oops"})

_TAG_RE = re.compile(r"<[^>]+>")
_DROP_BLOCK_RE = re.compile(
    r"<(script|style|noscript|template)\b[^>]*>.*?</\1>", re.S | re.I)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_TITLE_SPLIT_RE = re.compile(r"\s+[|·•—–]\s+|\s+-\s+")
_KEEP_RE = re.compile(r"[^\w\s]", re.U)


def visible_text(html: str) -> str:
    """What a reader would see. Script and style bodies are dropped first,
    because a challenge page is mostly JavaScript and counting it as text would
    make every interstitial look content-rich."""
    return _TAG_RE.sub(" ", _DROP_BLOCK_RE.sub(" ", html))


def visible_words(html: str) -> int:
    return len(visible_text(html).split())


def markup_only(html: str) -> str:
    """Everything inside tags, with the prose removed: attributes, script srcs,
    element ids. Where a challenge page carries its vendor's name."""
    return " ".join(_TAG_RE.findall(html)).lower()


def _normalize_title(raw: str) -> str:
    return " ".join(_KEEP_RE.sub(" ", raw).lower().split())


def page_guard(html: str) -> tuple[str, str]:
    """Decide whether a 200 response is something other than the page asked for.

    Returns `(kind, detail)` — kind is `bot_challenge`, `soft_404` or `""`.

    This is the hole left open when the reachability gate was added: a challenge
    or a soft 404 answers 200 with well-formed HTML, so every evidence script
    runs happily against a page that is not the site, and the registry grades
    whatever the interstitial happens to contain. Both are common — the audit
    User-Agent is exactly what bot protection is built to stop.
    """
    text = visible_text(html)
    words = len(text.split())
    raw_title = (_TITLE_RE.search(html) or [None, ""])[1]
    title = _normalize_title(raw_title)

    # The word count is the second condition on every branch below, and it is
    # what keeps a real page safe. Cloudflare's JS detections inject
    # `cdn-cgi/challenge-platform` into ordinary content pages, so the marker on
    # its own would condemn a working site the moment it turned that feature on.
    if words <= CHALLENGE_MAX_WORDS:
        markup = markup_only(html)
        for marker, vendor in CHALLENGE_MARKUP_MARKERS:
            if marker in markup:
                return "bot_challenge", (f"bot protection ({vendor}): a 200 "
                                         f"response with {words} words of text "
                                         f"and a {vendor} challenge in its markup")
        lowered_text = text.lower()
        for marker, vendor in CHALLENGE_TEXT_MARKERS:
            if marker in lowered_text:
                return "bot_challenge", (f"bot protection ({vendor}): a 200 "
                                         f"response with {words} words of text, "
                                         f"and {vendor} named in them")
        for phrase in CHALLENGE_TITLES:
            if phrase in title:
                return "bot_challenge", (f"bot protection: a 200 response "
                                         f"titled {raw_title.strip()[:60]!r} "
                                         f"with {words} words of text")

    segments = [_normalize_title(s) for s in _TITLE_SPLIT_RE.split(raw_title)]
    if title in NOT_FOUND_EXACT or any(s in NOT_FOUND_PHRASES for s in segments):
        return "soft_404", (f"soft 404: a 200 response titled "
                            f"{raw_title.strip()[:60]!r}")
    return "", ""


def audit_target(requested: str, final_url: str) -> str:
    """Which URL the rest of the run has to agree on.

    A redirect to another host leaves the requested URL describing nothing that
    was measured: `discover_urls` filters candidates on the old netloc so the
    sample collapses to the single entry page, and `sc-domain:` is derived from a
    domain the service account has no property for. Both fail quietly — a
    one-page sample looks like a small site, and an empty Search Console answer
    looks like a site with no traffic.

    A same-host redirect keeps the requested URL: nothing downstream is confused
    by it, and `redirect_checker.py` is then still handed the address that
    actually redirects, which is the hop it exists to report.
    """
    if final_url and urlparse(final_url).netloc != urlparse(requested).netloc:
        return final_url
    return requested


# Below this many words the entry page carries no content worth auditing. It is
# deliberately *not* treated as unreadable: an interstitial from a vendor the
# guard does not know and a client-rendered shell look identical from here, and
# the second is a real page with a real finding — javascript_render_audit.py and
# the JS-rendering items exist to report it. Refusing to score would hide that
# finding behind a guess. So this warns, names the number, and lets the registry
# do its job.
THIN_ENTRY_WORDS = 40


class Fetch(NamedTuple):
    """What one page request produced.

    `error` and `path` are mutually exclusive. `guard` is set whenever the
    response looked like an interstitial or an error page **even when it was not
    enforced**, so `--no-page-guard` records the suspicion instead of erasing it.
    """
    path: str        # temp file holding the HTML, "" when the fetch failed
    error: str       # why it failed, "" on success
    final_url: str   # the URL the request actually ended on, after redirects
    guard: str       # "bot_challenge" | "soft_404" | ""


def fetch_page(url: str, enforce_guard: bool = True) -> Fetch:
    """Fetch page HTML to a temp file.

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
        return Fetch("", f"{type(e).__name__}: {detail}" if detail
                         else type(e).__name__, "", "")

    # Where the request actually landed. safe_request follows redirects itself and
    # returns the last response, so this is the resolved URL — the one the rest of
    # the run has to agree on.
    final_url = getattr(resp, "url", "") or url
    code = getattr(resp, "status_code", 200)
    if code >= 400:
        return Fetch("", f"HTTP {code}", final_url, "")
    ctype = (getattr(resp, "headers", {}) or {}).get("Content-Type", "")
    if ctype and not any(t in ctype.lower() for t in ("html", "xml", "text/plain")):
        return Fetch("", f"not a page: Content-Type {ctype.split(';')[0]}",
                     final_url, "")
    html = resp.text
    # An empty or non-markup body is not a page either. This catches a server
    # answering 200 with nothing.
    if "<" not in html:
        return Fetch("", f"no HTML in a {len(html)}-byte 200 response",
                     final_url, "")

    kind, detail = page_guard(html)
    if kind and enforce_guard:
        return Fetch("", detail, final_url, kind)

    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                      mode="w", encoding="utf-8")
    tmp.write(html)
    tmp.close()
    return Fetch(tmp.name, "", final_url, kind)

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
        field = rule.get("field")
        if field:
            # Aimed at one field instead of the whole element. Without this the
            # pattern is matched against every value in the dict — including the
            # `fix` string, which is written in the vocabulary of the thing being
            # asked for. Two keyword items fired on "…containing the primary
            # keyword" inside a remediation message and never looked at a keyword.
            elements = value if isinstance(value, list) else [value]
            missing_field = [e for e in elements
                             if not isinstance(e, dict) or field not in e]
            if missing_field and len(missing_field) == len(elements) and elements:
                return None, f"no {field} in any {rule['path']} element"
            hits = [str(e[field]) for e in elements
                    if isinstance(e, dict) and field in e and rx.search(str(e[field]))]
        else:
            hits = [t for t in _texts(value) if rx.search(t)]
        if hits:
            return False, (f"matched {rule['none_matching']!r}"
                           f"{f' in {field}' if field else ''}: {hits[0][:120]}")
        return True, (f"no match for {rule['none_matching']!r}"
                      f"{f' in {field}' if field else ''}")

    if "value_map" in rule:
        # The structured alternative to matching prose. The registry enumerates
        # the script's own vocabulary for a field and says what each value means;
        # a value nobody mapped is NO_DATA, never a pass.
        #
        # This is what regex-over-messages could not do. `none_matching` returns
        # PASS when nothing matches, so a pattern aimed at wording a script never
        # emits — or emits in a different word order — passed every site in
        # silence. Fifteen of this registry's twenty-one such assertions were in
        # that state. Here the failure mode is inverted: an unlisted value is
        # undecided, and the evidence says which value it was.
        if value is _MISSING:
            return None, f"{rule['path']} missing"
        field = rule.get("field")
        elements = value if isinstance(value, list) else [value]
        mapping = {str(k): str(v) for k, v in rule["value_map"].items()}
        fails, unmapped, checked = [], [], 0
        for el in elements:
            if field:
                if not isinstance(el, dict) or field not in el:
                    unmapped.append(f"no {field} in element")
                    continue
                raw = el[field]
            else:
                raw = el
            checked += 1
            verdict = mapping.get(str(raw))
            if verdict == "fail":
                fails.append(str(raw))
            elif verdict != "pass":
                unmapped.append(str(raw))
        label = field or rule["path"]
        if fails:
            return False, f"{len(fails)} of {checked} {label} = {fails[0]!r}"
        if unmapped:
            return None, f"unmapped {label} = {unmapped[0]!r}"
        if not checked:
            return None, f"{rule['path']} produced nothing to judge"
        return True, f"all {checked} {label} value(s) acceptable"

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


# Which key of a rule holds the threshold, per operator. Used to report *what was
# compared* as data, so a report can put it in a sentence in any language instead
# of printing the assertion's internals.
#
# The evidence string evaluate() produces still lands in the JSON: it is the audit
# trail, and a reader who wants to know exactly which JSON path decided an item
# should be able to find it. It was never meant to be the sentence a client reads.
# Printing "summary.thin_pages = 6 (want 0)" in a report is the same category of
# mistake as showing a stack trace to a user.
THRESHOLD_OPS = ("eq", "ne", "gte", "lte", "gt", "lt", "between", "len_eq",
                 "len_gte", "len_lte", "len_between", "none_matching",
                 "count_matching_lte", "contains", "matches")


def measurement(rule: dict, data: dict) -> dict:
    """What an assertion compared, as structured data.

    Deliberately decides nothing — the verdict comes from evaluate() and only from
    there. This reads the same `rule["path"]` through the same `resolve()` and
    reports the operator, the threshold and the observed value, so there is no
    second implementation that could disagree about whether an item passed.
    """
    if not rule:
        return {}
    value = resolve(data, rule.get("path", ""))
    out = {"path": rule.get("path", "")}

    for op in THRESHOLD_OPS:
        if op in rule:
            out["op"] = op
            out["want"] = rule[op]
            break
    else:
        for op in ("truthy", "falsy", "none_severity", "value_map"):
            if op in rule:
                out["op"] = op
                break
        else:
            return out

    if value is _MISSING:
        out["missing"] = True
        return out

    op = out["op"]
    if op.startswith("len_"):
        out["got"] = _length(value)
        out["kind"] = "count"
        # What was counted, not just how many. "4 URLs are crawlable" is a
        # statistic; "/search, /cart, /checkout, /login are crawlable" is something
        # somebody can act on this afternoon.
        if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
            out["examples"] = value[:4]
    elif op == "none_matching":
        field = rule.get("field")
        if field:
            elements = value if isinstance(value, list) else [value]
            texts = [str(e[field]) for e in elements
                     if isinstance(e, dict) and field in e]
        else:
            texts = _texts(value)
        rx = re.compile(rule["none_matching"])
        hits = [t for t in texts if rx.search(t)]
        out["got"] = len(hits)
        out["want"] = 0
        out["kind"] = "matches"
        if hits:
            out["sample"] = hits[0][:160]
    elif op == "none_severity":
        levels = {str(lvl).lower() for lvl in rule["none_severity"]}
        hits = [it for it in (value if isinstance(value, list) else [])
                if isinstance(it, dict)
                and str(it.get("severity", "")).lower() in levels]
        out["got"] = len(hits)
        out["want"] = 0
        out["kind"] = "issues"
        out["levels"] = sorted(levels)
        if hits:
            out["sample"] = str(hits[0].get("message")
                                or hits[0].get("finding") or "")[:160]
    elif op == "value_map":
        field = rule.get("field")
        elements = value if isinstance(value, list) else [value]
        seen = [str(el.get(field)) if field and isinstance(el, dict) else str(el)
                for el in elements]
        bad = [v for v in seen if rule["value_map"].get(v) != "pass"]
        out["kind"] = "values"
        out["got"] = bad[0] if bad else (seen[0] if seen else None)
        out["want"] = sorted(k for k, v in rule["value_map"].items() if v == "pass")
    elif op in ("truthy", "falsy"):
        out["kind"] = "flag"
        out["got"] = bool(value)
        out["want"] = op == "truthy"
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        out["got"] = value
        out["kind"] = "number"
    else:
        out["got"] = str(value)[:160]
        out["kind"] = "value"
    return out


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
        return {"__error__": str(out["error"])[:300],
                "__error_kind__": out.get("error_kind", "crash"),
                "__elapsed__": elapsed}
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
                # A distinct mark for a timeout: watching a run, "T" tells you the
                # site is slow, "!" tells you a script is broken.
                mark = "." if not results[key].get("__error__") else (
                    "T" if results[key].get("__error_kind__") == "timeout" else "!")
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
        # `effort` has to travel with the row. It did not, so every graded item
        # arrived at the report without it, priority_of fell back to "medium" for
        # all 214, and the fix list ranked by severity alone — the exact thing the
        # effort estimate was added to prevent. The report printed "?" in its
        # effort column for a year of runs and nobody read it as a defect.
        row = {k: it[k] for k in ("id", "plerdy_ref", "category", "category_label",
                                  "title", "severity", "source")}
        # Defaulted rather than required, so a hand-built item cannot raise here;
        # a registry test asserts every real item declares one.
        row["effort"] = it.get("effort", "medium")
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
            #
            # MANUAL, not NO_DATA. NO_DATA says the audit tried and could not
            # decide, which invites somebody to fix the tool; these three are
            # answerable today, by a person opening the Search Console UI. That
            # is what MANUAL means, and it is what the other 31 manual items say.
            # Coverage is unmoved either way — both statuses stay in the
            # denominator and out of the decided count — so this buys honesty
            # about *who* has to act, not a better number.
            if it["id"] in GSC_UNAVAILABLE:
                row.update(status=MANUAL, evidence=GSC_UNAVAILABLE[it["id"]])
            else:
                row.update(status=NO_DATA,
                           evidence="needs Search Console" if has_gsc else
                                    "no GSC credentials — set GSC_CREDENTIALS_PATH")
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
                    kind = data.get("__error_kind__", "crash")
                    row.update(status=NO_DATA, error_kind=kind,
                               evidence=f"{FAILURE_LABEL.get(kind, FAILURE_LABEL['crash'])}: "
                                        f"{data['__error__'][:160]}")
                else:
                    row["measure"] = measurement(it["check"]["assert"], data)
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


# What a *wrong* entry page makes undecidable — everything the reachability gate
# covers, plus the offline checks. When the fetch simply failed there is no HTML
# to hand an offline script and it drops out on its missing input; when the page
# loaded but is an interstitial or an error page, the file exists and reads
# perfectly, so nothing stops those scripts from grading the wrong document. In
# archive mode that is not hypothetical: a saved challenge page scored 6 passes
# and 10 failures on its 12 words of text.
NEEDS_THE_RIGHT_PAGE = NEEDS_A_LIVE_SITE | {"offline"}


def unreachable_skips(items: list[dict], reason: str,
                      wrong_page: bool = False) -> dict[str, tuple[str, str]]:
    """Mark every check that reads the live site as undecided.

    Without this the audit grades a site it never saw. Most evidence scripts exit
    0 with a well-formed empty result when they cannot fetch anything, and an
    empty result satisfies exactly the assertions this registry is full of —
    `errors = 0`, `duplicates = 0`, no match for a warning pattern. Against a
    host that does not resolve, 29 of 42 scripts returned success and the run
    scored 61/100 on 40 fabricated passes. `missing_is` cannot catch it: the key
    is present, and its value is zero.

    `wrong_page` widens the gate to the offline checks, for the case where a page
    was read successfully and is the wrong page — see NEEDS_THE_RIGHT_PAGE.
    """
    gate = NEEDS_THE_RIGHT_PAGE if wrong_page else NEEDS_A_LIVE_SITE
    label = "entry page is not the site" if wrong_page else "entry page unreachable"
    out = {}
    for it in items:
        need = (it.get("check") or {}).get("requires", "fetch")
        if need in gate:
            out[it["id"]] = (NO_DATA, f"{label} ({reason})")
    return out


def run_stamp() -> str:
    """A history filename that two runs cannot share.

    Second precision was not enough: `--only` runs finish in under a second, so
    a run could overwrite the one before it and the history silently lost an
    entry — the file it would have been compared against. Milliseconds, at fixed
    width so the names still sort chronologically among themselves.
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond // 1000:03d}Z"


def history_path(domain: str, stamp: str) -> str:
    """Where this run is filed, without ever landing on an existing file.

    A stamp collision is now vanishingly unlikely, but "unlikely" is how the
    second-precision version was justified too, and the cost of being wrong is
    destroying a previous audit.
    """
    d = os.path.join(os.getcwd(), ".seo-runs", domain)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{stamp}.json")
    n = 2
    while os.path.exists(path):
        path = os.path.join(d, f"{stamp}-{n}.json")
        n += 1
    return path


EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def run_time(payload: dict, name: str) -> datetime:
    """When a stored run happened, as something orderable.

    `started_at` first, the filename stamp second. Both are parsed rather than
    compared as text: an ISO timestamp and a compact stamp sort against each
    other by accident of punctuation — `2026-08-03T…` always precedes
    `20260803T…` because `-` is below `0` — so a mixed directory would rank
    every legacy file above every current one.
    """
    started = str(payload.get("started_at") or "")
    if started:
        try:
            parsed = datetime.fromisoformat(started)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    stamp = name.split(".")[0].split("-")[0]
    for fmt in ("%Y%m%dT%H%M%S%fZ", "%Y%m%dT%H%M%SZ"):
        try:
            return datetime.strptime(stamp, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return EPOCH


def previous_run(domain: str, exclude: str) -> dict | None:
    """The most recent earlier run for this domain.

    Ordered by the timestamp *inside* each file rather than by its name. The name
    format has already changed once (seconds to milliseconds), and a directory
    holding both would sort wrongly by name for any run inside the same second —
    which is exactly the pair a diff is most likely to want.

    A history file that will not parse is skipped, not fatal: a corrupt record of
    an old run is no reason to abandon the current one.
    """
    d = os.path.join(os.getcwd(), ".seo-runs", domain)
    if not os.path.isdir(d):
        return None
    skip = os.path.basename(exclude) if exclude else ""
    best, best_key = None, EPOCH
    for name in sorted(f for f in os.listdir(d) if f.endswith(".json") and f != skip):
        try:
            with open(os.path.join(d, name), encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        key = run_time(payload, name)
        if key >= best_key:
            best, best_key = payload, key
    return best


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
        # The measurement has to come from the same page as the verdict. It did
        # not: the row kept the entry page's numbers while the status came from
        # the worst sampled page, so a report could say "52 characters, 60 is the
        # limit" directly under a FAIL — a passing number beside a failing verdict,
        # which is worse than printing the raw assertion.
        row = dict(row, status=worst["status"],
                   evidence=(f"{len(bad)}/{len(decided)} pages: {worst['evidence']}"),
                   measure=worst.get("measure", row.get("measure")),
                   pages_checked=len(runs),
                   pages_decided=len(decided),
                   pages_matching=len(bad))
        out.append(row)
    return out


PSL_PATH = os.path.join(SKILL_DIR, "resources", "config", "public_suffix_list.dat")
_PSL_CACHE: tuple[frozenset, frozenset, frozenset] | None = None
_PSL_WARNED = False


def load_public_suffixes(path: str = ""):
    """Parse the Public Suffix List into (exact, wildcard, exception) rule sets.

    The path is resolved at call time, not frozen into the default argument: a
    default binds once at import and then cannot be pointed anywhere else, which
    makes the missing-list branch untestable and any override silently ignored.

    Both sections are kept. The private section is the one that matters most
    here: `github.io`, `vercel.app`, `myshopify.com` and their kind are exactly
    the hosts a small site sits on, and only the private section names them.
    """
    exact, wildcard, exception = set(), set(), set()
    with open(path or PSL_PATH, encoding="utf-8") as f:
        for line in f:
            rule = line.strip().lower()
            if not rule or rule.startswith("//"):
                continue
            if rule.startswith("!"):
                exception.add(rule[1:])
            elif rule.startswith("*."):
                wildcard.add(rule)
            else:
                exact.add(rule)
    return frozenset(exact), frozenset(wildcard), frozenset(exception)


PSL_STALE_DAYS = 365


def psl_snapshot_date(path: str = "") -> str:
    """The date recorded in the bundled list's header, "" when there is none."""
    try:
        with open(path or PSL_PATH, encoding="utf-8") as f:
            for line in f:
                if line.startswith("// snapshot taken "):
                    return line.split("taken", 1)[1].strip()
                if not line.startswith("//"):
                    break
    except OSError:
        return ""
    return ""


def psl_staleness(path: str = "") -> tuple[str, int]:
    """(snapshot date, age in days). Age is -1 when the date cannot be read.

    Worth saying during an audit and not only when somebody thinks to run
    --check: a stale list is missing the platform suffixes registered since it was
    taken, and the only symptom is a Search Console property that answers nothing.
    """
    taken = psl_snapshot_date(path)
    if not taken:
        return "", -1
    try:
        when = datetime.fromisoformat(taken).replace(tzinfo=timezone.utc)
    except ValueError:
        return taken, -1
    return taken, (datetime.now(timezone.utc) - when).days


def public_suffixes():
    """The parsed list, or None when it is not on disk. Loaded once per process."""
    global _PSL_CACHE
    if _PSL_CACHE is None:
        try:
            _PSL_CACHE = load_public_suffixes()
        except OSError:
            return None
    return _PSL_CACHE


def suffix_label_count(labels: list[str], rules) -> int:
    """How many trailing labels form the public suffix, per the PSL algorithm."""
    exact, wildcard, exception = rules
    best = 1  # the implicit default rule, `*`
    for i in range(len(labels)):
        candidate = labels[i:]
        joined = ".".join(candidate)
        if joined in exception:
            # An exception rule says this is *not* a public suffix; the prevailing
            # rule is the same one minus its leftmost label.
            best = max(best, len(candidate) - 1)
        elif joined in exact:
            best = max(best, len(candidate))
        elif len(candidate) > 1 and "*." + ".".join(candidate[1:]) in wildcard:
            best = max(best, len(candidate))
    return best


def registrable_domain(host: str) -> str:
    """Reduce a hostname to the domain a Search Console property is keyed on:
    `www.example.com` is not a `sc-domain:` property, `example.com` is.

    Uses the bundled Public Suffix List. The seven hard-coded suffixes this
    replaced got the common ccTLD shapes right (`example.co.uk`, `example.com.br`)
    and every platform domain wrong: `something.github.io` became `github.io`,
    `myapp.vercel.app` became `vercel.app`. The default property was then one
    nobody owns, and every Search Console item came back empty — which reads as a
    site with no search traffic rather than as a property that does not exist.
    """
    labels = [l for l in host.split(":")[0].strip(".").lower().split(".") if l]
    if len(labels) <= 2:
        return ".".join(labels)

    rules = public_suffixes()
    if rules is None:
        # Say so rather than guess quietly: the fallback is the old heuristic, and
        # it is wrong about exactly the hosts people run small sites on.
        global _PSL_WARNED
        if not _PSL_WARNED:
            _PSL_WARNED = True
            print(f"  public suffix list not found at {PSL_PATH}; falling back to "
                  f"a heuristic. Pass --gsc-property if the default looks wrong.",
                  file=sys.stderr)
        second_level = {"co", "com", "net", "org", "gov", "edu", "ac"}
        keep = 3 if labels[-2] in second_level else 2
        return ".".join(labels[-keep:])

    keep = suffix_label_count(labels, rules) + 1
    return ".".join(labels[-keep:]) if keep <= len(labels) else ".".join(labels)


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
    ap.add_argument("--max-rps", type=float, default=None, metavar="N",
                    help="requests per second per host, across all evidence "
                         "scripts (default 4). 0 removes the pacing. An audit is a "
                         "burst by construction — the scripts run concurrently and "
                         "several walk a sitemap inside their own process.")
    ap.add_argument("--cwv-json", default="",
                    help="JSON file of Core Web Vitals from a local browser trace "
                         "(chrome-devtools MCP). Lab data, reported separately from "
                         "the CrUX field data PageSpeed provides. Without it the "
                         "three lab items report NO_DATA.")
    ap.add_argument("--rendered-json", default="",
                    help="JSON of measurements taken from the rendered page "
                         "(chrome-devtools MCP). Answers font size, link "
                         "distinctness, overlays and — from a mobile render — tap "
                         "targets. Without it those items report NO_DATA.")
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
    ap.add_argument("--no-page-guard", action="store_true",
                    help="audit the entry page even when it looks like a bot "
                         "challenge or a soft 404. The suspicion is still "
                         "recorded; use this when auditing an error page on "
                         "purpose, or when the guard is wrong about your page.")
    ap.add_argument("--sample", type=int, default=1, metavar="N",
                    help="audit N pages instead of one; page-level checks are "
                         "aggregated across them, site-level checks run once")
    ap.add_argument("--gsc-property", default="",
                    help="Search Console property (default: sc-domain:<registrable domain>). "
                         "Must be one the service account can read — it is not always the "
                         "same string as the audited URL.")
    a = ap.parse_args()

    # Passed to the evidence scripts through the environment, because they are
    # separate processes and the pacing they share is keyed on it.
    if a.max_rps is not None:
        os.environ["SEO_MAX_RPS"] = str(a.max_rps)

    mode = a.mode or ("archive" if a.archive else "live")
    if a.archive and mode != "archive":
        print(f"--archive given but --mode {mode}: archive files will be ignored",
              file=sys.stderr)
    caps = set(MODE_CAPS[mode])

    gsc_path = find_gsc_credentials(a.gsc_credentials)
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

    stamp = run_stamp()

    if not a.quiet:
        print(f"Checklist audit: {a.url}", file=sys.stderr)
        print(f"  mode: {mode} — {MODE_HELP[mode]}", file=sys.stderr)
        print(f"  GSC: {gsc_path or 'no credentials found'}", file=sys.stderr)
        print(f"  registry: {len(items)} items "
              f"(version {registry_version})", file=sys.stderr)
        if mode != "archive":
            from lib.safe_http import max_rps
            rps = max_rps()
            print(f"  rate limit: {rps} request(s)/second per host"
                  if rps else "  rate limit: OFF — every script goes as fast as it can",
                  file=sys.stderr)

    # The entry page is fetched before the profile is settled so detection can
    # read it — one request, not two, and archive mode gets the same treatment.
    temp_html = ""
    entry_error = ""
    entry_guard = ""
    entry_words = -1
    audit_url = a.url
    if mode == "archive":
        html_path = archive_entry(a.archive, a.entry)
        if not html_path:
            print(f"No HTML entry point found in {a.archive!r}", file=sys.stderr)
            return 2
        if not a.quiet:
            print(f"  entry: {html_path}", file=sys.stderr)
        # A saved copy can be a challenge page too — somebody archives a site
        # they were blocked from and the audit grades the interstitial.
        with open(html_path, encoding="utf-8", errors="replace") as f:
            entry_html = f.read()
        entry_guard, guard_detail = page_guard(entry_html)
        entry_words = visible_words(entry_html)
        if entry_guard and not a.no_page_guard:
            entry_error = guard_detail
    else:
        fetched = fetch_page(a.url, enforce_guard=not a.no_page_guard)
        html_path, entry_error, entry_guard = fetched.path, fetched.error, fetched.guard
        temp_html = html_path
        # Audit the URL the request actually landed on when the host changed.
        # Otherwise every script is handed the address that redirected away:
        # discover_urls filters on the old netloc and the sample collapses to one
        # page, and the Search Console property is derived from a domain the
        # service account cannot read. A same-host redirect keeps the requested
        # URL, so redirect_checker.py can still see the hop it is there to report.
        audit_url = audit_target(a.url, fetched.final_url)
        if audit_url != a.url:
            print(f"  redirected to another host: {a.url} -> {audit_url}\n"
                  f"  auditing the destination; Search Console property and the "
                  f"URL sample follow it", file=sys.stderr)
        if html_path:
            with open(html_path, encoding="utf-8", errors="replace") as f:
                entry_words = visible_words(f.read())
        if entry_error:
            print(f"\n  ENTRY PAGE UNREACHABLE: {entry_error}\n"
                  f"  Every check that reads the live site reports NO_DATA. "
                  f"Nothing about this site was measured.", file=sys.stderr)
        elif entry_guard:
            print(f"\n  WARNING: the entry page looks like "
                  f"{entry_guard.replace('_', ' ')}, audited anyway "
                  f"(--no-page-guard). Every verdict below describes that page.",
                  file=sys.stderr)

    # A page with no prose is audited, not refused — but the reader has to know,
    # because every page-level verdict below then describes an empty shell.
    if not entry_error and 0 <= entry_words < THIN_ENTRY_WORDS:
        print(f"\n  WARNING: the entry page carries {entry_words} visible "
              f"word(s). If the site is client-rendered or behind bot protection this "
              f"guard does not recognise, the page-level verdicts describe the "
              f"shell, not the content. The JS-rendering items report on it.",
              file=sys.stderr)

    domain = urlparse(audit_url).netloc or "unknown"
    gsc_property = a.gsc_property or (
        f"sc-domain:{registrable_domain(urlparse(audit_url).netloc)}")
    if gsc_path and not a.quiet:
        print(f"  GSC property: {gsc_property}", file=sys.stderr)
        # Only when a property was actually derived from the list: a stale snapshot
        # is missing suffixes registered since it was taken, and the only symptom
        # is a property that answers nothing.
        if not a.gsc_property:
            taken, age = psl_staleness()
            if age > PSL_STALE_DAYS:
                print(f"  public suffix list snapshot is {age} days old "
                      f"({taken}); refresh it with "
                      f"tools/refresh_public_suffix_list.py, or pass "
                      f"--gsc-property if that property looks wrong",
                      file=sys.stderr)

    # Only worth parsing while the answer is still open: an explicit --profile
    # other than `auto` has already decided.
    detected = detect_profile(html_path, audit_url) if a.profile in ("", "auto") else {}
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
        # A page that read fine and is the wrong page also takes the offline
        # checks with it: the file is there and parses, so nothing else would
        # stop them from grading an interstitial's 12 words as a site.
        for item_id, skip in unreachable_skips(
                items, entry_error, wrong_page=bool(entry_guard)).items():
            preskip.setdefault(item_id, skip)
    if not a.quiet and excluded:
        print(f"  profile: {a.profile} — {profile['label']}; "
              f"{len(excluded)} item(s) out of scope", file=sys.stderr)

    ctx = {"url": audit_url}
    if html_path:
        ctx["html"] = html_path
    if gsc_path:
        ctx["gsc_credentials"] = gsc_path
        ctx["gsc_property"] = gsc_property
    if a.links_csv:
        ctx["links_csv"] = os.path.expanduser(a.links_csv)
    if a.cwv_json:
        ctx["cwv_json"] = os.path.expanduser(a.cwv_json)
    if a.rendered_json:
        ctx["rendered_json"] = os.path.expanduser(a.rendered_json)
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
            sampled_urls = discover_urls(audit_url, a.sample)
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
            page = fetch_page(page_url)
            page_html = page.path
            if page.error:
                # Dropped rather than graded. A sampled URL that turns out to be
                # an asset, an error page or a challenge would otherwise fail
                # every page-level check, and the worst verdict wins.
                print(f"  [{n}/{len(sampled_urls)}] skipped {page_url} — {page.error}",
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
        "url": audit_url,
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
        # What the entry page looked like, whether or not it stopped the run. A
        # `--no-page-guard` run that scored a challenge page must say so in the
        # artifact, or the file is the same lie the guard exists to prevent.
        "entry_guard": entry_guard or None,
        "entry_guard_enforced": bool(entry_guard) and not a.no_page_guard,
        # The URL as asked for, when it is not the URL that was audited.
        "requested_url": a.url if audit_url != a.url else None,
        # Visible-word count of the entry page, and how old the suffix list that
        # picked the Search Console property is. Both are the kind of thing a
        # reader can only judge if the artifact says it.
        "entry_visible_words": entry_words if entry_words >= 0 else None,
        "entry_thin": 0 <= entry_words < THIN_ENTRY_WORDS,
        "public_suffix_snapshot": psl_snapshot_date() or None,
        "sample": a.sample,
        "sampled_urls": sampled_urls,
        "scores": score(graded),
        "runs": {f"{k[0]} {' '.join(str(x) for x in k[1][1:])}".strip():
                 {"elapsed": v.get("__elapsed__"), "error": v.get("__error__"),
                  "error_kind": v.get("__error_kind__")}
                 for k, v in results.items()},
        # Timeouts and crashes both land in NO_DATA; counted apart so a run that
        # was merely too slow does not read as a plugin full of broken scripts.
        "script_failures": {
            kind: sum(1 for v in results.values()
                      if v.get("__error_kind__") == kind)
            for kind in FAILURE_LABEL
            if any(v.get("__error_kind__") == kind for v in results.values())
        },
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
        print(f"UNREACHABLE: {audit_url} could not be read — {entry_error}.")
        print(f"No score: nothing about this site was measured. "
              f"{s['decided']}/{s['applicable']} items decided.")
    else:
        print(f"SEO Score: {s['seo_score']}/100   Coverage: {s['coverage_pct']}% "
              f"({s['decided']}/{s['applicable']} applicable items decided; "
              f"{s['coverage_of_registry_pct']}% of the full {s['total_items']}-item registry)")
    for st in (PASS, WARN, FAIL, NO_DATA, LLM_PENDING, MANUAL, NA):
        if s["status_counts"].get(st):
            print(f"  {st:<12} {s['status_counts'][st]}")
    if payload["requested_url"]:
        print(f"Redirected: {payload['requested_url']} -> {audit_url} "
              f"(another host; the destination was audited)")
    if entry_guard and not entry_error:
        print(f"WARNING: the entry page looks like {entry_guard.replace('_', ' ')} "
              f"and was audited anyway (--no-page-guard). Every verdict above "
              f"describes that page, not the site.")
    if payload["script_failures"]:
        parts = ", ".join(f"{n} {kind}" for kind, n in payload["script_failures"].items())
        print(f"Script failures: {parts}"
              + ("  — timeouts are retryable: raise --timeout or lower --workers"
                 if "timeout" in payload["script_failures"] else ""))
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
