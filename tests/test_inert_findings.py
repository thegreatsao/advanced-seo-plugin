"""The recorded inert findings, kept in step with the registry they describe.

``tests/inert-findings.json`` is a measurement, not a declaration and not a gate.
It records which findings a ``none_severity`` assertion cannot act on, but it cannot
decide whether any one of them is deliberate advice or an item that cannot keep the
claim in its title.

Recomputing the AST measurement does not belong in the suite. These cheap invariants
make a stale or empty record visible; re-record and read it with

    python tests/inert_findings.py --out tests/inert-findings.json
"""
from __future__ import annotations

import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(ROOT, "tests", "inert-findings.json")
REGISTRY = os.path.join(ROOT, "skills", "seo-checklist", "resources", "config",
                        "checklist.json")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


class RecordedInertFindings(unittest.TestCase):

    def setUp(self):
        self.record = load(RECORD)
        self.registry = load(REGISTRY)

    def test_it_describes_this_registry(self):
        self.assertEqual(self.record["registry_version"],
                         self.registry["registry_version"],
                         "tests/inert-findings.json describes another registry — "
                         "re-record it with tests/inert_findings.py")

    def test_every_none_severity_item_is_accounted_for(self):
        registry_ids = {item["id"] for item in self.registry["items"]}
        recorded_ids = set(self.record["items"])
        none_severity_ids = {
            item["id"]
            for item in self.registry["items"]
            if "none_severity" in ((item.get("check") or {}).get("assert") or {})
        }
        self.assertLessEqual(recorded_ids, registry_ids)
        self.assertLessEqual(none_severity_ids, recorded_ids)

    def test_the_record_is_not_empty(self):
        self.assertTrue(self.record["items"], "the inert-findings record is empty")


if __name__ == "__main__":
    unittest.main()
