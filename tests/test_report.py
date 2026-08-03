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
    FAIL, LLM_PENDING, NA, PASS, WARN, Lang, merge_llm_answers, priority_of,
    render_llm_queue, render_markdown,
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


if __name__ == "__main__":
    unittest.main()
