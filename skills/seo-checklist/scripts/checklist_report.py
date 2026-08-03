#!/usr/bin/env python3
"""Render checklist_runner.py results into readable deliverables.

Produces three artifacts from one results file:
  CHECKLIST-REPORT.md  the audit, grouped by category, dual-metric summary
  CHECKLIST.html       interactive view: filters, and checkboxes for MANUAL items
  LLM-QUEUE.md         the items only a language model can judge

The LLM queue closes the loop: answer it, save the verdicts as JSON, then rerun
with --llm-answers to merge them in and rescore. Without that, LLM_PENDING items
would sit unanswered forever and quietly cap the achievable coverage.

Usage:
    python3 checklist_report.py checklist-results.json
    python3 checklist_report.py checklist-results.json --llm-answers answers.json
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
NO_DATA, MANUAL, LLM_PENDING, NA = "NO_DATA", "MANUAL", "LLM_PENDING", "N/A"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
STATUS_ICON = {PASS: "PASS", FAIL: "FAIL", WARN: "WARN",
               NO_DATA: "NO DATA", MANUAL: "MANUAL", LLM_PENDING: "LLM", NA: "N/A"}

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_scoring():
    from checklist_runner import score  # reuse the single scoring implementation
    return score


from checklist_runner import SEVERITY_WEIGHT  # noqa: E402 — single source of truth

I18N_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "resources", "i18n")


class Lang:
    """Report chrome in the reader's language.

    Only the report's own wording is translated. Item titles, evidence and fixes
    stay as the registry wrote them unless a translation file explicitly
    overrides a title — a second, hand-maintained copy of 211 checklist strings
    would drift away from the registry the moment either side changed."""

    def __init__(self, code: str = "en"):
        self.code = code
        self.data = {}
        if code and code != "en":
            path = os.path.join(I18N_DIR, f"{code}.json")
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"no translation for {code!r}; add {path} or use --lang en")
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)

    def t(self, key: str, default: str) -> str:
        return self.data.get("strings", {}).get(key, default)

    def status(self, code: str, default: str) -> str:
        return self.data.get("statuses", {}).get(code, default)

    def sev(self, code: str) -> str:
        return self.data.get("severities", {}).get(code, code)

    def effort(self, code: str) -> str:
        return self.data.get("efforts", {}).get(code, code)

    def title(self, item: dict) -> str:
        return self.data.get("item_titles", {}).get(item["id"], item["title"])


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

# Ranking a fix list by severity alone puts a week of content rewriting above a
# one-line meta tag. Dividing by effort answers the question people actually ask
# first — what is worth doing this afternoon.
EFFORT_COST = {"low": 1, "medium": 2, "high": 4}


def priority_of(item: dict) -> float:
    """Severity per unit of effort. Higher is more worth doing first."""
    weight = SEVERITY_WEIGHT.get(item.get("severity"), 1)
    return round(weight / EFFORT_COST.get(item.get("effort", "medium"), 2), 2)


def esc_md(text: str) -> str:
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(data: dict, L: Lang | None = None) -> str:
    s = data["scores"]
    mode = data.get("mode", "live")
    L = L or Lang()
    sampled = data.get("sampled_urls") or []
    out = [
        f"# {L.t('report_title', 'SEO Checklist Audit')}",
        "",
        f"- **{L.t('page', 'URL')}:** {data['url']}",
        f"- **{L.t('mode', 'Mode')}:** `{mode}`"
        + (f" (archive: `{data['archive']}`)" if data.get("archive") else ""),
        f"- **{L.t('profile', 'Profile')}:** `{data.get('profile', 'default')}`",
        f"- **{L.t('generated', 'Run at')}:** {data.get('started_at', '')}",
        f"- **{L.t('registry', 'Registry')}:** `{data.get('registry_version', 'unknown')}`",
        f"- **Search Console:** "
        f"{'found' if data.get('gsc_credentials_found') else 'not configured'}",
    ]
    if len(sampled) > 1:
        out.append(f"- **{L.t('sampled_pages', 'Pages sampled')}:** {len(sampled)}")
    if data.get("only"):
        out.append(f"- **{L.t('scope', 'Scope')}:** "
                   f"`--only {','.join(data['only'])}` — "
                   + L.t("only_note", "a slice of the registry, not a full audit"))
    out += ["", f"## {L.t('summary', 'Summary')}", ""]

    # An unreachable entry page means no site was read, so there is no score to
    # print. Showing one anyway — even a low one — would present the absence of
    # evidence as a measurement, which is the failure this whole report exists
    # to avoid.
    if data.get("entry_reachable") is False:
        out += [
            f"> **{L.t('unreachable_title', 'The site could not be read')}** — "
            + L.t("unreachable_body",
                  "the entry page returned no usable page ({err}). Every check "
                  "that reads the live site is NO_DATA. No score is reported, "
                  "because nothing was measured.").format(
                      err=data.get("entry_error") or "unknown error"),
            "",
        ]
    else:
        out += [
            f"**{L.t('seo_score', 'SEO Score')} {s['seo_score']}/100**",
            "",
            f"**{L.t('coverage', 'Coverage')} {s['coverage_pct']}%** — {s['decided']} / "
            f"{s['applicable']} ({s['coverage_of_registry_pct']}% "
            f"{L.t('of_registry', 'of the full registry')}, {s['total_items']}).",
            "",
            L.t("coverage_note",
                "The two numbers are deliberately separate: a high score over thin "
                "coverage means little, and an item nobody could check is not "
                "evidence that the site failed it."),
            "",
        ]
    out += [
        f"| {L.t('status', 'Status')} | {L.t('count', 'Count')} | {L.t('meaning', 'Meaning')} |",
        "|---|---|---|",
    ]
    meaning = {
        PASS: L.status(PASS, "check passed"),
        FAIL: L.status(FAIL, "check failed — actionable"),
        WARN: L.status(WARN, "borderline, counts as half"),
        NO_DATA: L.status(NO_DATA, "could not be determined (script error, "
                                   "missing credentials, missing field)"),
        LLM_PENDING: L.status(LLM_PENDING, "needs a language-model judgement — "
                                           "see LLM-QUEUE.md"),
        MANUAL: L.status(MANUAL, "needs a human — see the Manual section"),
        NA: L.status(NA, f"not applicable in `{mode}` mode; excluded from both metrics"),
    }
    for st in (PASS, WARN, FAIL, NO_DATA, LLM_PENDING, MANUAL, NA):
        n = s["status_counts"].get(st, 0)
        if n:
            out.append(f"| {STATUS_ICON[st]} | {n} | {meaning[st]} |")

    out += ["", f"### {L.t('by_category', 'By category')}", "",
            f"| {L.t('category', 'Category')} | {L.t('score', 'Score')} | "
            f"{L.t('decided', 'Decided')} | {L.t('failed', 'Failed')} |", "|---|---|---|---|"]
    for cat in s["by_category"].values():
        c = cat["counts"]
        sc = f"{cat['score']}/100" if cat["score"] is not None else "—"
        out.append(f"| {cat['label']} | {sc} | {cat['decided']} | {c.get(FAIL, 0)} |")

    fails = sorted((i for i in data["items"] if i["status"] == FAIL),
                   key=lambda i: (-priority_of(i), SEVERITY_ORDER.get(i["severity"], 9)))
    if fails:
        quick = [i for i in fails if i.get("effort") == "low"]
        out += ["", f"## {L.t('priority_actions', 'Priority actions')}", "",
                L.t("priority_note", "Ranked by severity against effort, not "
                                     "severity alone.")
                + f" {len(quick)}/{len(fails)}.", "",
                f"| {L.t('pri', 'Pri')} | {L.t('sev', 'Sev')} | {L.t('effort', 'Effort')} "
                f"| ID | {L.t('issue', 'Issue')} | {L.t('evidence', 'Evidence')} "
                f"| {L.t('fix', 'Fix')} |",
                "|---|---|---|---|---|---|---|"]
        for i in fails:
            out.append(f"| {priority_of(i)} | {L.sev(i['severity'])} | "
                       f"{L.effort(i.get('effort', '?'))} | {i['id']} | "
                       f"{esc_md(L.title(i))} | {esc_md(i['evidence'])} | "
                       f"{esc_md(i['fix'])} |")
        if quick:
            out += ["", f"**{L.t('start_here', 'Start here')}**", ""]
            for i in quick[:8]:
                out.append(f"- **{i['id']}** ({L.sev(i['severity'])}) "
                           f"{esc_md(L.title(i))} — {esc_md(i['fix'])}")

    out += ["", f"## {L.t('full_checklist', 'Full checklist')}", ""]
    by_cat: dict[str, list] = {}
    for i in data["items"]:
        by_cat.setdefault(i["category_label"], []).append(i)
    for label, items in by_cat.items():
        out += [f"### {label}", "",
                f"| {L.t('status', 'Status')} | {L.t('sev', 'Sev')} | ID | "
                f"{L.t('item', 'Item')} | {L.t('evidence', 'Evidence')} |",
                "|---|---|---|---|---|"]
        for i in sorted(items, key=lambda x: (x["status"] != FAIL,
                                              SEVERITY_ORDER.get(x["severity"], 9))):
            out.append(f"| {STATUS_ICON[i['status']]} | {L.sev(i['severity'])} | {i['id']} | "
                       f"{esc_md(L.title(i))} | {esc_md(i['evidence'])} |")
        out.append("")

    manual = [i for i in data["items"] if i["status"] == MANUAL]
    if manual:
        out += [f"## {L.t('requires_human', 'Requires a human')}", "",
                L.t("manual_note", "These cannot be scripted. Nothing here "
                                   "counts against the score."), ""]
        for i in sorted(manual, key=lambda x: SEVERITY_ORDER.get(x["severity"], 9)):
            out.append(f"- [ ] **{i['id']}** ({i['severity']}) {i['title']} — {i['fix']}")
        out.append("")

    blocked = [i for i in data["items"] if i["status"] == NO_DATA]
    if blocked:
        out += [f"## {L.t('undetermined', 'Undetermined')}", "",
                L.t("undetermined_note",
                    "Checks that ran but could not produce a verdict. Each one "
                    "lowers coverage; none of them lowers the score."), "",
                f"| ID | {L.t('item', 'Item')} | {L.t('why', 'Why')} |", "|---|---|---|"]
        for i in blocked:
            out.append(f"| {i['id']} | {esc_md(i['title'])} | {esc_md(i['evidence'])} |")
        out.append("")

    errs = {k: v["error"] for k, v in data.get("runs", {}).items() if v.get("error")}
    if errs:
        out += [f"## {L.t('script_errors', 'Script errors')}", "",
                f"| {L.t('script', 'Script')} | {L.t('error', 'Error')} |", "|---|---|"]
        for k, v in errs.items():
            out.append(f"| `{esc_md(k)}` | {esc_md(v)[:160]} |")
        out.append("")

    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# LLM queue
# ---------------------------------------------------------------------------

# Which agent answers which lens, and what each one has to read. Splitting the
# queue this way means each agent reads its own slice of the page once; splitting
# by checklist category would have four agents re-reading the same body copy.
LENS_AGENTS = {
    "copy": ("seo-llm-copy", "the body text: prose quality, originality, intent match"),
    "layout": ("seo-llm-layout", "the rendered page furniture: ads, pop-ups, navigation, menus"),
    "locale": ("seo-llm-locale", "language and region targeting, translation quality"),
    "market": ("seo-llm-market", "competitive and geographic positioning"),
}


def render_llm_queue(data: dict, lens: str = "") -> str:
    pending = [i for i in data["items"] if i["status"] == LLM_PENDING]
    if lens:
        pending = [i for i in pending if i.get("lens") == lens]
    agent, reads = LENS_AGENTS.get(lens, ("", ""))
    out = [
        f"# LLM judgement queue{f' — {lens}' if lens else ''}",
        "",
        f"Page under audit: {data['url']}",
        "",
    ]
    if lens:
        out += [f"Assigned agent: `{agent}`. Read {reads}.", ""]
    out += [
        f"{len(pending)} checklist items need a judgement no script can make. Read the actual "
        "page content, then rule on each one. Do not guess from the URL or from this file alone — "
        "if the page does not give you enough to decide, answer `N/A` and say why.",
        "",
        "For each item answer with one of:",
        "",
        "- `PASS` — the page clearly satisfies it",
        "- `FAIL` — the page clearly violates it (say exactly where)",
        "- `WARN` — partially satisfied",
        "- `N/A` — not applicable to this page, or undecidable from the content",
        "",
        "Save the verdicts as JSON and merge them back:",
        "",
        "```json",
        '{ "CN-047": { "status": "PASS", "evidence": "no spelling or grammar errors in body copy" },',
        '  "CN-060": { "status": "N/A",  "evidence": "cloaking cannot be judged from a single render" } }',
        "```",
        "",
        "```bash",
        "python3 checklist_report.py checklist-results.json --llm-answers answers.json",
        "```",
        "",
        "---",
        "",
    ]
    by_cat: dict[str, list] = {}
    for i in pending:
        by_cat.setdefault(i["category_label"], []).append(i)
    for label, items in by_cat.items():
        out += [f"## {label}", ""]
        for i in sorted(items, key=lambda x: SEVERITY_ORDER.get(x["severity"], 9)):
            out += [f"### {i['id']} ({i['severity']})", "",
                    f"**{i['title']}**", "",
                    f"What good looks like: {i['fix']}", ""]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#e3e3e3;--card:#fafafa;
--pass:#1a7f37;--fail:#c1121f;--warn:#b06000;--none:#6b6b6b;--na:#9a9a9a}
@media(prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--mut:#9a9a9a;--line:#2c2c2c;
--card:#191919;--pass:#3fb950;--fail:#f85149;--warn:#d29922;--none:#8b949e;--na:#6e6e6e}}
*{box-sizing:border-box}body{margin:0;padding:2rem 1rem;background:var(--bg);color:var(--fg);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto}h1{font-size:1.6rem;margin:0 0 .3rem}
.sub{color:var(--mut);margin-bottom:1.5rem;font-size:.9rem}
.metrics{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:.75rem}
.metric{flex:1 1 220px;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:1rem}.metric b{display:block;font-size:2rem;line-height:1.1}
.metric span{color:var(--mut);font-size:.85rem}
.note{color:var(--mut);font-size:.85rem;margin:0 0 1.5rem;max-width:70ch}
.bar{display:flex;height:9px;border-radius:5px;overflow:hidden;margin:1rem 0 1.5rem}
.bar i{display:block}
.filters{display:flex;gap:.4rem;flex-wrap:wrap;margin-bottom:1.25rem}
.filters button{background:var(--card);color:var(--fg);border:1px solid var(--line);
border-radius:999px;padding:.3rem .8rem;cursor:pointer;font-size:.85rem}
.filters button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
h2{font-size:1.05rem;margin:1.75rem 0 .5rem;padding-bottom:.3rem;border-bottom:1px solid var(--line)}
.row{display:grid;grid-template-columns:80px 62px 1fr;gap:.6rem;padding:.55rem .4rem;
border-bottom:1px solid var(--line);align-items:start}
.row:last-child{border-bottom:0}
.st{font-size:.7rem;font-weight:700;letter-spacing:.03em;padding-top:.15rem}
.PASS{color:var(--pass)}.FAIL{color:var(--fail)}.WARN{color:var(--warn)}
.NO_DATA,.LLM_PENDING{color:var(--none)}.MANUAL{color:var(--fg)}.NA{color:var(--na)}
.sev{font-size:.7rem;color:var(--mut);padding-top:.2rem}
.ttl{font-weight:500}.ev{color:var(--mut);font-size:.83rem;margin-top:.15rem;word-break:break-word}
.fix{font-size:.83rem;margin-top:.2rem}
.row.done .ttl{opacity:.45;text-decoration:line-through}
label.chk{display:inline-flex;gap:.4rem;align-items:center;cursor:pointer}
.hidden{display:none}
"""

