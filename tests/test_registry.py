"""The registry is the audit's contract, so these tests guard the contract.

Most of what can go wrong here fails silently at runtime: a rule pointing at a
JSON path no script emits reports NO_DATA forever and looks like a site problem;
an item whose script was never shipped does the same. Nothing surfaces unless
something checks.
"""
import ast
import importlib.util
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


class DocsPointAtThingsThatExist(unittest.TestCase):
    """Cross-references between documents rot silently.

    The known-issues list is only useful if the documents that raise a caveat point
    at it, and a relative link that stops resolving is invisible until a reader
    follows it. Both are the documentation form of the failure this whole suite
    guards: something that reads as true and is not."""

    DOCS = ("README.md", "CHANGELOG.md", "CREDITS.md", "KNOWN-ISSUES.md",
            os.path.join("skills", "seo-checklist", "SKILL.md"))

    def _read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return f.read()

    def test_every_relative_markdown_link_resolves(self):
        broken = []
        for rel in self.DOCS:
            base = os.path.dirname(os.path.join(ROOT, rel))
            for target in re.findall(r"\]\(([^)#:]+\.md)[^)]*\)", self._read(rel)):
                if not os.path.exists(os.path.join(base, target)):
                    broken.append(f"{rel} -> {target}")
        self.assertEqual(broken, [], f"dead links: {broken}")

    def test_the_caveats_point_at_the_known_issues_list(self):
        """Whoever fixes one of these must find every place that documents it. The
        set of files naming KNOWN-ISSUES.md is that list."""
        self.assertTrue(os.path.exists(os.path.join(ROOT, "KNOWN-ISSUES.md")))
        for rel in ("README.md", "CHANGELOG.md",
                    os.path.join("skills", "seo-checklist", "SKILL.md")):
            self.assertIn("KNOWN-ISSUES.md", self._read(rel),
                          f"{rel} raises caveats but does not point at the list")

    def test_no_document_still_carries_the_retracted_sample_caveat(self):
        """`--sample` spreads its picks across the sitemap as of 0.3.0. The caveat
        that said otherwise was correct when written and is now the wrong thing to
        tell a reader — a stale warning costs the same trust as a missing one."""
        for rel in self.DOCS + ("skills/seo-checklist/scripts/checklist_runner.py",):
            text = self._read(rel)
            self.assertNotIn("document order, not a", text, f"{rel} is out of date")
            self.assertNotIn("is not a sample", text, f"{rel} is out of date")


