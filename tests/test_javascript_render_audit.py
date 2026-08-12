"""The render-parity audit distinguishes no measurement, a mismatch and a match."""

import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "seo-checklist", "scripts")
REGISTRY = os.path.join(ROOT, "skills", "seo-checklist", "resources", "config",
                        "checklist.json")
sys.path.insert(0, SCRIPTS)

import javascript_render_audit as render_audit  # noqa: E402
from checklist_runner import evaluate  # noqa: E402

with open(REGISTRY, encoding="utf-8") as registry_file:
    ITEMS = {item["id"]: item for item in json.load(registry_file)["items"]}

MB_105_ASSERTION = ITEMS["MB-105"]["check"]["assert"]
URL = "https://example.com/"
RAW_HTML = """<!doctype html><html><head><title>Raw title</title></head>
<body><h1>Raw heading</h1><a href="/inside">Inside</a></body></html>"""
DIFFERENT_HTML = """<!doctype html><html><head><title>Rendered title</title></head>
<body><h1>Rendered heading</h1></body></html>"""


def audit_with(rendered_html, render_error=None):
    fetched = {"error": None}
    with mock.patch.object(render_audit, "load_html",
                           return_value=(RAW_HTML, URL, fetched)), \
         mock.patch.object(render_audit, "render_with_playwright",
                           return_value=(rendered_html, render_error)):
        return render_audit.audit(URL)


class JavascriptRenderParity(unittest.TestCase):
    def test_unavailable_renderer_omits_diffs(self):
        result = audit_with(None, "playwright not installed")

        self.assertNotIn("diffs", result)
        self.assertIsNone(result["rendered"])
        self.assertEqual(result["render_error"], "playwright not installed")
        self.assertIn("raw", result)

    def test_mb_105_reports_no_data_without_a_rendered_document(self):
        result = audit_with(None, "browser launch failed")

        passed, evidence = evaluate(MB_105_ASSERTION, result)
        self.assertIsNone(passed)
        self.assertEqual(evidence, "diffs missing")

    def test_a_rendered_difference_is_present_and_fails_mb_105(self):
        result = audit_with(DIFFERENT_HTML)

        self.assertIn("diffs", result)
        self.assertGreater(len(result["diffs"]), 0)
        self.assertIs(evaluate(MB_105_ASSERTION, result)[0], False)

    def test_a_matching_render_is_present_and_passes_mb_105(self):
        result = audit_with(RAW_HTML)

        self.assertIn("diffs", result)
        self.assertEqual(result["diffs"], [])
        self.assertIs(evaluate(MB_105_ASSERTION, result)[0], True)