JS = """
const key = 'seo-checklist-' + document.body.dataset.domain;
const saved = JSON.parse(localStorage.getItem(key) || '{}');
document.querySelectorAll('input[type=checkbox][data-id]').forEach(cb => {
  if (saved[cb.dataset.id]) { cb.checked = true; cb.closest('.row').classList.add('done'); }
  cb.addEventListener('change', () => {
    saved[cb.dataset.id] = cb.checked;
    localStorage.setItem(key, JSON.stringify(saved));
    cb.closest('.row').classList.toggle('done', cb.checked);
  });
});
document.querySelectorAll('.filters button').forEach(b => {
  b.addEventListener('click', () => {
    const active = b.dataset.f;
    document.querySelectorAll('.filters button').forEach(o =>
      o.setAttribute('aria-pressed', o === b));
    document.querySelectorAll('.row').forEach(r =>
      r.classList.toggle('hidden', active !== 'ALL' && r.dataset.st !== active));
    document.querySelectorAll('section').forEach(s =>
      s.classList.toggle('hidden', !s.querySelector('.row:not(.hidden)')));
  });
});
"""


def render_html(data: dict) -> str:
    s = data["scores"]
    mode = data.get("mode", "live")
    counts = s["status_counts"]
    seg = [(PASS, "var(--pass)"), (WARN, "var(--warn)"), (FAIL, "var(--fail)"),
           (NO_DATA, "var(--none)"), (LLM_PENDING, "var(--none)"),
           (MANUAL, "var(--line)"), (NA, "var(--na)")]
    total = sum(counts.values()) or 1
    bar = "".join(f'<i style="width:{100 * counts.get(k, 0) / total:.2f}%;background:{c}"></i>'
                  for k, c in seg if counts.get(k))

    parts = [
        '<div class="wrap"><h1>SEO Checklist Audit</h1>',
        f'<p class="sub">{html.escape(data["url"])} &middot; mode <code>{mode}</code> '
        f'&middot; {html.escape(str(data.get("started_at", ""))[:19])}</p>',
        '<div class="metrics">',
        f'<div class="metric"><b>{s["seo_score"]}</b><span>SEO Score — passed checks, '
        f'severity-weighted</span></div>',
        f'<div class="metric"><b>{s["coverage_pct"]}%</b><span>Coverage — {s["decided"]} of '
        f'{s["applicable"]} items applicable in {mode} mode</span></div>',
        f'<div class="metric"><b>{counts.get(FAIL, 0)}</b><span>failing checks</span></div>',
        '</div>',
        '<p class="note">The two metrics stay separate on purpose: a high score over thin '
        'coverage means little, and an item nobody could check is not evidence that the site '
        'failed it.</p>',
        f'<div class="bar">{bar}</div>',
        '<div class="filters"><button data-f="ALL" aria-pressed="true">All</button>',
    ]
    for st in (FAIL, WARN, PASS, NO_DATA, LLM_PENDING, MANUAL, NA):
        if counts.get(st):
            parts.append(f'<button data-f="{st}">{STATUS_ICON[st]} ({counts[st]})</button>')
    parts.append("</div>")

    by_cat: dict[str, list] = {}
    for i in data["items"]:
        by_cat.setdefault(i["category_label"], []).append(i)

    for label, items in by_cat.items():
        parts.append(f"<section><h2>{html.escape(label)}</h2>")
        for i in sorted(items, key=lambda x: (x["status"] != FAIL,
                                              SEVERITY_ORDER.get(x["severity"], 9))):
            cls = i["status"].replace("/", "").replace(" ", "_")
            title = html.escape(i["title"])
            if i["status"] == MANUAL:
                title = (f'<label class="chk"><input type="checkbox" data-id="{i["id"]}">'
                         f'<span>{title}</span></label>')
            fix = (f'<div class="fix">{html.escape(i["fix"])}</div>'
                   if i["status"] in (FAIL, MANUAL, WARN) and i["fix"] else "")
            parts.append(
                f'<div class="row" data-st="{i["status"]}">'
                f'<div class="st {cls}">{STATUS_ICON[i["status"]]}</div>'
                f'<div class="sev">{i["severity"]}<br>{i["id"]}</div>'
                f'<div><div class="ttl">{title}</div>'
                f'<div class="ev">{html.escape(i["evidence"])}</div>{fix}</div></div>')
        parts.append("</section>")
    parts.append("</div>")

    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>SEO Checklist — {html.escape(data.get("domain", ""))}</title>'
            f"<style>{CSS}</style></head>"
            f'<body data-domain="{html.escape(data.get("domain", ""))}">'
            + "".join(parts) + f"<script>{JS}</script></body></html>")


