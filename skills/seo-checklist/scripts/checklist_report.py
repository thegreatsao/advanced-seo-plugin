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

    def fix(self, item: dict) -> str:
        """The recommendation, translated when a translation exists.

        Falls back to the registry's own English text rather than leaving a gap: a
        reader who gets the wrong language can still act on it, and a reader who
        gets nothing cannot. `item_fixes` is filled in per language as the need
        arises — 214 pre-written translations would go stale against a generated
        registry, which is the same trap the per-item explanations avoid."""
        return self.data.get("item_fixes", {}).get(item["id"], item.get("fix", ""))

    def category_help(self, key: str) -> str:
        """The plain-language explanation for a category, translated if available.

        Kept in the translation files rather than the code because it is the layer a
        non-specialist actually reads — an English-only explanation of what a
        failure costs is no explanation for the person who has to pay for it."""
        return self.data.get("categories", {}).get(key, CATEGORY_HELP.get(key, ""))

    def untranslated(self) -> list[str]:
        """Which layers of a non-English report will still come out in English.

        A half-translated document is worse than an English one, because the reader
        cannot tell which parts were considered and which were merely left. The
        report chrome and the category explanations are complete for every shipped
        language; the per-item titles and fixes are opt-in and currently empty. Say
        so on stderr rather than letting the reader discover it in the output."""
        if not self.data:
            return []
        return [name for name, key in (("item titles", "item_titles"),
                                       ("recommendations", "item_fixes"))
                if not self.data.get(key)]


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


# ---------------------------------------------------------------------------
# Saying it in words
# ---------------------------------------------------------------------------

# One plain sentence per category: what this group of checks is about, and what it
# costs when it is wrong. Written for somebody who runs the business, not the site.
#
# Per category rather than per item, on purpose. Fifteen texts can be kept true;
# 214 would drift out of step with the registry the first time an item changed, and
# a stale explanation attached to a live verdict is worse than none. The specifics
# come from the measurement and the fix, which are generated, so they cannot drift.
CATEGORY_HELP = {
    "crawling_indexing":
        "Whether Google can find, read and store your pages at all. Nothing else on "
        "this list matters if a page never gets into the index.",
    "meta_structured":
        "The title and description Google shows in its results, plus the machine-"
        "readable markup behind them. This is what a searcher reads before deciding "
        "whether to click.",
    "content":
        "Whether each page says something substantial, once, in a way a reader and a "
        "search engine can both follow. Thin or duplicated pages compete with your "
        "own better ones.",
    "keywords":
        "Whether each page targets a distinct search intent. When several pages chase "
        "the same query they split the signal and none of them ranks well.",
    "backlinks":
        "Who links to you from elsewhere. Links remain one of the strongest ranking "
        "signals, and judging their quality needs a link index this audit does not "
        "have — most of these items are for a human.",
    "mobile":
        "How the site behaves on a phone, which is what Google measures and where "
        "most visitors arrive.",
    "speed":
        "How quickly the page becomes usable. Slow pages lose visitors before they "
        "read anything, and speed is a ranking factor in its own right.",
    "security":
        "HTTPS, headers and the basics that keep a browser from warning your "
        "visitors. A warning screen costs the visit outright.",
    "international":
        "Whether Google can tell which language and country each page is for. Wrong "
        "signals send the wrong version to the wrong visitor.",
    "google":
        "What Google's own tools report about the site: indexing state, manual "
        "actions, the queries you actually rank for.",
    "architecture":
        "How pages link to each other. A page buried five clicks deep, or reachable "
        "by no link at all, is a page nobody finds.",
    "technical":
        "Configuration a visitor never sees but a crawler does: redirects, headers, "
        "sitemaps, structured-data validity.",
    "media":
        "Images and video: their weight, their alt text and their markup. Usually the "
        "heaviest thing on a page and the easiest to fix.",
    "competition":
        "How the site stands against the sites it competes with. Judgement work, not "
        "measurement.",
    "local":
        "Everything that makes a business findable in its own town: address, opening "
        "hours, map, reviews, and the markup that ties them together.",
    "geo_ai":
        "Whether AI assistants and AI search can read, quote and attribute your "
        "content. A newer channel than Google, and it reads pages differently.",
}


