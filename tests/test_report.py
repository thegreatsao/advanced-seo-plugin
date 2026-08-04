"""Tests for the report layer: the merge rules and the prioritisation.

The merge is the one place where a text file can overwrite a machine verdict, so
its boundary is worth pinning down. Prioritisation is the one place where a
ranking claims to know what to do first.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "seo-checklist")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

from checklist_report import (  # noqa: E402
    FAIL, LLM_PENDING, MANUAL, NA, NO_DATA, PASS, WARN, Lang, apply_llm_review,
    fix_rows, history_section, merge_llm_answers, priority_of, render_html,
    render_llm_queue, render_markdown, write_fixes,
)

I18N = os.path.join(SKILL, "resources", "i18n")


def item(item_id, status, **extra):
    row = {"id": item_id, "title": item_id, "category": "content",
           "category_label": "Content", "severity": "high", "effort": "low",
           "status": status, "evidence": "", "fix": "do the thing"}
    row.update(extra)
    return row


def results(*items):
    return {"url": "https://example.com", "mode": "page", "profile": "default",
            "registry_version": "test", "items": list(items),
            "scores": {}, "runs": {}}


class Merge(unittest.TestCase):
    def test_fills_a_pending_item(self):
        data = results(item("CN-047", LLM_PENDING, source="llm"))
        n = merge_llm_answers(data, {"CN-047": {"status": PASS, "evidence": "clean"}})
        self.assertEqual(n, 1)
        self.assertEqual(data["items"][0]["status"], PASS)

    def test_cannot_overwrite_a_script_verdict(self):
        """An answers file must not be able to talk a failure into a pass."""
        data = results(item("CI-001", FAIL, source="script"))
        n = merge_llm_answers(data, {"CI-001": {"status": PASS, "evidence": "trust me"}})
        self.assertEqual(n, 0)
        self.assertEqual(data["items"][0]["status"], FAIL)

    def test_rejects_a_status_outside_the_vocabulary(self):
        data = results(item("CN-047", LLM_PENDING, source="llm"))
        merge_llm_answers(data, {"CN-047": {"status": "GREAT", "evidence": "x"}})
        self.assertEqual(data["items"][0]["status"], LLM_PENDING)

    def test_na_is_an_acceptable_answer(self):
        data = results(item("CN-060", LLM_PENDING, source="llm"))
        n = merge_llm_answers(data, {"CN-060": {"status": NA,
                                                "evidence": "needs a second fetch"}})
        self.assertEqual(n, 1)
        self.assertEqual(data["items"][0]["status"], NA)


class Priority(unittest.TestCase):
    def test_cheap_work_outranks_equally_severe_expensive_work(self):
        cheap = item("A", FAIL, severity="high", effort="low")
        dear = item("B", FAIL, severity="high", effort="high")
        self.assertGreater(priority_of(cheap), priority_of(dear))

    def test_severity_still_dominates_within_one_effort_level(self):
        crit = item("A", FAIL, severity="critical", effort="medium")
        low = item("B", FAIL, severity="low", effort="medium")
        self.assertGreater(priority_of(crit), priority_of(low))

    def test_a_critical_item_is_never_ranked_below_a_low_one(self):
        """Effort may reorder peers; it must not bury a critical failure."""
        crit = item("A", FAIL, severity="critical", effort="high")
        low = item("B", FAIL, severity="low", effort="low")
        self.assertGreaterEqual(priority_of(crit), priority_of(low))


class Queue(unittest.TestCase):
    def test_lens_split_only_takes_its_own_slice(self):
        data = results(item("A", LLM_PENDING, source="llm", lens="copy"),
                       item("B", LLM_PENDING, source="llm", lens="layout"))
        copy_q = render_llm_queue(data, "copy")
        self.assertIn("### A", copy_q)
        self.assertNotIn("### B", copy_q)
        self.assertIn("seo-llm-copy", copy_q)

    def test_combined_queue_holds_everything(self):
        data = results(item("A", LLM_PENDING, source="llm", lens="copy"),
                       item("B", LLM_PENDING, source="llm", lens="layout"))
        both = render_llm_queue(data)
        self.assertIn("### A", both)
        self.assertIn("### B", both)


class Localisation(unittest.TestCase):
    def test_every_shipped_translation_parses_and_declares_a_language(self):
        for name in os.listdir(I18N):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(I18N, name), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data.get("lang"), name[:-5], name)
            for block in ("strings", "statuses", "severities", "efforts"):
                self.assertIn(block, data, f"{name} has no {block}")

    def test_unknown_language_is_refused_rather_than_silently_english(self):
        with self.assertRaises(FileNotFoundError):
            Lang("xx")

    def test_translated_report_renders_and_keeps_the_numbers(self):
        data = results(item("A", FAIL))
        from checklist_runner import score
        data["scores"] = score(data["items"])
        out = render_markdown(data, Lang("ru"))
        self.assertIn("Аудит по чеклисту", out)
        self.assertIn("A", out)

    def test_english_is_the_default_and_needs_no_file(self):
        data = results(item("A", PASS))
        from checklist_runner import score
        data["scores"] = score(data["items"])
        self.assertIn("SEO Checklist Audit", render_markdown(data))

    def test_a_partly_translated_language_names_what_is_still_english(self):
        """A reader cannot tell a layer that was left in English from a layer that
        was considered and kept. The report has to say which."""
        reported = Lang("ru").untranslated()
        self.assertIn("item titles", reported)
        self.assertIn("recommendations", reported)

    def test_the_report_chrome_is_counted_rather_than_declared_complete(self):
        """This claim was wrong, and wrong in the flattering direction.

        `untranslated()` named the two opt-in layers and said nothing about the
        report's own wording, on the assumption that it was complete. Six of the
        fifty-one strings had no Russian at all — the whole "what was audited"
        block, which is the highest-stakes prose in the document — and `t()` falls
        back to English silently, so nothing showed. The count now comes from the
        file, so the next string added is reported the day it is added.
        """
        missing = Lang("ru").missing_strings()
        self.assertTrue(missing, "if ru.json is now complete, so much the better — "
                                 "but then this test needs a different fixture, not "
                                 "deleting")
        self.assertTrue(any("report string" in w for w in Lang("ru").untranslated()))
        # And the count has to be real: every key it names must be one the report
        # actually asks for, or the warning is noise.
        with open(os.path.join(SKILL, "scripts", "checklist_report.py"),
                  encoding="utf-8") as f:
            source = f.read()
        for key in missing:
            self.assertIn(f'"{key}"', source)

    def test_english_reports_nothing_untranslated(self):
        self.assertEqual(Lang("en").untranslated(), [])

    def test_a_filled_block_drops_out_of_the_warning(self):
        lang = Lang("ru")
        lang.data["item_titles"] = {"A": "Заголовок"}
        self.assertNotIn("item titles", lang.untranslated())
        lang.data["item_fixes"] = {"A": "Сделать"}
        self.assertNotIn("recommendations", lang.untranslated())

    def test_every_category_in_the_registry_has_a_translated_explanation(self):
        """The category explanation is the layer a non-specialist reads. A missing
        one silently falls back to English in the middle of a translated page,
        which is exactly the ambiguity `untranslated()` exists to remove."""
        with open(os.path.join(SKILL, "resources", "config",
                               "checklist.json"), encoding="utf-8") as f:
            categories = {i["category"] for i in json.load(f)["items"]}
        for name in os.listdir(I18N):
            if not name.endswith(".json"):
                continue
            translated = set(Lang(name[:-5]).data.get("categories", {}))
            missing = sorted(categories - translated)
            self.assertEqual(missing, [], f"{name} is missing: {missing}")


class SecondReading(unittest.TestCase):
    """An unopposed judgement reported with the confidence of a measured status is
    the LLM queue's weak point. The reviewer's power is deliberately asymmetric:
    it can withdraw confidence, never substitute a verdict."""

    def answered(self, status=PASS, evidence="looked fine"):
        row = item("CN-047", status, source="llm(answered)",
                   evidence=f"LLM: {evidence}")
        data = results(row)
        from checklist_runner import score
        data["scores"] = score(data["items"])
        return data

    def test_agreement_corroborates_and_keeps_the_verdict(self):
        data = self.answered(PASS)
        stats = apply_llm_review(data, {"CN-047": {"status": "PASS",
                                                   "evidence": "read it too"}})
        row = data["items"][0]
        self.assertEqual(stats["corroborated"], 1)
        self.assertEqual(row["status"], PASS)
        self.assertTrue(row["corroborated"])
        self.assertIn("second reading agrees", row["evidence"])

    def test_disagreement_returns_the_item_to_undecided(self):
        """Not a winner, not an average. Two careful readings that conflict mean
        the page did not settle the question."""
        data = self.answered(PASS)
        stats = apply_llm_review(data, {"CN-047": {"status": "FAIL",
                                                   "evidence": "the H1 lies"}})
        row = data["items"][0]
        self.assertEqual(stats["contested"], 1)
        self.assertEqual(row["status"], NO_DATA)
        self.assertEqual(row["contested"], {"first": PASS, "second": FAIL})
        self.assertIn("PASS", row["evidence"])
        self.assertIn("FAIL", row["evidence"])

    def test_a_contested_item_costs_coverage(self):
        data = self.answered(PASS)
        before = data["scores"]["coverage_pct"]
        apply_llm_review(data, {"CN-047": {"status": "FAIL", "evidence": "no"}})
        self.assertLess(data["scores"]["coverage_pct"], before)

    def test_it_cannot_touch_a_script_verdict(self):
        """A measurement is not an opinion. Letting a reviewer contest one would
        make every script result negotiable."""
        data = results(item("CI-001", PASS, source="script"))
        from checklist_runner import score
        data["scores"] = score(data["items"])
        stats = apply_llm_review(data, {"CI-001": {"status": "FAIL", "evidence": "x"}})
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(data["items"][0]["status"], PASS)

    def test_it_cannot_answer_an_unanswered_item(self):
        """That would make the reviewer the primary judge, with nobody deciding to
        promote it."""
        data = results(item("CN-047", LLM_PENDING))
        from checklist_runner import score
        data["scores"] = score(data["items"])
        stats = apply_llm_review(data, {"CN-047": {"status": "PASS", "evidence": "x"}})
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(data["items"][0]["status"], LLM_PENDING)

    def test_an_invalid_status_is_ignored_not_applied(self):
        data = self.answered(PASS)
        stats = apply_llm_review(data, {"CN-047": {"status": "PROBABLY", "evidence": "x"}})
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(data["items"][0]["status"], PASS)

    def test_items_the_reviewer_says_nothing_about_are_untouched(self):
        data = self.answered(PASS)
        apply_llm_review(data, {})
        self.assertEqual(data["items"][0]["status"], PASS)
        self.assertNotIn("corroborated", data["items"][0])

    def test_the_queue_tells_the_reader_a_second_pass_exists(self):
        data = results(item("CN-047", LLM_PENDING, lens="copy"))
        out = render_llm_queue(data, "copy")
        self.assertIn("--llm-review", out)
        self.assertIn("seo-llm-adversary", out)


class NoScoreSurvivesEveryRenderer(unittest.TestCase):
    """The runner refuses to print a score when nothing was read. Every surface
    downstream has to refuse it too — the HTML tile printed the literal `None`,
    which reads as a broken tool in the one file that gets handed to a client."""

    def _unread(self):
        from checklist_runner import score
        data = results(item("A", "NO_DATA"))
        data["scores"] = score(data["items"])
        data["entry_reachable"] = False
        data["entry_error"] = "soft 404: a 200 response titled '404 Not Found'"
        return data

    def test_the_score_is_none_when_nothing_was_decided(self):
        self.assertIsNone(self._unread()["scores"]["seo_score"])

    def test_the_markdown_says_why_instead_of_a_number(self):
        out = render_markdown(self._unread())
        self.assertIn("could not be read", out)
        self.assertNotIn("None/100", out)

    def test_the_html_prints_no_number_at_all(self):
        """Asserted on the intent, not on the wording: no number anywhere, and an
        explanation in its place. The exact sentence has changed once already."""
        from checklist_report import render_html
        out = render_html(self._unread())
        self.assertNotIn(">None<", out)
        self.assertNotIn("None/100", out)
        self.assertIn("could not be read", out)


class WhatWasAudited(unittest.TestCase):
    """Four facts the runner records and prints, and the report never mentioned.

    Each one says the numbers may not describe the page a visitor gets: the run was
    allowed off the public internet, the entry page looked like an interstitial and
    was scored anyway, the page carried almost no text, or some verdicts came from a
    file the operator measured elsewhere. The report is what gets handed to
    somebody, so an omission here is the same failure as printing a score for a site
    that was never read — one surface further along.
    """

    def _scored(self, **extra):
        from checklist_runner import score
        data = results(item("A", PASS), item("B", FAIL))
        data["scores"] = score(data["items"])
        data["entry_reachable"] = True
        data.update(extra)
        return data

    def test_a_private_run_is_named_on_every_surface(self):
        from checklist_report import provenance_warnings, render_html
        data = self._scored(allow_private=True, entry_private=True)
        self.assertTrue(any("only reachable" in w for w in provenance_warnings(data)))
        for out in (render_markdown(data), render_html(data)):
            self.assertIn("--allow-private", out)
            self.assertIn("staging", out)

    def test_the_flag_and_a_private_host_are_different_claims(self):
        """`--allow-private` says what was permitted; `entry_private` says what
        happened. Only the second means the external-API items were undecidable, and
        saying so about a public site would be a caveat on nothing."""
        from checklist_report import provenance_warnings
        permitted = provenance_warnings(self._scored(allow_private=True,
                                                    entry_private=False))
        self.assertEqual(len(permitted), 1)
        self.assertNotIn("could not be decided", permitted[0])
        happened = provenance_warnings(self._scored(allow_private=True,
                                                   entry_private=True))
        self.assertIn("could not be decided", happened[0])

    def test_a_scored_interstitial_says_so(self):
        """A --no-page-guard run produced a clean-looking deliverable that never
        mentioned it had graded a Cloudflare challenge."""
        from checklist_report import provenance_warnings, render_html
        data = self._scored(entry_guard="bot_challenge", entry_guard_enforced=False)
        self.assertTrue(any("bot challenge" in w for w in provenance_warnings(data)))
        self.assertIn("bot challenge", render_html(data))
        self.assertIn("bot challenge", render_markdown(data))

    def test_a_verdict_from_a_supplied_measurement_says_where_it_came_from(self):
        """"LCP 820 ms — PASS" looks identical whether the tool measured it or was
        handed it in a file, and eight items can be decided the second way."""
        from checklist_report import provenance_warnings, render_html
        data = self._scored(artifacts={
            "cwv_json": {"path": "/t/cwv.json", "describes": "https://example.com/",
                         "matches_audited_url": True}})
        self.assertTrue(any("supplied with the run" in w
                            for w in provenance_warnings(data)))
        for out in (render_markdown(data), render_html(data)):
            self.assertIn("cwv", out)

    def test_a_rejected_artifact_is_not_advertised_as_evidence(self):
        """It decided nothing — its items are NO_DATA with the reason — so naming it
        here would tell the reader a measurement was used when it was refused."""
        from checklist_report import provenance_warnings
        data = self._scored(artifacts={
            "cwv_json": {"path": "/t/cwv.json", "describes": "https://other.example/",
                         "matches_audited_url": False}})
        self.assertEqual(provenance_warnings(data), [])

    def test_an_enforced_guard_is_not_a_caveat(self):
        """When the guard stopped the run there is no score to qualify, and the
        unreachable banner already explains itself."""
        from checklist_report import provenance_warnings
        data = self._scored(entry_guard="soft_404", entry_guard_enforced=True)
        self.assertEqual(provenance_warnings(data), [])

    def test_a_thin_page_is_named_but_an_unread_one_is_not(self):
        from checklist_report import provenance_warnings
        thin = self._scored(entry_thin=True, entry_visible_words=12)
        self.assertTrue(any("12" in w for w in provenance_warnings(thin)))
        unread = self._scored(entry_thin=True, entry_visible_words=0,
                             entry_reachable=False)
        self.assertEqual(provenance_warnings(unread), [])

    def test_a_clean_public_run_carries_no_caveat(self):
        from checklist_report import provenance_warnings
        self.assertEqual(provenance_warnings(self._scored()), [])


class HistoryReachesTheFile(unittest.TestCase):
    """`.seo-runs/` held every run and the comparison reached a terminal at best.

    A checklist is a thing people re-run, so the question "did last month's fixes
    work" is the second one a returning reader has — and the report could not answer
    it from data that was already on disk.
    """

    def _data(self, *changes, **extra):
        from checklist_runner import score
        data = results(item("CN-047", FAIL), item("CN-048", PASS))
        # A real `scores` block, because both renderers read more of it than the
        # history section does and a hand-made stub would only test this test.
        data["scores"] = dict(score(data["items"]), seo_score=71, coverage_pct=55)
        data["entry_reachable"] = True
        data["compared_with"] = {"started_at": "2026-07-01T09:30:00+00:00",
                                 "seo_score": 64, "coverage_pct": 50,
                                 "registry_version": "test"}
        data["diff"] = list(changes)
        data.update(extra)
        return data

    def _change(self, item_id, was, now, direction, severity="high"):
        return {"id": item_id, "title": f"{item_id} title", "from": was, "to": now,
                "direction": direction, "severity": severity, "evidence": ""}

    def test_no_baseline_means_no_section(self):
        """A first audit has nothing to compare with, and an empty "since last time"
        heading would imply there was a last time."""
        from checklist_runner import score
        data = results(item("CN-047", FAIL))
        data["scores"] = score(data["items"])
        data["entry_reachable"] = True
        data["compared_with"] = None
        data["diff"] = None
        self.assertEqual(history_section(data), [])
        self.assertNotIn("Since the previous audit", render_markdown(data, Lang()))

    def test_the_baseline_is_named_not_implied(self):
        """"Since the previous run" is not a date. A comparison whose other half is
        anonymous cannot be checked by the person being shown it."""
        text = "\n".join(history_section(self._data()))
        self.assertIn("2026-07-01T09:30", text)
        self.assertIn("64", text)
        self.assertIn("71", text)

    def test_a_fix_and_a_regression_are_told_apart(self):
        text = "\n".join(history_section(self._data(
            self._change("CN-047", FAIL, PASS, "improved"),
            self._change("CN-048", PASS, FAIL, "regressed"))))
        fixed = text.index("Fixed since then")
        worse = text.index("Got worse")
        self.assertLess(fixed, worse, "the good news should not bury the bad")
        self.assertIn("| CN-047 |", text)
        self.assertIn("| CN-048 |", text)

    def test_losing_the_evidence_is_not_reported_as_a_regression(self):
        """PASS -> NO_DATA is the run losing the ability to tell, not the site
        getting worse. Filing it under regressions would tell a client their site
        broke when the measurement broke."""
        text = "\n".join(history_section(self._data(
            self._change("CN-047", PASS, NO_DATA, "evidence"))))
        self.assertNotIn("Got worse", text)
        self.assertIn("not on the site", text)

    def test_a_changed_registry_is_said_out_loud(self):
        """A score that moved because the checklist changed is not a site that
        moved, and a reader cannot know that unless told."""
        data = self._data(self._change("CN-047", FAIL, PASS, "improved"),
                          diff_note="previous run used registry abc, this one def")
        self.assertIn("registry abc", "\n".join(history_section(data)))

    def test_both_renderers_carry_it(self):
        data = self._data(self._change("CN-047", FAIL, PASS, "improved"))
        self.assertIn("Since the previous audit", render_markdown(data, Lang()))
        html = render_html(data, Lang())
        self.assertIn("Since the previous audit", html)
        self.assertIn("+7", html, "the score movement is not shown")


class TheFixListIsMachineReadable(unittest.TestCase):
    """`checklist-results.json` is the audit log, not a task list. Getting the
    actionable part into a tracker meant parsing the report or filtering the log."""

    def _data(self):
        return results(
            item("A-001", FAIL, severity="critical", effort="low"),
            item("A-002", WARN, severity="medium", effort="high"),
            item("A-003", MANUAL, severity="high"),
            item("A-004", PASS),
            item("A-005", NO_DATA),
            item("A-006", LLM_PENDING, source="llm"),
            item("A-007", NA),
        )

    def test_only_the_actionable_items_are_in_it(self):
        """NO_DATA is not a fix — it is usually work for whoever runs the audit, not
        for whoever owns the site — and LLM_PENDING is a question still waiting for
        an answer. Either one would fill a sprint with the auditor's own business."""
        ids = [r["id"] for r in fix_rows(self._data())]
        self.assertEqual(set(ids), {"A-001", "A-002", "A-003"})

    def test_it_is_ordered_the_way_the_report_orders_it(self):
        rows = fix_rows(self._data())
        self.assertEqual([r["id"] for r in rows][0], "A-001")
        self.assertEqual([r["priority"] for r in rows],
                         sorted((r["priority"] for r in rows), reverse=True))

    def test_the_status_travels_with_the_row(self):
        """A tracker importing these has to be able to tell a failing check from a
        task nobody could automate."""
        by_id = {r["id"]: r for r in fix_rows(self._data())}
        self.assertEqual(by_id["A-003"]["status"], MANUAL)
        self.assertEqual(by_id["A-001"]["status"], FAIL)

    def test_the_url_column_says_what_it_actually_is(self):
        """Most items record no page: a page-level check over a sample reports the
        worst page's verdict without its address, and a site-level check has no page
        to name. A column called `url` would be read as "fix this page"."""
        row = fix_rows(self._data())[0]
        self.assertIn("audited_url", row)
        self.assertNotIn("url", set(row) - {"audited_url"})

    def test_csv_and_json_hold_the_same_rows(self):
        import csv as _csv
        import tempfile
        data = self._data()
        with tempfile.TemporaryDirectory() as d:
            csv_path = write_fixes(os.path.join(d, "f.csv"), data)
            json_path = write_fixes(os.path.join(d, "f.json"), data)
            with open(csv_path, encoding="utf-8-sig", newline="") as f:
                from_csv = [r["id"] for r in _csv.DictReader(f)]
            with open(json_path, encoding="utf-8") as f:
                from_json = [r["id"] for r in json.load(f)]
        self.assertEqual(from_csv, from_json)
        self.assertEqual(from_csv, [r["id"] for r in fix_rows(data)])

    def test_the_csv_opens_in_a_spreadsheet_without_mojibake(self):
        """Excel reads a plain UTF-8 CSV as Latin-1, so a BOM is the difference
        between an item title and a row of garbage. The destination for this file is
        overwhelmingly likely to be somebody's spreadsheet."""
        import tempfile
        data = results(item("A-001", FAIL, title="Заголовок с не-ASCII"))
        with tempfile.TemporaryDirectory() as d:
            path = write_fixes(os.path.join(d, "f.csv"), data)
            with open(path, "rb") as f:
                raw = f.read()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "no UTF-8 BOM")
        self.assertIn("Заголовок".encode(), raw)


if __name__ == "__main__":
    unittest.main()
