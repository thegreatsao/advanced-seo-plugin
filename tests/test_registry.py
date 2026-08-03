"""The registry is the audit's contract, so these tests guard the contract.

Most of what can go wrong here fails silently at runtime: a rule pointing at a
JSON path no script emits reports NO_DATA forever and looks like a site problem;
an item whose script was never shipped does the same. Nothing surfaces unless
something checks.
"""
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "seo-checklist")
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)

REGISTRY = os.path.join(SKILL, "resources", "config", "checklist.json")
SHAPES = os.path.join(SKILL, "resources", "references", "script-output-shapes.md")
PROFILES = os.path.join(SKILL, "resources", "config", "profiles.json")

with open(REGISTRY, encoding="utf-8") as f:
    DATA = json.load(f)
ITEMS = DATA["items"]

VALID_SOURCES = {"script", "llm", "manual", "gsc"}
VALID_SEVERITY = {"critical", "high", "medium", "low"}
VALID_EFFORT = {"low", "medium", "high"}
VALID_REQUIRES = {"offline", "fetch", "crawl", "api", "gsc"}
with open(os.path.join(SCRIPTS, "checklist_runner.py"), encoding="utf-8") as f:
    RUNNER_SRC = f.read()


class RegistryShape(unittest.TestCase):
    def test_ids_unique(self):
        ids = [i["id"] for i in ITEMS]
        dupes = {i for i in ids if ids.count(i) > 1}
        self.assertEqual(dupes, set(), f"duplicate item ids: {dupes}")

    def test_every_item_has_the_required_fields(self):
        for i in ITEMS:
            for key in ("id", "category", "category_label", "title", "severity",
                        "source", "effort", "fix"):
                self.assertIn(key, i, f"{i.get('id')} missing {key}")
            self.assertIn(i["severity"], VALID_SEVERITY, i["id"])
            self.assertIn(i["source"], VALID_SOURCES, i["id"])
            self.assertIn(i["effort"], VALID_EFFORT, i["id"])

    def test_registry_is_versioned(self):
        self.assertTrue(DATA.get("registry_version"),
                        "results cannot say which registry produced them")
        self.assertEqual(DATA.get("item_count"), len(ITEMS))

    def test_script_items_are_fully_specified(self):
        for i in ITEMS:
            if i["source"] != "script":
                continue
            chk = i.get("check")
            self.assertTrue(chk, f"{i['id']} is source=script with no check block")
            self.assertTrue(chk.get("script"), f"{i['id']} names no script")
            self.assertIn(chk.get("requires"), VALID_REQUIRES, i["id"])
            self.assertTrue(chk.get("assert"), f"{i['id']} has no assert rule")
            self.assertIn("path", chk["assert"], f"{i['id']} assert has no path")

    def test_assert_rules_use_operators_the_runner_implements(self):
        """Checked against the runner's source rather than a list kept here — a
        list in the test drifts, and an operator the runner never sees produces
        a rule that silently reports NO_DATA forever."""
        for i in ITEMS:
            chk = i.get("check") or {}
            for rule in (chk.get("assert"), chk.get("warn")):
                if not rule:
                    continue
                for key in rule:
                    self.assertIn(f'"{key}"', RUNNER_SRC,
                                  f"{i['id']} uses operator {key!r}, which "
                                  f"checklist_runner.py does not implement")

    def test_a_rule_does_more_than_name_a_path(self):
        """A rule of only {"path": ...} can never decide anything."""
        for i in ITEMS:
            rule = (i.get("check") or {}).get("assert")
            if rule:
                self.assertGreater(len(set(rule) - {"path", "missing_is"}), 0,
                                   f"{i['id']} asserts nothing about {rule['path']}")

    def test_every_referenced_script_exists(self):
        for i in ITEMS:
            script = (i.get("check") or {}).get("script")
            if script:
                self.assertTrue(os.path.exists(os.path.join(SCRIPTS, script)),
                                f"{i['id']} references missing script {script}")

    def test_every_llm_item_has_a_lens(self):
        """Without a lens an item belongs to no agent and is never answered."""
        for i in ITEMS:
            if i["source"] == "llm":
                self.assertTrue(i.get("lens"), f"{i['id']} has no lens")

    def test_manual_and_llm_items_are_never_low_effort(self):
        for i in ITEMS:
            if i["source"] == "manual":
                self.assertEqual(i["effort"], "high", i["id"])
            if i["source"] == "llm":
                self.assertIn(i["effort"], {"medium", "high"}, i["id"])