class VersionAndChangelog(unittest.TestCase):
    """A changelog nobody is forced to update is a changelog that lies. The failure
    mode is always the same one: the version moves and the entry does not."""

    def setUp(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as f:
            self.manifest = json.load(f)
        with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
            self.changelog = f.read()

    def test_the_manifest_version_has_a_changelog_entry(self):
        version = self.manifest["version"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        headings = re.findall(r"^## (\d+\.\d+\.\d+)", self.changelog, re.M)
        self.assertTrue(headings, "CHANGELOG.md has no version headings")
        self.assertEqual(headings[0], version,
                         f"plugin.json says {version}, newest CHANGELOG entry is "
                         f"{headings[0]}")

    def test_the_registry_version_in_the_newest_entry_is_the_shipped_one(self):
        """The entry states which contract it shipped. If the registry is
        regenerated without a changelog line, that claim silently goes stale."""
        newest = self.changelog.split("\n## ")[1]
        self.assertIn(DATA["registry_version"], newest,
                      f"registry is {DATA['registry_version']}; the newest "
                      f"CHANGELOG entry does not mention it")

    def test_pyproject_states_the_same_version_as_the_manifest(self):
        """Two files naming a version is one more chance for them to disagree, and
        the manifest is the one a plugin host reads."""
        self.assertEqual(pyproject_value(r'^version = "([^"]+)"'),
                         self.manifest["version"])

    def test_the_readme_names_the_shipped_version(self):
        """It said 0.5.0 while 0.7.0 shipped — two releases behind, in the first
        paragraph a reader sees, because nothing checked. The version in the manifest
        is a fact about the code; the one in the README is a promise to the reader,
        and only one of them was being kept."""
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            stated = re.search(r"^Version (\d+\.\d+\.\d+)", f.read(), re.M)
        self.assertTrue(stated, "README.md no longer states a version")
        self.assertEqual(stated.group(1), self.manifest["version"])


def pyproject_value(pattern: str) -> str:
    """One value out of pyproject.toml, by regex.

    Not `tomllib`: that arrived in 3.11 and the floor this very file asserts is
    3.10, so parsing the file properly would make the test unrunnable on the
    version it exists to defend.
    """
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        found = re.search(pattern, f.read(), re.M)
    assert found, f"pyproject.toml has no {pattern}"
    return found.group(1)


class TheDeclaredPythonFloorIsExercised(unittest.TestCase):
    """A `requires-python` nothing runs is a guess with a colon in it.

    The floor is real and the failure it prevents is ugly: `duplicate_content.py`,
    `link_profile.py` and `pagespeed.py` annotate with PEP 604 unions without
    `from __future__ import annotations`, so on 3.9 the annotation is evaluated at
    import and raises `TypeError: unsupported operand type(s) for |`. That happens
    before a single check runs, and the message says nothing about SEO or about a
    Python version being too old.
    """

    def matrix_versions(self):
        with open(os.path.join(ROOT, ".github", "workflows", "ci.yml"),
                  encoding="utf-8") as f:
            line = re.search(r"python-version: \[([^\]]+)\]", f.read())
        self.assertTrue(line, "the CI matrix no longer lists python versions")
        return [v.strip().strip('"') for v in line.group(1).split(",")]

    def test_ci_runs_the_lowest_version_the_project_claims_to_support(self):
        floor = pyproject_value(r'requires-python = ">=([\d.]+)"')
        versions = sorted(self.matrix_versions(),
                          key=lambda v: tuple(int(p) for p in v.split(".")))
        self.assertEqual(versions[0], floor,
                         f"pyproject.toml claims >={floor} and CI's lowest is "
                         f"{versions[0]}; one of the two is wrong")

    def test_ruff_targets_the_same_floor(self):
        floor = pyproject_value(r'requires-python = ">=([\d.]+)"')
        target = pyproject_value(r'target-version = "py(\d+)"')
        self.assertEqual(target, floor.replace(".", ""),
                         "ruff would suggest rewrites for a version this project "
                         "does not require, or miss ones it does")

    def test_the_floor_is_not_lower_than_the_syntax_in_the_tree(self):
        """Measured from the source rather than trusted, because the way this claim
        breaks is somebody using a newer feature in a script nobody re-reads."""
        floor = tuple(int(p) for p in
                      pyproject_value(r'requires-python = ">=([\d.]+)"').split("."))
        offenders = []
        for folder in (SCRIPTS, os.path.join(SKILL, "tools"),
                       os.path.dirname(os.path.abspath(__file__))):
            for name in sorted(os.listdir(folder)):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as f:
                    source = f.read()
                tree = ast.parse(source, path)
                future = any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
                             and any(a.name == "annotations" for a in n.names)
                             for n in tree.body)
                for node in ast.walk(tree):
                    # 3.10: `X | Y` evaluated at runtime, which an annotation is
                    # unless the __future__ import postpones it.
                    annotation = None
                    if isinstance(node, (ast.AnnAssign, ast.arg)):
                        annotation = getattr(node, "annotation", None)
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        annotation = node.returns
                    if annotation is not None and not future:
                        for sub in ast.walk(annotation):
                            if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr):
                                if floor < (3, 10):
                                    offenders.append(f"{name}:{node.lineno} PEP 604")
                                break
                    # 3.10: zip(strict=), and the match statement.
                    if isinstance(node, ast.Match) and floor < (3, 10):
                        offenders.append(f"{name}:{node.lineno} match")
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == "zip" and floor < (3, 10)
                            and any(k.arg == "strict" for k in node.keywords)):
                        offenders.append(f"{name}:{node.lineno} zip(strict=)")
        self.assertEqual(offenders, [], "these need a higher floor than declared")


class ChecklistProvenance(unittest.TestCase):
    """The 200 borrowed titles have to say where they came from, in the file that
    holds them. CREDITS.md is the licence record; this is the one that survives the
    file being copied out on its own."""

    def setUp(self):
        self.path = os.path.join(SKILL, "resources", "config", "plerdy-titles.json")
        with open(self.path, encoding="utf-8") as f:
            self.raw = json.load(f)

    def test_the_titles_file_names_its_source(self):
        src = self.raw.get("_source")
        self.assertIsInstance(src, dict, "plerdy-titles.json has no _source block")
        self.assertIn("plerdy.com/seo-checklist", src.get("url", ""))
        self.assertRegex(src.get("retrieved", ""), r"^\d{4}-\d{2}-\d{2}$")

    def test_metadata_keys_do_not_reach_the_generator(self):
        """`load_titles` used to call int() on every key, so any note added to this
        file would have crashed the build rather than documenting it."""
        sys.path.insert(0, os.path.join(SKILL, "tools"))
        import build_checklist
        titles = build_checklist.load_titles()
        self.assertEqual(len(titles), 200)
        self.assertTrue(all(isinstance(k, int) for k in titles))
        self.assertEqual(titles[1], "Ensure URL Is Indexed")

    def test_every_numbered_title_is_referenced_by_exactly_one_item(self):
        """plerdy_ref is the trace back to the source line, so the mapping has to be
        a bijection over 1..200 — and the 14 items this plugin added must not claim
        a reference they do not have."""
        numbered = sorted(int(k) for k in self.raw if k.lstrip("-").isdigit())
        refs = [i["plerdy_ref"] for i in ITEMS if i["plerdy_ref"] is not None]
        self.assertEqual(numbered, list(range(1, 201)))
        self.assertEqual(sorted(refs), numbered)
        added = [i["id"] for i in ITEMS if i["plerdy_ref"] is None]
        self.assertEqual(len(added), 14, f"unexpected unreferenced items: {added}")


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