def phrase_measure(item: dict, L: "Lang | None" = None) -> str:
    """The measurement as a sentence.

    The evidence string stays in the JSON as the audit trail; this is what a reader
    gets. `summary.thin_pages = 6 (want 0)` becomes "Found 6, expected none" — the
    item title already says what was counted, so no vocabulary of JSON paths is
    needed and nothing has to be invented.
    """
    L = L or Lang()
    m = item.get("measure") or {}
    op, kind = m.get("op"), m.get("kind")
    got, want = m.get("got"), m.get("want")

    if m.get("missing") or (not m and item.get("status") == NO_DATA):
        text = L.t("m_missing", "The check ran but produced no value for this.")
    elif kind in ("count", "number") and op in ("eq", "len_eq") and want == 0:
        text = L.t("m_none_expected", "Found {got}; there should be none.").format(got=got)
    elif kind in ("count", "number") and op in ("lte", "len_lte",
                                                "count_matching_lte") and want == 0:
        # "4, and no more than 0 is acceptable" is technically right and reads like
        # a machine. Zero is a different sentence from every other threshold.
        text = L.t("m_none_expected", "Found {got}; there should be none.").format(got=got)
    elif kind in ("count", "number") and op in ("lte", "len_lte", "count_matching_lte"):
        text = L.t("m_at_most", "{got}, and no more than {want} is acceptable.").format(
            got=got, want=want)
    elif kind in ("count", "number") and op in ("gte", "len_gte"):
        text = (L.t("m_none_found", "None found; at least {want} is expected.").format(want=want)
                if not got else
                L.t("m_at_least", "{got}, where at least {want} is expected.").format(
                    got=got, want=want))
    elif kind in ("count", "number") and op == "eq":
        text = L.t("m_exactly", "{got}, where {want} is expected.").format(got=got, want=want)
    elif kind == "flag":
        text = (L.t("m_present", "Present.") if got else L.t("m_absent", "Not found."))
    elif kind == "matches":
        text = (L.t("m_no_match", "Nothing matching was found.") if not got else
                L.t("m_matched", "{got} match(es) found.").format(got=got))
    elif kind == "issues":
        levels = "/".join(m.get("levels") or [])
        text = (L.t("m_no_issues", "No {levels} issues reported.").format(levels=levels)
                if not got else
                L.t("m_issues", "{got} {levels} issue(s) reported.").format(
                    got=got, levels=levels))
    elif kind == "values":
        allowed = ", ".join(str(w) for w in (want or []))
        text = L.t("m_value", "Reported '{got}'; acceptable: {allowed}.").format(
            got=got, allowed=allowed)
    elif got is not None:
        text = L.t("m_reported", "Reported: {got}.").format(got=got)
    else:
        return item.get("evidence", "")

    examples = m.get("examples")
    if examples:
        text += " " + L.t("m_examples", "Namely: {list}.").format(
            list=", ".join(str(e)[:60] for e in examples))
    sample = m.get("sample")
    if sample:
        text += " " + L.t("m_example", "For example: {sample}").format(
            sample=str(sample)[:120])

    decided = item.get("pages_decided")
    matching = item.get("pages_matching")
    if decided and decided > 1 and item.get("status") in (FAIL, WARN):
        text += " " + L.t("m_pages", "Seen on {matching} of {decided} pages checked.").format(
            matching=matching or decided, decided=decided)
    return text