class RegistryDocs(unittest.TestCase):
    def test_every_script_the_registry_runs_is_documented(self):
        """Assert rules must be written against observed output, and the shapes
        file is where that observation is recorded."""
        with open(SHAPES, encoding="utf-8") as f:
            doc = f.read()
        scripts = {(i.get("check") or {}).get("script") for i in ITEMS} - {None}
        undocumented = sorted(s for s in scripts if f"### {s}" not in doc)
        self.assertEqual(undocumented, [], f"undocumented: {undocumented}")


class Profiles(unittest.TestCase):
    def setUp(self):
        with open(PROFILES, encoding="utf-8") as f:
            self.profiles = json.load(f)["profiles"]

    def test_default_profile_excludes_nothing(self):
        d = self.profiles["default"]
        self.assertEqual(d["exclude_categories"], [])
        self.assertEqual(d["exclude_scripts"], [])
        self.assertEqual(d["exclude_items"], [])

    def test_profiles_reference_real_categories_scripts_and_items(self):
        cats = {i["category"] for i in ITEMS}
        scripts = {(i.get("check") or {}).get("script") for i in ITEMS} - {None}
        ids = {i["id"] for i in ITEMS}
        for name, p in self.profiles.items():
            for c in p["exclude_categories"]:
                self.assertIn(c, cats, f"{name} excludes unknown category {c}")
            for s in p["exclude_scripts"]:
                self.assertIn(s, scripts, f"{name} excludes unused script {s}")
            for i in p["exclude_items"]:
                self.assertIn(i, ids, f"{name} excludes unknown item {i}")

    def test_no_profile_excludes_a_critical_item(self):
        """Profiles narrow scope; they must not be a way to hide hard failures."""
        sys.path.insert(0, SCRIPTS)
        from checklist_runner import profile_excludes
        for name, p in self.profiles.items():
            excluded = profile_excludes(ITEMS, p)
            crit = [i["id"] for i in ITEMS
                    if i["id"] in excluded and i["severity"] == "critical"]
            self.assertEqual(crit, [], f"profile {name} hides critical items {crit}")


