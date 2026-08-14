"""Declared fixture expectations, compared with two real runner audits.

The manifest is the oracle. Its verdicts were written from checklist titles and
fixture construction before this module was run; this file only loads and reports
them. A mismatch is a triage input, not permission to edit either side silently.

Nothing in this module can be run without running the fixtures. `setUpModule`
audits all four origins whichever test is selected, so
`unittest tests.test_fixture_oracle.ManifestContract` — a check that the id sets
and the manifest agree, touching no verdict — answers every undeclared item on the
way. **Commit a new declaration before running anything here at all**, including
the tests that look like they only read the manifest. This cost the ordering proof
for one batch on 2026-08-14; the declarations were written first and git cannot
show it.
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

HTTP_DECLARED_IDS = {
    "AR-146", "AR-151", "AR-158", "AR-162", "BL-081", "BL-084",
    "BL-086", "BL-087", "CI-004", "CI-008", "CI-019", "CN-034",
    "CN-035", "CN-041", "CN-048", "CN-051", "CN-054", "CN-065",
    "CN-066", "GO-132", "GO-137", "GO-138", "IN-123", "LO-200",
    "MB-093", "MB-094", "MB-096", "MB-097", "MB-103", "MB-104",
    "MD-185", "MS-020", "MS-021", "MS-022", "MS-026", "MS-028",
    "MS-029", "MS-030", "MS-031", "SP-214", "SP-215", "SP-216",
    "SE-117", "TE-166", "TE-168", "TE-172", "TE-174", "TECH-001",
    # Stage 2b, the first six of the sixty-eight decidable items nobody had
    # declared. Five more crawl items were left undeclared on purpose: their
    # verdicts had already been read off a run in the session that would have
    # declared them, and a declaration made after seeing the answer proves
    # nothing. See ROADMAP.md.
    "BL-083", "CI-001", "CI-003", "CI-005", "CI-015", "LO-198",
    "AR-147", "AR-155", "CI-006", "CI-009", "CI-011", "CI-012", "CI-016",
    "GEO-001", "MD-186", "MD-187", "TE-176",
    # Stage 2c: the five crawl items left undeclared above, the twelve fetch
    # items whose verdicts a warn-band measurement had already printed, and
    # the three that were declared and withdrawn. No session that had read
    # those verdicts could declare them; this batch was written by one that
    # had not.
    #
    # MS-033, CN-068 and GO-131 are the withdrawn three, and their `good` side
    # is honest about not being blind: HANDOFF-4 §5.2 records what the sampled
    # run answered. Each is reasoned from /privacy.html, which carries no
    # social tags, no analytics snippet and no byline, and all three are
    # declared *before* the fixture question in KNOWN-ISSUES.md §6 is settled,
    # so repairing the fixture has to disagree with a declaration rather than
    # quietly agree with itself.
    "AR-149", "AR-154", "AR-163", "CI-018", "CN-039", "CN-068", "GEO-008",
    "GO-131", "GO-136", "MB-102", "MD-190", "MS-032", "MS-033", "SP-109",
    "SP-110", "TE-170", "TECH-002",
    # Stage 2d. Two are INDETERMINATE on purpose and neither is a shrug:
    # KW-076 reads {keyword}, an operator input this audit does not pass, and
    # MB-105 compares served HTML against a rendered DOM, which exists only where
    # a browser does — Playwright is installed here and on no CI runner, so any
    # settled verdict for it would be a claim about this laptop.
    "AR-152", "CI-013", "CN-036", "GEO-002", "GEO-003", "KW-076", "MB-095",
    "MB-098", "MB-100", "MB-105", "MD-184", "MD-189", "TE-169", "TE-177",
    # Stage 2e. SE-118 is declared on all four origins and means different things on
    # each pair: the HTTP origins have no certificate to judge, and the HTTPS pair is
    # where the item has a subject at all.
    "AR-153", "GEO-004", "GEO-005", "GEO-006", "GEO-007", "GO-143", "GO-144",
    "GO-145", "IN-121", "IN-122", "IN-127", "IN-128", "SE-118", "TE-180",
    "TECH-003",
}
TLS_DECLARED_IDS = {"AR-150", "CI-014", "SE-115", "SE-117", "SE-118", "SE-120",
                    "TE-175"}
DECLARED_IDS = {
    "good": HTTP_DECLARED_IDS,
    "broken": HTTP_DECLARED_IDS,
    "good_tls": TLS_DECLARED_IDS,
    "broken_tls": TLS_DECLARED_IDS,
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
                           ("--cwv-json", "cwv.json"),
                           ("--links-csv", "top-linking-sites.csv")):
        path = SITE.artifact(label, filename)
        if path:
            artifacts += [flag, path]
    proc = spawn(
        [sys.executable, os.path.join(SCRIPTS, "checklist_runner.py"), url,
         "--allow-private", "--sample", "3", "--max-rps", "0",
         "--no-history", "--no-prompt", "--quiet", "--timeout", "120",
         "--json", out, *artifacts], env=SITE.environment(label),
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


def coverage() -> tuple[int, int, int]:
    """Unique items, items settled for both site qualities, and opposed items."""
    fixtures = manifest()["fixtures"]
    item_ids = set().union(*(set(row) for row in fixtures.values()))
    settled_both = 0
    opposed = 0
    for item_id in item_ids:
        by_side = {"good": set(), "broken": set()}
        all_settled = set()
        for label, declarations in fixtures.items():
            declared = declarations.get(item_id)
            if not declared or declared["expect"] == "INDETERMINATE":
                continue
            status = declared["expect"]
            all_settled.add(status)
            by_side["good" if label.startswith("good") else "broken"].add(status)
        if all(by_side.values()):
            settled_both += 1
        if len(all_settled) > 1:
            opposed += 1
    return len(item_ids), settled_both, opposed


def setUpModule():
    global SITE
    SITE = FixtureSite().start()
    for label, url in (("good", SITE.good), ("broken", SITE.broken),
                       ("good_tls", SITE.good_tls),
                       ("broken_tls", SITE.broken_tls)):
        RESULTS[label] = audit(label, url)


def tearDownModule():
    try:
        tally, differences = comparison()
        print("\nFixture oracle through stage 3")
        for label in manifest()["fixtures"]:
            counts = tally[label]
            declarations = len(manifest()["fixtures"][label])
            print(f"  {label}: {declarations} declarations — "
                  f"{counts['matched']} matched, "
                  f"{counts['disagreed']} disagreed, "
                  f"{counts['indeterminate']} indeterminate")
        totals = {key: sum(row[key] for row in tally.values())
                  for key in ("matched", "disagreed", "indeterminate")}
        declarations = sum(len(row) for row in manifest()["fixtures"].values())
        print(f"  total: {declarations} declarations — "
              f"{totals['matched']} matched, "
              f"{totals['disagreed']} disagreed, "
              f"{totals['indeterminate']} indeterminate")
        items, settled_both, opposed = coverage()
        print(f"  coverage: {items} items declared, {settled_both} settled on both "
              f"sides, {opposed} opposed across fixture origins")
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

    def test_both_fixtures_declare_all_items(self):
        fixtures = manifest()["fixtures"]
        self.assertEqual(set(fixtures), set(DECLARED_IDS))
        for label, declarations in fixtures.items():
            self.assertEqual(set(declarations), DECLARED_IDS[label], label)

    def test_every_declaration_has_a_supported_verdict_and_reason(self):
        for label, declarations in manifest()["fixtures"].items():
            for item_id, declared in declarations.items():
                with self.subTest(fixture=label, item=item_id):
                    self.assertIn(declared["expect"], ALLOWED)
                    self.assertTrue(declared["why"].strip())


class FixtureOracle(unittest.TestCase):

    def test_every_settled_declaration_matches_the_real_runner(self):
        """Every settled declaration agrees after the completed triage."""
        _tally, differences = comparison()
        detail = "\n".join(
            f"{row['fixture']} {row['item']}: expected {row['expected']}, "
            f"actual {row['actual']} — {row['why']}"
            for row in differences)
        self.assertEqual(differences, [], detail)


if __name__ == "__main__":
    unittest.main()