# ---------------------------------------------------------------------------

def merge_llm_answers(data: dict, answers: dict) -> int:
    """Fold LLM verdicts into the results and rescore. Only LLM_PENDING items
    may be overwritten — an answer file must not be able to flip a verdict a
    script already established."""
    valid = {PASS, FAIL, WARN, NA}
    applied = 0
    for item in data["items"]:
        a = answers.get(item["id"])
        if not a or item["status"] != LLM_PENDING:
            continue
        st = str(a.get("status", "")).upper()
        if st not in valid:
            print(f"  skipping {item['id']}: invalid status {a.get('status')!r}", file=sys.stderr)
            continue
        item["status"] = st
        item["evidence"] = f"LLM: {a.get('evidence', '').strip() or 'no rationale given'}"
        item["source"] = "llm(answered)"
        applied += 1
    if applied:
        data["scores"] = load_scoring()(data["items"])
    return applied


def write(path: str, text: str) -> str:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return os.path.abspath(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render checklist audit deliverables")
    ap.add_argument("results", help="checklist-results.json from checklist_runner.py")
    ap.add_argument("--markdown", default="CHECKLIST-REPORT.md")
    ap.add_argument("--html", default="CHECKLIST.html")
    ap.add_argument("--llm-queue", default="LLM-QUEUE.md")
    ap.add_argument("--llm-answers", default="", help="JSON of LLM verdicts to merge back")
    ap.add_argument("--no-html", action="store_true")
    ap.add_argument("--lang", default="en",
                    help="language for the report chrome (en, ru); item titles "
                         "stay in the registry's wording unless translated")
    a = ap.parse_args()

    with open(a.results, encoding="utf-8") as f:
        data = json.load(f)

    if a.llm_answers:
        with open(a.llm_answers, encoding="utf-8") as f:
            answers = json.load(f)
        n = merge_llm_answers(data, answers)
        with open(a.results, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Merged {n} LLM verdict(s) into {a.results}")

    try:
        lang = Lang(a.lang)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2
    written = [("Report", write(a.markdown, render_markdown(data, lang)))]
    if not a.no_html:
        written.append(("HTML", write(a.html, render_html(data))))

    pending_items = [i for i in data["items"] if i["status"] == LLM_PENDING]
    pending = len(pending_items)
    if pending:
        written.append(("LLM queue", write(a.llm_queue, render_llm_queue(data))))
        # One file per lens, so each agent gets exactly its own slice. Items with
        # no lens (a registry written before lenses existed) stay in the combined
        # queue rather than being dropped from the split.
        stem = a.llm_queue[:-3] if a.llm_queue.endswith(".md") else a.llm_queue
        for lens in sorted({i.get("lens") for i in pending_items if i.get("lens")}):
            agent = LENS_AGENTS.get(lens, ("?", ""))[0]
            written.append((f"  -> {agent}",
                            write(f"{stem}-{lens}.md", render_llm_queue(data, lens))))
        stray = [i["id"] for i in pending_items if not i.get("lens")]
        if stray:
            print(f"No lens for {', '.join(stray)} — only in the combined queue",
                  file=sys.stderr)

    s = data["scores"]
    print(f"\nSEO Score {s['seo_score']}/100   Coverage {s['coverage_pct']}% "
          f"({s['decided']}/{s['applicable']})")
    for label, path in written:
        print(f"  {label}: {path}")
    if pending:
        print(f"\n{pending} item(s) still need an LLM verdict — answer LLM-QUEUE.md, "
              f"then rerun with --llm-answers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
