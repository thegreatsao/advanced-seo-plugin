"""Declared fixture expectations, compared with two real runner audits.

The manifest is the oracle. Its verdicts were written from checklist titles and
fixture construction before this module was run; this file only loads and reports
them. A mismatch is stage 1's result, not permission to edit either side.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "seo-checklist", "scripts")
REGISTRY = os.path.join(
    ROOT, "skills", "seo-checklist", "resources", "config", "checklist.json")
MANIFEST = os.path.join(ROOT, "tests", "fixtures", "expectations.json")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import FixtureSite, spawn  # noqa: E402

DECLARED_IDS = {
    "AR-151", "AR-158", "AR-162", "BL-081", "CI-008", "CI-019",
    "CN-041", "CN-054", "GO-132", "GO-137", "GO-138", "LO-200",
    "MB-096", "MB-097", "MD-185", "MS-022", "MS-029", "TE-168",
    "TE-172", "TE-174", "TECH-001",
}
ALLOWED = {"PASS", "WARN", "FAIL", "N/A", "INDETERMINATE"}
SITE = None
RESULTS: dict[str, dict[str, str]] = {}


def manifest() -> dict:
    with open(MANIFEST, encoding="utf-8") as stream:
        return json.load(stream)


def audit(label: str, url: str) -> dict[str, str]:
    """Run the unmodified checker against one served fixture."""
    out = os.path.join(SITE.dir, f"oracle-{label}.json")
    artifacts = []
    for flag, filename in (("--rendered-json", "rendered.json"),
                           ("--cwv-json", "cwv.json")):
        path = SITE.artifact(label, filename)
        if path:
            artifacts += [flag, path]
    proc = spawn(
        [sys.executable, os.path.join(SCRIPTS, "checklist_runner.py"), url,
         "--allow-private", "--sample", "3", "--max-rps", "0",
         "--no-history", "--no-prompt", "--quiet", "--timeout", "120",
         "--json", out, *artifacts],
        timeout=900)
    if proc.returncode != 0:
        raise AssertionError(
            f"the {label} oracle audit exited {proc.returncode}\n"
            f"{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}")
    with open(out, encoding="utf-8") as stream:
        payload = json.load(stream)
    rows = payload["items"]
    if isinstance(rows, dict):
        return {item_id: row["status"] for item_id, row in rows.items()}
    return {row["id"]: row["status"] for row in rows}


def comparison() -> tuple[dict[str, dict[str, int]], list[dict[str, str]]]:
    tally = {}
    differences = []
    for label, declarations in manifest()["fixtures"].items():
        counts = {"matched": 0, "disagreed": 0, "indeterminate": 0}
        for item_id, declared in declarations.items():
            expected = declared["expect"]
            if expected == "INDETERMINATE":
                counts["indeterminate"] += 1
                continue
            actual = RESULTS[label][item_id]
            if actual == expected:
                counts["matched"] += 1
            else:
                counts["disagreed"] += 1
                differences.append({
                    "fixture": label,
                    "item": item_id,
                    "expected": expected,
                    "actual": actual,
                    "why": declared["why"],
                })
        tally[label] = counts
    return tally, differences


def setUpModule():
    global SITE
    SITE = FixtureSite().start()
    for label, url in (("good", SITE.good), ("broken", SITE.broken)):
        RESULTS[label] = audit(label, url)


def tearDownModule():
    try:
        tally, differences = comparison()
        print("\nFixture oracle stage 1")
        for label in ("good", "broken"):
            counts = tally[label]
            print(f"  {label}: 21 declarations — {counts['matched']} matched, "
                  f"{counts['disagreed']} disagreed, "
                  f"{counts['indeterminate']} indeterminate")
        totals = {key: sum(row[key] for row in tally.values())
                  for key in ("matched", "disagreed", "indeterminate")}
        print(f"  total: 42 declarations — {totals['matched']} matched, "
              f"{totals['disagreed']} disagreed, "
              f"{totals['indeterminate']} indeterminate")
        print("  differences:")
        if not differences:
            print("    none")
        for row in differences:
            print(f"    {row['fixture']} {row['item']}: expected "
                  f"{row['expected']}, actual {row['actual']} — {row['why']}")
    finally:
        if SITE:
            SITE.stop()


class ManifestContract(unittest.TestCase):

    def test_metadata_matches_the_registry(self):
        declared = manifest()
        with open(REGISTRY, encoding="utf-8") as stream:
            registry_version = json.load(stream)["registry_version"]
        self.assertEqual(declared["schema_version"], 1)
        self.assertEqual(declared["registry_version"], registry_version)
        self.assertEqual(
            declared["declared_from"],
            "item title plus fixture construction; never from a run")

    def test_both_fixtures_declare_all_21_items(self):
        fixtures = manifest()["fixtures"]
        self.assertEqual(set(fixtures), {"good", "broken"})
        for label, declarations in fixtures.items():
            self.assertEqual(set(declarations), DECLARED_IDS, label)

    def test_every_declaration_has_a_supported_verdict_and_reason(self):
        for label, declarations in manifest()["fixtures"].items():
            for item_id, declared in declarations.items():
                with self.subTest(fixture=label, item=item_id):
                    self.assertIn(declared["expect"], ALLOWED)
                    self.assertTrue(declared["why"].strip())


class FixtureOracle(unittest.TestCase):

    def test_every_settled_declaration_matches_the_real_runner(self):
        """Every settled declaration agrees after the stage-one triage."""
        _tally, differences = comparison()
        detail = "\n".join(
            f"{row['fixture']} {row['item']}: expected {row['expected']}, "
            f"actual {row['actual']} — {row['why']}"
            for row in differences)
        self.assertEqual(differences, [], detail)


if __name__ == "__main__":
    unittest.main()