class BundledPlaybooks(unittest.TestCase):
    """The playbooks are bundled so the plugin is self-contained. That only holds
    if the files exist, the items they claim still exist, and none of them is
    allowed to move a status on its own."""

    def setUp(self):
        path = os.path.join(SKILL, "resources", "config", "playbooks.json")
        with open(path, encoding="utf-8") as f:
            self.playbooks = json.load(f)["playbooks"]

    def test_every_playbook_file_is_present(self):
        """A self-contained plugin cannot point at a file it does not ship."""
        for name, p in self.playbooks.items():
            self.assertTrue(os.path.exists(os.path.join(SKILL, p["path"])),
                            f"{name} points at missing {p['path']}")

    def test_every_referenced_item_exists(self):
        ids = {i["id"] for i in ITEMS}
        for name, p in self.playbooks.items():
            for item_id in p["items"]:
                self.assertIn(item_id, ids, f"{name} references unknown {item_id}")

    def test_every_playbook_states_what_it_cannot_decide(self):
        """A playbook that does not say where it stops will be read as a verdict."""
        for name, p in self.playbooks.items():
            self.assertTrue(p.get("leaves_status"), f"{name} has no leaves_status")

    def test_documented_in_the_skill(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            doc = f.read()
        for name, p in self.playbooks.items():
            self.assertIn(os.path.basename(p["path"]), doc,
                          f"{name} is configured but never documented")

    def test_nothing_instructs_the_reader_to_install_another_plugin(self):
        """Self-containment is the point: the audit must not tell anyone to go
        fetch a skill from somewhere else. Attribution in CREDITS.md and in the
        playbook headers is provenance, not a dependency, and is exempt."""
        offenders = []
        for base, _dirs, files in os.walk(SKILL):
            for f in files:
                if not f.endswith(".md"):
                    continue
                path = os.path.join(base, f)
                with open(path, encoding="utf-8") as fh:
                    for n, line in enumerate(fh, 1):
                        if line.lstrip().startswith(("<!--", "Bundled playbook")):
                            continue
                        if "skill is installed" in line or "install the" in line.lower():
                            offenders.append(f"{os.path.relpath(path, SKILL)}:{n}")
        self.assertEqual(offenders, [], f"external dependency implied at {offenders}")

    def test_borrowed_material_is_attributed(self):
        """Two playbooks are adapted from MIT-licensed work; the notice has to
        travel with them."""
        credits = os.path.join(ROOT, "CREDITS.md")
        self.assertTrue(os.path.exists(credits), "CREDITS.md is missing")
        with open(credits, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("MIT License", text)
        for name in ("competitor-research", "client-report-structure"):
            self.assertIn(name, text, f"{name} is not attributed in CREDITS.md")


class GeneratorIsInStep(unittest.TestCase):
    def test_registry_matches_its_generator(self):
        r = subprocess.run([sys.executable,
                            os.path.join(SKILL, "tools", "build_checklist.py"),
                            "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class NoAssertionThatCanNeverFire(unittest.TestCase):
    """`none_matching` passes when nothing matches, so a pattern aimed at wording
    its script cannot emit reports PASS for every site, silently, forever.

    Fifteen of the registry's twenty-one pattern assertions were in that state:
    three asked an accessibility checker about font sizes it never measures, two
    asked a mobile checker about interstitials it never looks for, one wanted
    "lazy" before "LCP" in a message that says "LCP image is lazy-loaded", and one
    — a `critical` item about blocking CSS and JS in robots.txt — was matching its
    own script's module docstring.
    """

    def test_every_pattern_assertion_can_match_its_script(self):
        sys.path.insert(0, os.path.join(SKILL, "tools"))
        from audit_assertions import audit
        dead = audit(REGISTRY)
        detail = "; ".join(f"{d['id']} {d['script']} {d['op']}={d['pattern']!r}"
                           for d in dead)
        self.assertEqual(dead, [], f"assertions that always pass: {detail}")

    def test_the_audit_notices_a_pattern_nobody_can_emit(self):
        """The guard has to be able to fail, or it is decoration. A registry whose
        assertion looks for a string no script contains must be reported."""
        sys.path.insert(0, os.path.join(SKILL, "tools"))
        from audit_assertions import audit
        import tempfile
        fake = dict(DATA, items=[{
            "id": "ZZ-001", "category": "content", "category_label": "C",
            "title": "t", "severity": "low", "source": "script", "effort": "low",
            "fix": "", "check": {"script": "parse_html.py", "args": [],
                                 "requires": "offline",
                                 "assert": {"path": "issues",
                                            "none_matching": "quantum entanglement"}}}])
        path = os.path.join(tempfile.mkdtemp(), "fake.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fake, f)
        self.assertEqual([d["id"] for d in audit(path)], ["ZZ-001"])

    def test_remediation_text_does_not_count_as_something_the_script_emits(self):
        """The gap that let KW-072 and KW-073 through this guard for a whole tier:
        their pattern matched a `fix` string, so the tool saw a live assertion."""
        sys.path.insert(0, os.path.join(SKILL, "tools"))
        from audit_assertions import emittable_strings
        strings = emittable_strings("article_seo.py")
        advice = [t for t in strings if "primary keyword" in t.lower()]
        self.assertEqual(advice, [], f"remediation text counted as output: {advice[:1]}")
        self.assertTrue(any("No H1 tag detected" in t for t in strings),
                        "findings must still count")

    def test_page_derived_paths_are_exempt_and_few(self):
        """A pattern over a value that comes from the page is checking the site,
        not the script's wording — but the exemption list is a way to silence the
        guard, so it stays short and explicit."""
        sys.path.insert(0, os.path.join(SKILL, "tools"))
        from audit_assertions import PAGE_DERIVED
        self.assertLessEqual(len(PAGE_DERIVED), 5)
        for script, path in PAGE_DERIVED:
            self.assertTrue(os.path.exists(os.path.join(SCRIPTS, script)), script)


class GradedRowsCarryWhatTheReportRanksOn(unittest.TestCase):
    """The report claims its fix list is ranked by severity against effort. That
    was false for every run: `grade()` did not copy `effort` onto the row, so
    priority_of fell back to "medium" for all 214 items and the ranking collapsed
    to severity alone. The effort column printed "?" and nobody read it as a bug."""

    def test_effort_survives_grading(self):
        from checklist_runner import grade
        item = [{"id": "X-001", "plerdy_ref": 1, "category": "content",
                 "category_label": "C", "title": "t", "severity": "high",
                 "source": "manual", "effort": "low", "fix": ""}]
        self.assertEqual(grade(item, {}, {}, {}, False)[0]["effort"], "low")

    def test_effort_changes_the_ranking(self):
        """If it did not, carrying the field would be decoration."""
        sys.path.insert(0, SCRIPTS)
        from checklist_report import priority_of
        cheap = priority_of({"severity": "high", "effort": "low"})
        dear = priority_of({"severity": "high", "effort": "high"})
        self.assertGreater(cheap, dear)

    def test_every_registry_item_declares_an_effort(self):
        for i in ITEMS:
            self.assertIn(i.get("effort"), VALID_EFFORT, i["id"])


if __name__ == "__main__":
    unittest.main()