def plain_summary(data: dict, L: "Lang | None" = None) -> list[str]:
    """The three or four sentences that answer "so what?" before any number does."""
    L = L or Lang()
    s = data["scores"]
    c = s["status_counts"]
    broken = c.get(FAIL, 0) + c.get(WARN, 0)
    out = []
    if data.get("entry_reachable") is False:
        return [L.t("p_unreadable",
                    "The page could not be read, so nothing here was measured. "
                    "There is no score for the same reason.")]
    out.append(L.t("p_checked",
                   "We checked {decided} things on this site and {broken} of them "
                   "need work.").format(decided=s["decided"], broken=broken))
    quick = sum(1 for i in data["items"]
                if i["status"] in (FAIL, WARN) and i.get("effort") == "low")
    if quick:
        out.append(L.t("p_quick",
                       "{quick} of those are quick fixes — a setting or a line of "
                       "text, not a rebuild.").format(quick=quick))
    undecided = c.get(LLM_PENDING, 0) + c.get(MANUAL, 0) + c.get(NO_DATA, 0)
    if undecided:
        out.append(L.t("p_undecided",
                       "{undecided} more could not be settled by measurement: they "
                       "need a person's judgement, an account we do not have, or "
                       "data that does not exist. They are listed, not hidden.")
                   .format(undecided=undecided))
    return out


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
    # The answer to "so what?" goes above the metrics, not below them. A reader who
    # stops after three lines should still leave with the truth.
    out += [line for line in plain_summary(data, L)] + [""]

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

    fails = sorted((i for i in data["items"] if i["status"] in (FAIL, WARN)),
                   key=lambda i: (-priority_of(i), SEVERITY_ORDER.get(i["severity"], 9)))
    if fails:
        quick = [i for i in fails if i.get("effort") == "low"]
        out += ["", f"## {L.t('do_first', 'What to do first')}", "",
                L.t("do_first_note",
                    "Ordered by how much each matters against how much work it is "
                    "— {quick} of the {total} are quick.").format(
                        quick=len(quick), total=len(fails)), ""]
        # One block per item rather than a row in a seven-column table. The table
        # led with a computed priority float and three jargon columns before it
        # reached the problem, and put the raw assertion in the evidence column.
        current = ""
        for i in fails:
            if i["category_label"] != current:
                current = i["category_label"]
                out += [f"### {current}", ""]
                note = L.category_help(i.get("category", ""))
                if note:
                    out += [f"*{note}*", ""]
            badges = f"{L.sev(i['severity'])} · {L.effort(i.get('effort', 'medium'))}"
            out += [f"**{L.title(i)}**  ",
                    f"`{badges}`  ",
                    f"{phrase_measure(i, L)}  ",
                    f"{L.t('what_to_do', 'What to do')}: {L.fix(i)}", ""]

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
            out.append(f"- [ ] **{i['id']}** ({L.sev(i['severity'])}) "
                       f"{L.title(i)} — {L.fix(i)}")
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
        "Then have a second reader go through the same items independently and "
        "merge that with `--llm-review review.json`. Where the two agree the "
        "verdict says so; where they disagree the item returns to `NO_DATA` "
        "carrying both readings, because two careful readings that conflict mean "
        "the page did not settle it. The reviewer cannot overwrite a verdict — "
        "see `resources/agents/seo-llm-adversary.md`.",
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
h3{font-size:.95rem;margin:1.25rem 0 .4rem;color:var(--mut)}
small{font-size:.55em;font-weight:400;color:var(--mut)}

/* Layer 1 — the plain answer, before any number */
.hero{margin-bottom:2rem}
.plain p{font-size:1.15rem;line-height:1.5;margin:.2rem 0 .6rem;max-width:60ch}
.metric.warnbox b{color:var(--fail)}
.legend{display:flex;gap:1rem;flex-wrap:wrap;font-size:.78rem;color:var(--mut);
margin:-1rem 0 0}
.legend span{display:inline-flex;align-items:center;gap:.35rem}
.legend i{width:9px;height:9px;border-radius:2px;display:inline-block}

/* Layer 2 — where the problems are */
.catrow{display:grid;grid-template-columns:minmax(120px,1.4fr) 3fr 68px 1.6fr;
gap:.75rem;align-items:center;padding:.3rem 0;font-size:.9rem}
.catname{font-weight:500}
.cattrack{background:var(--line);border-radius:999px;height:8px;overflow:hidden}
.cattrack i{display:block;height:100%;border-radius:999px}
.cattrack .pass{background:var(--pass)}.cattrack .warn{background:var(--warn)}
.cattrack .fail{background:var(--fail)}
.catnum{text-align:right;font-variant-numeric:tabular-nums}
.catmeta{color:var(--mut);font-size:.8rem}
.cathelp{color:var(--mut);font-size:.83rem;margin:.1rem 0 .9rem;max-width:78ch;
padding-left:.1rem}
@media(max-width:640px){.catrow{grid-template-columns:1fr 60px;grid-auto-rows:auto}
.cattrack{grid-column:1/-1}.catmeta{grid-column:1/-1}}

