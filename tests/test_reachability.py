"""A rule that cannot report FAIL cannot find the defect its title names.

`KW-076` *Use the Primary Keyword in Body Copy* was in that state for years:
`article_seo.py` wrote `target_keyword` only when it already held something, so the
assertion `truthy` read a value that was true whenever it existed. PASS or NO_DATA on
every site ever audited, and no gate saw it — `audit_assertions.py` audits patterns,
severities and unseen paths, and this is none of those.

Some rules are meant to be unable to fail. `TE-179` prices domain age with a warn band
that is its assertion's exact complement; `TE-178` asserts a field its script
deliberately never writes. In all three cases the field is absent, or safe, exactly when
the answer would have been bad, so **the code cannot say which were meant** — intent is
declared in `CANNOT_FAIL` in `build_checklist.py` and lands on the item as
`check.cannot_fail`.

What these tests guard is that the declaration cannot become an exemption list: the
mechanism is re-derived from the script's source on every run, and disagreement in
either direction, or agreement on the wrong mechanism, fails the build.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "seo-checklist")
TOOLS = os.path.join(SKILL, "tools")
sys.path.insert(0, TOOLS)

import audit_reachability as R  # noqa: E402
from audit_assertions import PATH_EXEMPT, SCRIPTS  # noqa: E402

REGISTRY = os.path.join(SKILL, "resources", "config", "checklist.json")
EXPECTATIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "fixtures", "expectations.json")

with open(REGISTRY, encoding="utf-8") as f:
    DATA = json.load(f)


def a_registry(rule, script="probe.py", warn=None, cannot_fail=None, item_id="ZZ-001"):
    """One-item registry, for asking the tool about a shape rather than a site."""
    check = {"script": script, "args": [], "requires": "fetch", "assert": rule}
    if warn:
        check["warn"] = warn
    if cannot_fail:
        check["cannot_fail"] = cannot_fail
    return dict(DATA, items=[{
        "id": item_id, "category": "content", "category_label": "C", "title": "t",
        "severity": "low", "source": "script", "effort": "low", "fix": "",
        "check": check}])


class Tree:
    """A registry, a script and a shapes reference in a directory of their own.

    The tool reads scripts from a directory it is given rather than from a module
    constant, which is what lets these tests hand it a shape instead of describing
    one — and what let the `guarded_by_assertion` detector be run against the real
    `article_seo.py` at `v0.44.0`, where it found the defect at line 705.
    """

    def __init__(self, registry, source, shapes="### `probe.py`\n\n`value` — a value\n"):
        self.dir = tempfile.mkdtemp()
        self.scripts = os.path.join(self.dir, "scripts")
        os.makedirs(self.scripts, exist_ok=True)
        self.registry = os.path.join(self.dir, "registry.json")
        self.shapes = os.path.join(self.dir, "shapes.md")
        with open(self.registry, "w", encoding="utf-8") as f:
            json.dump(registry, f)
        with open(os.path.join(self.scripts, "probe.py"), "w", encoding="utf-8") as f:
            f.write(source)
        with open(self.shapes, "w", encoding="utf-8") as f:
            f.write(shapes)

    def proved(self):
        return R.proofs(self.registry, self.shapes, self.scripts)

    def findings(self):
        return R.audit(self.registry, self.shapes, self.scripts)


class TheRegistryAgreesWithItsOwnCode(unittest.TestCase):
    """The gate. Everything below is about whether it can fail."""

    def test_no_rule_is_unable_to_fail_without_saying_so(self):
        findings = R.audit(REGISTRY)
        detail = "; ".join(f"{f['id']} [{f['kind']}] {f['detail']}" for f in findings)
        self.assertEqual(findings, [], f"reachability disagreements: {detail}")

    def test_every_declaration_names_a_mechanism_the_tool_can_prove(self):
        for item in DATA["items"]:
            declared = (item.get("check") or {}).get("cannot_fail")
            if declared:
                self.assertIn(declared["mechanism"], R.MECHANISMS, item["id"])
                self.assertTrue(declared.get("why", "").strip(), item["id"])


class NothingTheFixturesHaveFailedIsCalledUnfailable(unittest.TestCase):
    """The calibration, and it has already earned its place.

    A fourth detector claimed a rule could not fail when every write of its field was
    a literal that passed. It reported `SE-115`, `GO-132`, `TE-174` and `TE-175`, and
    all four have a declared FAIL in the oracle that a real run matched — the
    registry was right and the detector was wrong four times out of four, for four
    different reasons. It was removed rather than exempted. This test is what caught
    it, so it stays whatever the detectors become.
    """

    def failing_items(self):
        with open(EXPECTATIONS, encoding="utf-8") as f:
            fixtures = json.load(f)["fixtures"]
        return {item_id for origin in fixtures.values()
                for item_id, row in origin.items() if row["expect"] == "FAIL"}

    def test_the_oracle_has_items_that_fail(self):
        """Otherwise the test below passes by having nothing to compare."""
        self.assertGreater(len(self.failing_items()), 30)

    def test_no_item_the_oracle_expects_to_fail_is_proved_unable_to(self):
        proved = set(R.proofs(REGISTRY)) & self.failing_items()
        self.assertEqual(sorted(proved), [], "these fail on a fixture and the tool "
                                             "says they cannot: " + ", ".join(proved))


class TheDetectorsFindTheShapesTheyExistFor(unittest.TestCase):

    def test_a_field_emitted_only_when_it_would_pass(self):
        """KW-076 verbatim: the value is written exactly when it would pass.

        Run against the real `article_seo.py` at `v0.44.0` during implementation, it
        reported line 705 — the defect at the commit that shipped it. That check
        cannot live here, because CI checks out one commit with no history.
        """
        tree = Tree(a_registry({"path": "value", "truthy": True}),
                    "def main(args):\n"
                    "    result = {}\n"
                    "    value = compute()\n"
                    "    if value:\n"
                    "        result['value'] = value\n"
                    "    return result\n")
        self.assertEqual(tree.proved()["ZZ-001"]["mechanism"], "guarded_by_assertion")

    def test_a_warn_band_that_is_the_assertion_s_complement(self):
        tree = Tree(a_registry({"path": "value", "gte": 90},
                               warn={"path": "value", "lt": 90}),
                    "def main():\n    return {'value': measure()}\n")
        self.assertEqual(tree.proved()["ZZ-001"]["mechanism"], "warn_complement")

    def test_a_field_no_code_writes(self):
        tree = Tree(a_registry({"path": "absent", "len_eq": 0}),
                    "def main():\n    return {'value': 1}\n")
        self.assertEqual(tree.proved()["ZZ-001"]["mechanism"], "path_never_emitted")


class TheDetectorsRefuseWhatTheyCannotSee(unittest.TestCase):
    """Every refusal here is a wrong answer the tool gave before it had one."""

    def test_a_guard_about_the_input_is_not_a_guard_about_the_value(self):
        """The shape KW-076 was repaired into. `in_body` can still be False, so the
        item can still fail, and a detector that could not tell these apart would
        have called the repair a defect."""
        tree = Tree(a_registry({"path": "value", "truthy": True}),
                    "def main(args):\n"
                    "    result = {}\n"
                    "    if args.keyword is not None:\n"
                    "        result['value'] = occurrences(args.keyword) > 0\n"
                    "    return result\n")
        self.assertEqual(tree.proved(), {})

    def test_a_counter_started_at_a_passing_value_is_not_a_constant(self):
        """`unminified_count` is initialised to 0 and counted up with `+=`; the site
        scan sees the initialiser and not the increment, so it stands down."""
        tree = Tree(a_registry({"path": "value", "truthy": True}),
                    "def main():\n"
                    "    result = {'value': 0}\n"
                    "    for x in things():\n"
                    "        if x:\n"
                    "            result['value'] += 1\n"
                    "    return result\n")
        self.assertEqual(tree.proved(), {})

    def test_a_container_filled_later_is_not_a_constant(self):
        """`duplicates` is `[]` at line 46 and appended to at 73."""
        tree = Tree(a_registry({"path": "value", "truthy": True}),
                    "def main():\n"
                    "    result = {}\n"
                    "    if found():\n"
                    "        result['value'] = []\n"
                    "    result['value'].append(1)\n"
                    "    return result\n")
        self.assertEqual(tree.proved(), {})

    def test_a_field_the_probe_has_seen_is_never_called_unwritten(self):
        """A key written through a helper is invisible to the scan and perfectly
        visible to a probe. `safe_browsing.threats` is absent from a keyless probe
        and written at `domain_safety_check.py:106`; neither half alone is a proof."""
        tree = Tree(a_registry({"path": "value", "len_eq": 0}),
                    "def main():\n    return build_the_result()\n")
        self.assertEqual(tree.proved(), {})

    def test_a_key_the_script_mentions_is_never_called_unwritten(self):
        tree = Tree(a_registry({"path": "absent", "len_eq": 0}),
                    "def main():\n"
                    "    out = {}\n"
                    "    out.update({k: 1 for k in ['absent']})\n"
                    "    return out\n")
        self.assertEqual(tree.proved(), {})


class ADeclarationCannotOutliveItsReason(unittest.TestCase):
    """Three directions, because an exemption list only ever fails in one."""

    UNFAILABLE = ("def main(args):\n"
                  "    result = {}\n"
                  "    value = compute()\n"
                  "    if value:\n"
                  "        result['value'] = value\n"
                  "    return result\n")
    FAILABLE = "def main():\n    return {'value': measure() > 0}\n"

    def test_proved_and_undeclared_is_reported(self):
        tree = Tree(a_registry({"path": "value", "truthy": True}), self.UNFAILABLE)
        self.assertEqual([(f["id"], f["kind"]) for f in tree.findings()],
                         [("ZZ-001", "undeclared")])

    def test_declared_and_no_longer_provable_is_reported(self):
        tree = Tree(a_registry({"path": "value", "truthy": True},
                               cannot_fail={"mechanism": "guarded_by_assertion",
                                            "why": "it was, once"}),
                    self.FAILABLE)
        self.assertEqual([(f["id"], f["kind"]) for f in tree.findings()],
                         [("ZZ-001", "stale")])

    def test_a_declaration_naming_the_wrong_mechanism_is_reported(self):
        """The one an exemption list cannot catch: still unable to fail, and the
        recorded reason is not why. `neighbors.suspicious` was exempted as needing a
        Safe Browsing key for three releases while its script wanted a reverse-IP
        service it has never had."""
        tree = Tree(a_registry({"path": "value", "truthy": True},
                               cannot_fail={"mechanism": "warn_complement",
                                            "why": "the wrong reason"}),
                    self.UNFAILABLE)
        self.assertEqual([(f["id"], f["kind"]) for f in tree.findings()],
                         [("ZZ-001", "wrong mechanism")])

    def test_a_mechanism_outside_the_vocabulary_is_reported(self):
        tree = Tree(a_registry({"path": "value", "truthy": True},
                               cannot_fail={"mechanism": "because I said so",
                                            "why": "…"}),
                    self.UNFAILABLE)
        self.assertEqual([f["kind"] for f in tree.findings()], ["unknown mechanism"])

    def test_a_declaration_without_a_reason_is_reported(self):
        tree = Tree(a_registry({"path": "value", "truthy": True},
                               cannot_fail={"mechanism": "guarded_by_assertion",
                                            "why": "  "}),
                    self.UNFAILABLE)
        self.assertEqual([f["kind"] for f in tree.findings()], ["unexplained"])


class TheOtherExemptionListStaysHonest(unittest.TestCase):
    """`PATH_EXEMPT` says "absent from the probe because the credential was".

    That is a claim about a field the script writes when it can. It was false for
    `neighbors.suspicious` from 0.42 to 0.45 — nothing writes that field under any
    credential — and the entry read as true the whole time because nothing checked
    the half of it that was about code.
    """

    def test_every_exempt_path_is_one_its_script_actually_writes(self):
        wrong = []
        for (script, path), reason in PATH_EXEMPT.items():
            self.assertTrue(os.path.exists(os.path.join(SCRIPTS, script)), script)
            if not R.mentions_key(script, path.split(".")[-1]):
                wrong.append(f"{script} {path} — exempted as {reason!r}, and no code "
                             f"in it writes that field at all")
        self.assertEqual(wrong, [], "\n".join(wrong))


if __name__ == "__main__":
    unittest.main()