class ProbeCoversWhatTheRegistryReads(unittest.TestCase):
    """`tools/probe_shapes.py` is how the asserted paths get checked against real
    output. It used to hold its own list of scripts, and an unchecked copy of a
    list is a list that is wrong: it named seven scripts that no longer exist and
    missed three the registry reads — `cwv_metrics.py`, `rendered_audit.py` and
    `gsc_links_csv.py`, which between them decide eleven items. The tool for
    finding drift had drifted, in both directions, and nothing said so.

    Now the jobs are derived from the registry, and these tests are what keeps that
    true rather than merely true today."""

    def jobs(self, ctx):
        spec = importlib.util.spec_from_file_location(
            "probe_shapes", os.path.join(SKILL, "tools", "probe_shapes.py"))
        # Not imported: importing it *runs* the probe, against the network. Only the
        # one definition is taken, compiled out of the shipped source, which keeps
        # this test offline while still reading the code that ships.
        with open(spec.origin, encoding="utf-8") as f:
            source = f.read()
        start = source.index("def registry_jobs(")
        end = source.index("\nJOBS = registry_jobs")
        namespace = {"json": json, "os": os, "sys": sys,
                     "REGISTRY": os.path.join(SKILL, "resources", "config",
                                              "checklist.json")}
        exec(compile(source[start:end], spec.origin, "exec"), namespace)
        return namespace["registry_jobs"](ctx)

    def registry_scripts(self, placeholders_available):
        with open(os.path.join(SKILL, "resources", "config", "checklist.json"),
                  encoding="utf-8") as f:
            items = json.load(f)["items"]
        out = set()
        for item in items:
            check = item.get("check") or {}
            if not check.get("script"):
                continue
            needed = {a[1:-1] for a in check.get("args") or []
                      if isinstance(a, str) and a.startswith("{") and a.endswith("}")}
            if needed <= placeholders_available:
                out.add(check["script"])
        return out

    FULL_CTX = {"url": "https://example.com/", "html": "/tmp/p.html",
                "gsc_property": "sc-domain:example.com",
                "gsc_credentials": "/tmp/k.json", "cwv_json": "/tmp/cwv.json",
                "rendered_json": "/tmp/r.json", "links_csv": "/tmp/l.csv",
                "indexnow_key": "k"}

    def test_every_script_the_registry_names_is_probed(self):
        probed = {script for script, _ in self.jobs(self.FULL_CTX)}
        expected = self.registry_scripts(set(self.FULL_CTX))
        self.assertEqual(expected - probed, set())

    def test_every_probed_script_exists_on_disk(self):
        missing = sorted({script for script, _ in self.jobs(self.FULL_CTX)
                          if not os.path.exists(os.path.join(SKILL, "scripts", script))})
        self.assertEqual(missing, [], "the probe would report these as __missing__ "
                                      "and nothing else would notice")

    def test_a_job_whose_input_is_absent_is_dropped_not_probed_with_a_placeholder(self):
        """The old list hard-coded a `[URL]` argv per script, so a check needing a
        credential path had no way to be skipped — it was simply not listed, which
        is why three of them never were."""
        jobs = self.jobs({"url": "https://example.com/"})
        for script, args in jobs:
            for arg in args:
                self.assertFalse(arg.startswith("{") and arg.endswith("}"),
                                 f"{script} would be probed with {arg} as a literal")
        scripts = {script for script, _ in jobs}
        self.assertNotIn("gsc_checker.py", scripts)
        self.assertNotIn("cwv_metrics.py", scripts)

    def test_the_jobs_are_deduplicated_the_way_the_runner_deduplicates(self):
        """17 items read one `parse_html.py` run. A probe that ran it 17 times would
        be reporting on a different workload than the one it is meant to describe."""
        jobs = self.jobs(self.FULL_CTX)
        self.assertEqual(len(jobs), len({(s, tuple(a)) for s, a in jobs}))
        self.assertEqual(sum(1 for s, _ in jobs if s == "parse_html.py"), 1)


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
        for script, _path in PAGE_DERIVED:
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