/* Layer 3 — one card per thing to fix */
.card{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--fail);
border-radius:8px;padding:.85rem 1rem;margin:.6rem 0}
.card.WARN{border-left-color:var(--warn)}
.cardhead{display:flex;gap:.4rem;align-items:center;flex-wrap:wrap;margin-bottom:.35rem}
.card h3{margin:.1rem 0 .35rem;font-size:1rem;color:var(--fg)}
.badge{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;
border-radius:999px;padding:.12rem .5rem;border:1px solid var(--line);color:var(--mut)}
.badge.sev-critical,.badge.sev-high{color:var(--fail);border-color:var(--fail)}
.badge.sev-medium{color:var(--warn);border-color:var(--warn)}
.badge.eff{color:var(--mut)}
.cardhead .cat{font-size:.75rem;color:var(--mut);margin-left:auto}
.found{margin:.1rem 0 .4rem;font-weight:500}
.why{color:var(--mut);font-size:.86rem;margin:.1rem 0 .5rem;max-width:78ch}
.do{margin:.2rem 0 .1rem;font-size:.9rem}
details.tech{margin-top:.5rem}
details.tech summary{cursor:pointer;color:var(--mut);font-size:.78rem}
.techbody{font-size:.78rem;color:var(--mut);padding:.4rem 0 0;word-break:break-word}

/* Layer 4 — folded machine detail */
details.fold{border-top:1px solid var(--line);padding:.6rem 0}
details.fold>summary{cursor:pointer;font-weight:500;font-size:.95rem}
details.fold .count{color:var(--mut);font-weight:400;font-size:.85rem}
details.fold[open]>summary{margin-bottom:.75rem}
.foot{color:var(--mut);font-size:.78rem;margin-top:2rem}
code{font-size:.9em;background:var(--card);padding:.05rem .3rem;border-radius:4px}
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


def _badges(item: dict, L: Lang) -> str:
    sev = html.escape(L.sev(item["severity"]))
    eff = html.escape(L.effort(item.get("effort", "medium")))
    return (f'<span class="badge sev-{item["severity"]}">{sev}</span>'
            f'<span class="badge eff">{eff}</span>')


def _card(item: dict, L: Lang) -> str:
    """One thing to fix, as a reader needs it: what, how bad, what it costs, what to
    do — and the machine detail folded away rather than deleted."""
    why = L.category_help(item.get("category", ""))
    tech = html.escape(item.get("evidence", ""))
    script = html.escape(str(item.get("script", "")))
    detail = (f'<summary>{html.escape(L.t("technical_detail", "Technical detail"))}</summary>'
              f'<div class="techbody"><code>{item["id"]}</code>'
              + (f' &middot; <code>{script}</code>' if script else "")
              + f'<div>{tech}</div></div>')
    return (f'<article class="card {item["status"]}" data-st="{item["status"]}">'
            f'<div class="cardhead">{_badges(item, L)}'
            f'<span class="cat">{html.escape(item["category_label"])}</span></div>'
            f'<h3>{html.escape(L.title(item))}</h3>'
            f'<p class="found">{html.escape(phrase_measure(item, L))}</p>'
            + (f'<p class="why">{html.escape(why)}</p>' if why else "")
            + (f'<p class="do"><b>{html.escape(L.t("what_to_do", "What to do"))}:</b> '
               f'{html.escape(L.fix(item))}</p>' if item.get("fix") else "")
            + f'<details class="tech">{detail}</details></article>')


def render_html(data: dict, L: Lang | None = None) -> str:
    """Four layers, widest audience first.

    The old report was one flat run of 214 equal-weight table rows whose evidence
    column printed the assertion's internals — `summary.thin_pages = 6 (want 0)`.
    Informative to whoever wrote the registry, opaque to whoever owns the site.
    Nothing is removed here: the plain layer comes first, the machine layer is
    folded underneath it, and the full checklist stays as the audit trail.
    """
    L = L or Lang()
    s = data["scores"]
    mode = data.get("mode", "live")
    counts = s["status_counts"]
    unreadable = data.get("entry_reachable") is False

    seg = [(FAIL, "var(--fail)"), (WARN, "var(--warn)"), (PASS, "var(--pass)"),
           (NO_DATA, "var(--none)"), (LLM_PENDING, "var(--none)"),
           (MANUAL, "var(--line)"), (NA, "var(--na)")]
    total = sum(counts.values()) or 1
    bar = "".join(f'<i style="width:{100 * counts.get(k, 0) / total:.2f}%;background:{c}" '
                  f'title="{STATUS_ICON[k]}: {counts.get(k, 0)}"></i>'
                  for k, c in seg if counts.get(k))

    parts = [f'<div class="wrap"><h1>{html.escape(L.t("report_title", "SEO Checklist Audit"))}'
             f' &mdash; {html.escape(data.get("domain", ""))}</h1>',
             f'<p class="sub">{html.escape(data["url"])} &middot; <code>{mode}</code>'
             f' &middot; {html.escape(str(data.get("profile", "default")))}'
             f' &middot; {html.escape(str(data.get("started_at", ""))[:16])}</p>']

    # -- Layer 1: what this means, in sentences, before any number ---------------
    parts.append('<section class="hero"><div class="plain">'
                 + "".join(f"<p>{html.escape(line)}</p>" for line in plain_summary(data, L))
                 + "</div>")
    if unreadable:
        parts.append(f'<div class="metrics"><div class="metric"><b>&mdash;</b><span>'
                     f'{html.escape(L.t("no_score", "No score: the entry page could not be read"))}'
                     f'</span></div></div>')
    else:
        parts += [
            '<div class="metrics">',
            f'<div class="metric"><b>{s["seo_score"]}<small>/100</small></b>'
            f'<span>{html.escape(L.t("m_score_help", "Of the checks that could be decided, how many passed — weighted by how much each matters"))}</span></div>',
            f'<div class="metric"><b>{s["coverage_pct"]}<small>%</small></b>'
            f'<span>{html.escape(L.t("m_cov_help", "How much of the checklist could be decided at all: {decided} of {applicable}").format(decided=s["decided"], applicable=s["applicable"]))}</span></div>',
            f'<div class="metric warnbox"><b>{counts.get(FAIL, 0) + counts.get(WARN, 0)}</b>'
            f'<span>{html.escape(L.t("m_broken_help", "Checks that need work"))}</span></div>',
            "</div>",
            f'<p class="note">{html.escape(L.t("coverage_note", "The two numbers are deliberately separate: a high score over thin coverage means little, and an item nobody could check is not evidence that the site failed it."))}</p>',
        ]
    parts.append(f'<div class="bar">{bar}</div><div class="legend">'
                 + "".join(f'<span><i style="background:{c}"></i>'
                           f'{STATUS_ICON[k]} {counts.get(k, 0)}</span>'
                           for k, c in seg if counts.get(k))
                 + "</div></section>")

    # -- Layer 2: where the problems are, as bars ------------------------------
    cats = [(key, cat) for key, cat in s["by_category"].items() if cat["decided"]]
    cats.sort(key=lambda kv: kv[1]["score"] if kv[1]["score"] is not None else 101)
    if cats:
        parts.append(f'<section><h2>{html.escape(L.t("where", "Where the problems are"))}</h2>')
        for key, cat in cats:
            score = cat["score"]
            tone = "fail" if score < 60 else ("warn" if score < 85 else "pass")
            failed = cat["counts"].get(FAIL, 0) + cat["counts"].get(WARN, 0)
            parts.append(
                f'<div class="catrow"><div class="catname">{html.escape(cat["label"])}</div>'
                f'<div class="cattrack"><i class="{tone}" style="width:{score}%"></i></div>'
                f'<div class="catnum">{score}<small>/100</small></div>'
                f'<div class="catmeta">'
                + html.escape(L.t("cat_meta", "{decided} checked, {failed} need work")
                              .format(decided=cat["decided"], failed=failed))
                + "</div></div>")
            help_text = L.category_help(key)
            if help_text and failed:
                parts.append(f'<p class="cathelp">{html.escape(help_text)}</p>')
        parts.append("</section>")

    # -- Layer 3: what to do, as cards ------------------------------------------
    todo = sorted((i for i in data["items"] if i["status"] in (FAIL, WARN)),
                  key=lambda i: (-priority_of(i), SEVERITY_ORDER.get(i["severity"], 9)))
    if todo:
        quick = [i for i in todo if i.get("effort") == "low"]
        parts.append(f'<section><h2>{html.escape(L.t("do_first", "What to do first"))}</h2>'
                     f'<p class="note">'
                     + html.escape(L.t("do_first_note",
                                       "Ordered by how much each matters against how much "
                                       "work it is — {quick} of the {total} are quick.")
                                   .format(quick=len(quick), total=len(todo)))
                     + "</p>" + "".join(_card(i, L) for i in todo) + "</section>")

    # -- Layer 4: the machine layer, folded --------------------------------------
    def fold(title: str, body: str, count: int) -> str:
        return (f'<details class="fold"><summary>{html.escape(title)} '
                f'<span class="count">{count}</span></summary>{body}</details>')

    manual = [i for i in data["items"] if i["status"] == MANUAL]
    if manual:
        rows = "".join(
            f'<div class="row" data-st="MANUAL"><div class="st MANUAL">{STATUS_ICON[MANUAL]}</div>'
            f'<div class="sev">{html.escape(L.sev(i["severity"]))}<br>{i["id"]}</div>'
            f'<div><div class="ttl"><label class="chk">'
            f'<input type="checkbox" data-id="{i["id"]}">'
            f'<span>{html.escape(L.title(i))}</span></label></div>'
            f'<div class="fix">{html.escape(L.fix(i))}</div></div></div>'
            for i in sorted(manual, key=lambda x: SEVERITY_ORDER.get(x["severity"], 9)))
        parts.append(fold(L.t("requires_human", "Needs a person"),
                          f'<p class="note">'
                          + html.escape(L.t("manual_note",
                                            "These cannot be scripted. Nothing here counts "
                                            "against the score. Tick them off as you go — "
                                            "the ticks are remembered in this browser."))
                          + f"</p>{rows}", len(manual)))

    pending = [i for i in data["items"] if i["status"] == LLM_PENDING]
    if pending:
        rows = "".join(
            f'<div class="row" data-st="LLM_PENDING">'
            f'<div class="st LLM_PENDING">{STATUS_ICON[LLM_PENDING]}</div>'
            f'<div class="sev">{html.escape(L.sev(i["severity"]))}<br>{i["id"]}</div>'
            f'<div class="ttl">{html.escape(L.title(i))}</div></div>' for i in pending)
        parts.append(fold(L.t("awaiting_judgement", "Awaiting a reading of the page"),
                          f'<p class="note">'
                          + html.escape(L.t("pending_note",
                                            "Questions no script can settle — wording, "
                                            "layout, intent. They lower coverage until "
                                            "someone answers them."))
                          + f"</p>{rows}", len(pending)))

    blocked = [i for i in data["items"] if i["status"] == NO_DATA]
    if blocked:
        rows = "".join(
            f'<div class="row" data-st="NO_DATA"><div class="st NO_DATA">{STATUS_ICON[NO_DATA]}</div>'
            f'<div class="sev">{html.escape(L.sev(i["severity"]))}<br>{i["id"]}</div>'
            f'<div><div class="ttl">{html.escape(L.title(i))}</div>'
            f'<div class="ev">{html.escape(i.get("evidence", ""))}</div></div></div>'
            for i in blocked)
        parts.append(fold(L.t("undetermined", "Could not be determined"),
                          f'<p class="note">'
                          + html.escape(L.t("undetermined_note",
                                            "Checks that ran and could not reach a verdict. "
                                            "Each lowers coverage; none lowers the score. "
                                            "This list is the honest part of the audit."))
                          + f"</p>{rows}", len(blocked)))

    by_cat: dict[str, list] = {}
    for i in data["items"]:
        by_cat.setdefault(i["category_label"], []).append(i)
    full = ['<div class="filters"><button data-f="ALL" aria-pressed="true">'
            + html.escape(L.t("all", "All")) + "</button>"]
    for st in (FAIL, WARN, PASS, NO_DATA, LLM_PENDING, MANUAL, NA):
        if counts.get(st):
            full.append(f'<button data-f="{st}">{STATUS_ICON[st]} ({counts[st]})</button>')
    full.append("</div>")
    for label, items in by_cat.items():
        full.append(f"<h3>{html.escape(label)}</h3>")
        for i in sorted(items, key=lambda x: (x["status"] != FAIL,
                                              SEVERITY_ORDER.get(x["severity"], 9))):
            cls = i["status"].replace("/", "").replace(" ", "_")
            full.append(
                f'<div class="row" data-st="{i["status"]}">'
                f'<div class="st {cls}">{STATUS_ICON[i["status"]]}</div>'
                f'<div class="sev">{html.escape(L.sev(i["severity"]))}<br>{i["id"]}</div>'
                f'<div><div class="ttl">{html.escape(L.title(i))}</div>'
                f'<div class="ev">{html.escape(i.get("evidence", ""))}</div></div></div>')
    parts.append(fold(L.t("full_checklist", "Every check, with its raw evidence"),
                      "".join(full), s["total_items"]))

    parts.append(f'<p class="foot">{html.escape(L.t("foot", "Registry"))} '
                 f'<code>{html.escape(str(data.get("registry_version", "")))}</code>'
                 f' &middot; {s["total_items"]} '
                 + html.escape(L.t("items_word", "items")) + "</p></div>")

    return ('<!doctype html><html lang="' + html.escape(L.code or "en") + '"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>SEO &mdash; {html.escape(data.get("domain", ""))}</title>'
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


def apply_llm_review(data: dict, review: dict) -> dict:
    """Fold a second, independent judgement into answers the first pass produced.

    Thirty items rest on one language model's reading of one page, unopposed. A
    second reader cannot make those verdicts more accurate on its own — but it can
    say when they are not reliable, and that is the part the score has no way to
    express otherwise.

    Agreement corroborates: the verdict stands and says it was checked twice.
    Disagreement does **not** pick a winner and does not average them. Two
    competent readings that conflict mean the page did not settle the question, so
    the item goes back to NO_DATA carrying both opinions. The reviewer therefore
    has a veto over confidence and no vote on the answer — which is deliberate: a
    reviewer that could overwrite a verdict is just a second first pass, and one
    that could only agree is decoration.

    Returns counts, so the caller can report what the second pass actually did.
    """
    valid = {PASS, FAIL, WARN, NA}
    stats = {"corroborated": 0, "contested": 0, "skipped": 0}
    for item in data["items"]:
        second = review.get(item["id"])
        if not second:
            continue
        verdict = str(second.get("status", "")).upper()
        if verdict not in valid:
            print(f"  review of {item['id']}: invalid status "
                  f"{second.get('status')!r}", file=sys.stderr)
            stats["skipped"] += 1
            continue
        # Only an answered LLM item can be reviewed. A script's verdict is not up
        # for discussion, and an item the first pass never answered would make the
        # reviewer the primary judge without anyone deciding that.
        if item.get("source") != "llm(answered)":
            print(f"  review of {item['id']}: not an answered LLM item "
                  f"({item.get('source')}, {item['status']}) — ignored",
                  file=sys.stderr)
            stats["skipped"] += 1
            continue

        note = str(second.get("evidence", "")).strip() or "no rationale given"
        if verdict == item["status"]:
            item["corroborated"] = True
            item["evidence"] = f"{item['evidence']} | second reading agrees: {note}"
            stats["corroborated"] += 1
        else:
            item["contested"] = {"first": item["status"], "second": verdict}
            item["evidence"] = (f"contested: first reading said {item['status']} "
                                f"({item['evidence']}); second said {verdict} "
                                f"({note})")
            item["status"] = NO_DATA
            item["source"] = "llm(contested)"
            stats["contested"] += 1
    if stats["contested"]:
        data["scores"] = load_scoring()(data["items"])
    return stats


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
    ap.add_argument("--llm-review", default="",
                    help="JSON of a second, independent judgement over the same "
                         "items. Agreement corroborates the verdict; disagreement "
                         "returns the item to NO_DATA carrying both readings. The "
                         "reviewer cannot overwrite a verdict or answer an "
                         "unanswered item.")
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

    if a.llm_review:
        with open(a.llm_review, encoding="utf-8") as f:
            review = json.load(f)
        stats = apply_llm_review(data, review)
        with open(a.results, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Second reading: {stats['corroborated']} corroborated, "
              f"{stats['contested']} contested (back to NO_DATA), "
              f"{stats['skipped']} ignored")
        if stats["contested"]:
            print("  Coverage drops by the contested items, and it should: two "
                  "readings that disagree did not settle the question.")

    try:
        lang = Lang(a.lang)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2
    gaps = lang.untranslated()
    if gaps:
        print(f"--lang {lang.code}: {' and '.join(gaps)} are not translated yet and "
              f"will appear in English. The report is English-only for client "
              f"delivery until they are filled in.", file=sys.stderr)
    written = [("Report", write(a.markdown, render_markdown(data, lang)))]
    if not a.no_html:
        written.append(("HTML", write(a.html, render_html(data, lang))))

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
    if s.get("seo_score") is None:
        print(f"\nNo SEO Score: {data.get('entry_error') or 'the site could not be read'}"
              f"\nCoverage {s['coverage_pct']}% ({s['decided']}/{s['applicable']})")
    else:
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
