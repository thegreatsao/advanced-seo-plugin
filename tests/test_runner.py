"""Tests for the parts of the runner where a wrong answer is invisible.

The recurring hazard in this codebase is not a crash, it is a confident verdict
built on absent data. These tests exist mostly to pin down the difference
between "failed", "could not be decided" and "out of scope", because every one
of those collapses into a plausible-looking number if it goes wrong.
"""
import builtins
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "seo-checklist", "scripts")
sys.path.insert(0, SCRIPTS)

from checklist_runner import (  # noqa: E402
    ANCHOR_RE, FAIL, FAILURE_LABEL, GSC_UNAVAILABLE, LLM_PENDING, MANUAL, NA,
    NO_DATA, PASS, WARN, aggregate_pages, audit_target, build_plan,
    choose_profile, diff_runs, evaluate, grade, is_page_level,
    looks_like_a_page, page_guard, profile_excludes, redact, registrable_domain,
    THIN_ENTRY_WORDS, history_path, load_public_suffixes, previous_run,
    psl_snapshot_date, psl_staleness, resolve, run_script,
    run_stamp, run_time, score, suffix_label_count, unreachable_skips,
    visible_words,
)
from cwv_metrics import read as cwv_read  # noqa: E402
from detect_profile import detect  # noqa: E402


class Resolve(unittest.TestCase):
    def test_walks_dicts_and_list_indices(self):
        data = {"a": {"b": [{"c": 7}]}}
        self.assertEqual(resolve(data, "a.b.0.c"), 7)

    def test_absent_key_is_distinct_from_none(self):
        from checklist_runner import _MISSING
        self.assertIs(resolve({"a": None}, "a"), None)
        self.assertIs(resolve({"a": None}, "b"), _MISSING)


class Evaluate(unittest.TestCase):
    def test_scalar_comparisons(self):
        self.assertEqual(evaluate({"path": "n", "eq": 3}, {"n": 3})[0], True)
        self.assertEqual(evaluate({"path": "n", "lte": 3}, {"n": 4})[0], False)
        self.assertEqual(evaluate({"path": "n", "gte": 3}, {"n": 3})[0], True)

    def test_absent_field_is_undecided_not_failed(self):
        """The whole design rests on this: silence is not a failure."""
        passed, why = evaluate({"path": "nope", "eq": 1}, {"a": 1})
        self.assertIsNone(passed)
        self.assertIn("nope", why)

    def test_missing_is_makes_absence_the_answer(self):
        self.assertEqual(evaluate({"path": "meta_keywords", "falsy": True,
                                   "missing_is": "pass"}, {})[0], True)
        self.assertEqual(evaluate({"path": "x", "truthy": True,
                                   "missing_is": "fail"}, {})[0], False)

    def test_none_severity_is_case_insensitive(self):
        """gsc_checker.py capitalises severity; a raw comparison would never fire."""
        data = {"issues": [{"severity": "High", "message": "m"}]}
        self.assertEqual(
            evaluate({"path": "issues", "none_severity": ["high"]}, data)[0], False)

    def test_none_severity_missing_array_is_undecided(self):
        self.assertIsNone(
            evaluate({"path": "issues", "none_severity": ["high"]}, {})[0])

    def test_none_matching_scans_nested_structures(self):
        data = {"meta_robots": "index, follow"}
        self.assertEqual(
            evaluate({"path": "meta_robots", "none_matching": "noindex"}, data)[0], True)


class ValueMap(unittest.TestCase):
    """The structured replacement for matching prose. Its whole point is the
    failure mode: an unlisted value is undecided, where a pattern that matched
    nothing was a pass."""

    RULE = {"path": "rows", "field": "verdict",
            "value_map": {"self_canonical": "pass", "cross_host": "fail"}}

    def test_all_mapped_to_pass(self):
        ok, why = evaluate(self.RULE, {"rows": [{"verdict": "self_canonical"}] * 3})
        self.assertTrue(ok)
        self.assertIn("3", why)

    def test_one_mapped_to_fail_decides_the_item(self):
        ok, why = evaluate(self.RULE, {"rows": [{"verdict": "self_canonical"},
                                                {"verdict": "cross_host"}]})
        self.assertFalse(ok)
        self.assertIn("cross_host", why)

    def test_an_unmapped_value_is_undecided_not_a_pass(self):
        """`unknown` is what canonical_checker emits when it could not tell. A
        pattern would have skipped over it and passed."""
        ok, why = evaluate(self.RULE, {"rows": [{"verdict": "unknown"}]})
        self.assertIsNone(ok)
        self.assertIn("unknown", why)

    def test_a_new_vocabulary_word_is_undecided(self):
        """The reason to enumerate: a value the script starts emitting later, that
        nobody mapped, must not be read as clean."""
        self.assertIsNone(evaluate(self.RULE, {"rows": [{"verdict": "brand_new"}]})[0])

    def test_a_failure_outranks_an_undecided_row(self):
        ok, _ = evaluate(self.RULE, {"rows": [{"verdict": "unknown"},
                                              {"verdict": "cross_host"}]})
        self.assertFalse(ok, "a decided failure must not be softened into NO_DATA")

    def test_a_missing_field_is_undecided(self):
        self.assertIsNone(evaluate(self.RULE, {"rows": [{"url": "x"}]})[0])

    def test_nothing_to_judge_is_undecided(self):
        self.assertIsNone(evaluate(self.RULE, {"rows": []})[0])

    def test_the_path_itself_missing_is_undecided(self):
        self.assertIsNone(evaluate(self.RULE, {})[0])

    def test_it_works_on_a_scalar_too(self):
        rule = {"path": "state", "value_map": {"ok": "pass", "bad": "fail"}}
        self.assertTrue(evaluate(rule, {"state": "ok"})[0])
        self.assertFalse(evaluate(rule, {"state": "bad"})[0])
        self.assertIsNone(evaluate(rule, {"state": "other"})[0])


class Scoring(unittest.TestCase):
    def rows(self, *statuses):
        return [{"id": f"X-{n:03d}", "category": "content",
                 "category_label": "Content", "severity": "high",
                 "status": s, "effort": "low"}
                for n, s in enumerate(statuses)]

    def test_na_leaves_both_metrics_alone(self):
        """'We did not crawl' must not read as 'the site failed'."""
        with_na = score(self.rows(PASS, FAIL, NA, NA))
        without = score(self.rows(PASS, FAIL))
        self.assertEqual(with_na["seo_score"], without["seo_score"])
        self.assertEqual(with_na["coverage_pct"], without["coverage_pct"])

    def test_no_data_lowers_coverage_but_not_the_score(self):
        clean = score(self.rows(PASS, PASS))
        murky = score(self.rows(PASS, PASS, NO_DATA))
        self.assertEqual(clean["seo_score"], murky["seo_score"])
        self.assertLess(murky["coverage_pct"], clean["coverage_pct"])

    def test_warn_counts_as_half(self):
        self.assertEqual(score(self.rows(WARN))["seo_score"], 50)
        self.assertEqual(score(self.rows(PASS))["seo_score"], 100)
        self.assertEqual(score(self.rows(FAIL))["seo_score"], 0)

    def test_pending_work_does_not_inflate_the_score(self):
        for status in (LLM_PENDING, MANUAL):
            s = score(self.rows(PASS, status))
            self.assertEqual(s["seo_score"], 100)
            self.assertLess(s["coverage_pct"], 100)


class Diff(unittest.TestCase):
    def run_of(self, statuses, **extra):
        payload = {"items": [{"id": i, "title": i, "status": s}
                             for i, s in statuses.items()]}
        payload.update(extra)
        return payload

    def test_reports_a_real_transition(self):
        prev = self.run_of({"A": PASS, "B": PASS})
        cur = self.run_of({"A": FAIL, "B": PASS})
        changes, note = diff_runs(prev, cur)
        self.assertEqual([(c["id"], c["from"], c["to"]) for c in changes],
                         [("A", PASS, FAIL)])
        self.assertEqual(note, "")

    def test_warns_when_the_registry_changed_underneath(self):
        prev = self.run_of({"A": PASS}, registry_version="aaa")
        cur = self.run_of({"A": PASS}, registry_version="bbb")
        _, note = diff_runs(prev, cur)
        self.assertIn("registry", note)

    def test_warns_when_the_compared_sets_barely_overlap(self):
        """'No status changes' over an empty intersection is false reassurance."""
        prev = self.run_of({"A": PASS, "B": PASS})
        cur = self.run_of({"C": PASS})
        changes, note = diff_runs(prev, cur)
        self.assertEqual(changes, [])
        self.assertIn("not in this one", note)

    def test_warns_when_the_mode_changed(self):
        prev = self.run_of({"A": PASS}, mode="live")
        cur = self.run_of({"A": NA}, mode="archive")
        _, note = diff_runs(prev, cur)
        self.assertIn("mode", note)


class Profiles(unittest.TestCase):
    ITEMS = [
        {"id": "LO-196", "category": "local", "severity": "medium",
         "check": {"script": "local_seo_checker.py"}},
        {"id": "CN-001", "category": "content", "severity": "high"},
        {"id": "EC-001", "category": "content", "severity": "low",
         "check": {"script": "product_schema_checker.py"}},
    ]

    def test_category_exclusion(self):
        out = profile_excludes(self.ITEMS, {"exclude_categories": ["local"],
                                            "exclude_scripts": [], "exclude_items": []})
        self.assertEqual(set(out), {"LO-196"})

    def test_script_exclusion(self):
        out = profile_excludes(self.ITEMS, {"exclude_categories": [],
                                            "exclude_scripts": ["product_schema_checker.py"],
                                            "exclude_items": []})
        self.assertEqual(set(out), {"EC-001"})

    def test_excluded_items_never_reach_the_plan(self):
        preskip = {"CN-001": (NA, "profile")}
        items = [{"id": "CN-001", "source": "script",
                  "check": {"script": "parse_html.py", "args": [], "requires": "offline"}}]
        plan, skipped = build_plan(items, {}, {"offline"}, "archive", preskip)
        self.assertEqual(plan, {})
        self.assertIn("CN-001", skipped)


class ProfilePrompt(unittest.TestCase):
    """The prompt must never be able to hang or narrow scope behind your back."""

    class _Tty(io.StringIO):
        def isatty(self):
            return True

    def ask(self, answer, interactive=True, tty=True):
        stdin, real_input = sys.stdin, builtins.input
        sys.stdin = self._Tty() if tty else io.StringIO()
        builtins.input = lambda prompt="": answer
        try:
            return choose_profile("", interactive)
        finally:
            sys.stdin, builtins.input = stdin, real_input

    def test_explicit_flag_is_never_second_guessed(self):
        self.assertEqual(choose_profile("saas", True), "saas")

    def test_accepts_a_number_or_a_name(self):
        self.assertEqual(self.ask("2"), "local")
        self.assertEqual(self.ask("ecommerce"), "ecommerce")

    def test_enter_means_the_full_registry(self):
        self.assertEqual(self.ask(""), "default")

    def test_without_a_terminal_it_does_not_ask(self):
        """CI, cron and background runs must not block on a question nobody sees."""
        def explode(prompt=""):
            raise AssertionError("prompted with no terminal attached")
        stdin, real_input = sys.stdin, builtins.input
        sys.stdin, builtins.input = io.StringIO(), explode
        try:
            self.assertEqual(choose_profile("", True), "default")
        finally:
            sys.stdin, builtins.input = stdin, real_input

    def test_no_prompt_flag_skips_the_question(self):
        self.assertEqual(self.ask("2", interactive=False), "default")

    def test_falls_back_to_the_widest_scope_not_the_narrowest(self):
        """Every non-answer resolves to `default`. Guessing a narrower profile
        would drop checks and raise the score without anyone deciding to."""
        for answer in ("", "nonsense", "99"):
            self.assertEqual(self.ask(answer), "default")

    def test_eof_is_treated_as_no_answer(self):
        stdin, real_input = sys.stdin, builtins.input
        sys.stdin = self._Tty()

        def eof(prompt=""):
            raise EOFError

        builtins.input = eof
        try:
            self.assertEqual(choose_profile("", True), "default")
        finally:
            sys.stdin, builtins.input = stdin, real_input


class Detection(unittest.TestCase):
    """Detection may suggest, never decide. These pin down both halves."""

    def page(self, body="", head="", jsonld=None):
        ld = (f'<script type="application/ld+json">{json.dumps(jsonld)}</script>'
              if jsonld else "")
        return f"<!doctype html><html><head>{head}{ld}</head><body>{body}</body></html>"

    def test_product_schema_reads_as_a_store(self):
        d = detect(self.page(jsonld={"@type": "Product", "name": "Thing"}))
        self.assertEqual(d["profile"], "ecommerce")

    def test_localbusiness_schema_reads_as_local(self):
        d = detect(self.page(jsonld={"@type": "LocalBusiness", "name": "Cafe"}))
        self.assertEqual(d["profile"], "local")

    def test_graph_containers_and_multi_typed_nodes_are_flattened(self):
        """JSON-LD is legally a node, an array, or a @graph, and @type may be a
        list — a parser that assumes one shape reads most real sites as empty."""
        d = detect(self.page(jsonld={"@graph": [{"@type": ["Organization",
                                                           "LocalBusiness"]}]}))
        self.assertEqual(d["profile"], "local")

    def test_thin_evidence_never_narrows_anything(self):
        d = detect(self.page("<h1>Hello</h1>"))
        self.assertEqual(d["profile"], "default")
        self.assertEqual(d["confidence"], "none")

    def test_empty_input_is_an_error_not_a_guess(self):
        d = detect("")
        self.assertEqual(d["profile"], "default")
        self.assertTrue(d["error"])

    def test_image_paths_do_not_fingerprint_magento(self):
        """`mage/` matches inside `image/`; that alone fingerprinted Magento on
        two sites that have never run it."""
        d = detect(self.page('<img src="/assets/image/hero.png">'))
        self.assertNotIn("Magento", d["signals"]["ecommerce"])

    def test_a_close_second_is_reported_as_low_confidence(self):
        d = detect(self.page(
            head='<link href="/pricing"><a href="/signup">x</a>',
            body='<a href="/pricing">p</a><a href="/signup">s</a>'
                 '<a href="/cart">c</a><a href="/products/x">x</a>'))
        if d["profile"] != "default":
            self.assertIn(d["confidence"], {"low", "high"})


class DetectedProfilePrompt(unittest.TestCase):
    class _Tty(io.StringIO):
        def isatty(self):
            return True

    def ask(self, answer, detected):
        stdin, real_input = sys.stdin, builtins.input
        sys.stdin = self._Tty()
        builtins.input = lambda prompt="": answer
        try:
            return choose_profile("", True, detected)
        finally:
            sys.stdin, builtins.input = stdin, real_input

    def test_enter_accepts_the_detected_profile(self):
        d = {"profile": "local", "confidence": "high", "signals": {"local": ["x"]}}
        self.assertEqual(self.ask("", d), "local")

    def test_the_user_can_override_the_suggestion(self):
        d = {"profile": "local", "confidence": "high", "signals": {"local": ["x"]}}
        self.assertEqual(self.ask("ecommerce", d), "ecommerce")

    def test_auto_accepts_detection_without_asking(self):
        d = {"profile": "saas", "confidence": "high", "signals": {"saas": ["x"]}}

        def explode(prompt=""):
            raise AssertionError("--profile auto must not prompt")

        stdin, real_input = sys.stdin, builtins.input
        sys.stdin, builtins.input = self._Tty(), explode
        try:
            self.assertEqual(choose_profile("auto", True, d), "saas")
        finally:
            sys.stdin, builtins.input = stdin, real_input

    def test_detection_does_not_narrow_scope_without_a_terminal(self):
        """The suggestion is mentioned, never applied, when nobody can confirm."""
        d = {"profile": "ecommerce", "confidence": "high", "signals": {"ecommerce": ["x"]}}
        stdin, real_input = sys.stdin, builtins.input
        sys.stdin = io.StringIO()
        builtins.input = lambda prompt="": "ecommerce"
        try:
            self.assertEqual(choose_profile("", True, d), "default")
        finally:
            sys.stdin, builtins.input = stdin, real_input


class Sampling(unittest.TestCase):
    def row(self, item_id, status, evidence="", requires="fetch"):
        return {"id": item_id, "status": status, "evidence": evidence,
                "check": {"requires": requires}}

    def test_site_level_items_are_not_aggregated(self):
        primary = [self.row("A", PASS, "site ok", requires="crawl")]
        pages = [[self.row("A", FAIL, "page bad", requires="crawl")] for _ in range(3)]
        out = aggregate_pages(primary, pages)
        self.assertEqual(out[0]["status"], PASS)

    def test_worst_page_verdict_wins_and_the_count_is_reported(self):
        primary = [self.row("A", PASS)]
        pages = [[self.row("A", PASS)], [self.row("A", FAIL, "missing title")],
                 [self.row("A", PASS)]]
        out = aggregate_pages(primary, pages)
        self.assertEqual(out[0]["status"], FAIL)
        self.assertIn("1/3 pages", out[0]["evidence"])
        self.assertEqual(out[0]["pages_decided"], 3)

    def test_undecided_pages_do_not_become_a_verdict(self):
        primary = [self.row("A", NO_DATA)]
        pages = [[self.row("A", NO_DATA)], [self.row("A", NO_DATA)]]
        out = aggregate_pages(primary, pages)
        self.assertEqual(out[0]["status"], NO_DATA)

    def test_page_level_classification(self):
        self.assertTrue(is_page_level({"check": {"requires": "fetch"}}))
        self.assertTrue(is_page_level({"check": {"requires": "offline"}}))
        self.assertFalse(is_page_level({"check": {"requires": "crawl"}}))
        self.assertFalse(is_page_level({"check": {"requires": "gsc"}}))


class Domains(unittest.TestCase):
    def test_reduces_to_the_search_console_property(self):
        self.assertEqual(registrable_domain("www.example.com"), "example.com")
        self.assertEqual(registrable_domain("example.com"), "example.com")
        self.assertEqual(registrable_domain("shop.bbc.co.uk"), "bbc.co.uk")

    def test_platform_domains_are_not_swallowed(self):
        """What the seven hard-coded suffixes got wrong, and it is the shape most
        small sites have: the whole host is the registrable domain here, and
        reducing it produced a property nobody owns."""
        for host, expected in (("something.github.io", "something.github.io"),
                               ("myapp.vercel.app", "myapp.vercel.app"),
                               ("site.netlify.app", "site.netlify.app"),
                               ("shop.myshopify.com", "shop.myshopify.com")):
            self.assertEqual(registrable_domain(host), expected, host)

    def test_the_ccTLD_shapes_the_old_heuristic_got_right_still_work(self):
        for host, expected in (("a.b.example.com.br", "example.com.br"),
                               ("www.example.co.il", "example.co.il"),
                               ("x.example.gov.uk", "example.gov.uk")):
            self.assertEqual(registrable_domain(host), expected, host)

    def test_a_port_and_a_trailing_dot_are_ignored(self):
        self.assertEqual(registrable_domain("www.example.com:8443"), "example.com")
        self.assertEqual(registrable_domain("www.example.com."), "example.com")


class PublicSuffixList(unittest.TestCase):
    """The list is bundled, so its absence and its content are both testable
    offline — and both matter: a missing snapshot silently narrows every domain to
    its last two labels."""

    FIXTURE = """// a comment
com
co.uk
*.ck
!www.ck
github.io
"""

    def _rules(self):
        path = os.path.join(tempfile.mkdtemp(), "psl.dat")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.FIXTURE)
        return load_public_suffixes(path)

    def test_the_parser_sorts_the_three_rule_kinds(self):
        exact, wildcard, exception = self._rules()
        self.assertEqual(exact, {"com", "co.uk", "github.io"})
        self.assertEqual(wildcard, {"*.ck"})
        self.assertEqual(exception, {"www.ck"})

    def test_the_longest_matching_rule_wins(self):
        rules = self._rules()
        self.assertEqual(suffix_label_count(["example", "com"], rules), 1)
        self.assertEqual(suffix_label_count(["x", "example", "co", "uk"], rules), 2)
        self.assertEqual(suffix_label_count(["x", "github", "io"], rules), 2)

    def test_a_wildcard_rule_consumes_a_label(self):
        self.assertEqual(suffix_label_count(["foo", "bar", "ck"], self._rules()), 2)

    def test_an_exception_rule_shortens_the_suffix(self):
        """`!www.ck` against `*.ck` means www.ck is registrable, not a suffix."""
        self.assertEqual(suffix_label_count(["www", "ck"], self._rules()), 1)

    def test_an_unlisted_tld_falls_back_to_the_default_rule(self):
        self.assertEqual(suffix_label_count(["example", "zzz"], self._rules()), 1)

    def test_the_bundled_snapshot_is_present_and_plausible(self):
        """Its absence is not a crash, it is a quiet downgrade to the heuristic
        this replaced — so the shipped file gets an assertion of its own."""
        from checklist_runner import PSL_PATH
        self.assertTrue(os.path.exists(PSL_PATH), f"no snapshot at {PSL_PATH}")
        exact, wildcard, exception = load_public_suffixes(PSL_PATH)
        self.assertGreater(len(exact), 5000)
        self.assertIn("co.uk", exact)
        self.assertIn("github.io", exact, "the private section is missing")
        self.assertTrue(wildcard and exception)

    def test_a_missing_list_falls_back_loudly(self):
        import checklist_runner as cr
        saved_cache, saved_warned = cr._PSL_CACHE, cr._PSL_WARNED
        cr._PSL_CACHE, cr._PSL_WARNED = None, False
        saved_path = cr.PSL_PATH
        cr.PSL_PATH = os.path.join(tempfile.mkdtemp(), "absent.dat")
        err = io.StringIO()
        saved_stderr, sys.stderr = sys.stderr, err
        try:
            # The heuristic's answer, and the warning that it is the heuristic's.
            self.assertEqual(cr.registrable_domain("shop.bbc.co.uk"), "bbc.co.uk")
            self.assertIn("public suffix list not found", err.getvalue())
        finally:
            sys.stderr = saved_stderr
            cr.PSL_PATH = saved_path
            cr._PSL_CACHE, cr._PSL_WARNED = saved_cache, saved_warned


class UnreachableSite(unittest.TestCase):
    """The worst failure this tool can have is grading a site it never read.

    Evidence scripts mostly exit 0 with an empty result when they cannot fetch
    anything, and an empty result satisfies the assertions the registry is built
    from — `errors = 0`, no match for a warning pattern. A run against a host
    that does not resolve once scored 61/100 on 40 passes.
    """

    ITEMS = [
        {"id": "F", "check": {"requires": "fetch", "script": "s.py"}},
        {"id": "C", "check": {"requires": "crawl", "script": "s.py"}},
        {"id": "A", "check": {"requires": "api", "script": "s.py"}},
        {"id": "O", "check": {"requires": "offline", "script": "s.py"}},
        {"id": "G", "check": {"requires": "gsc", "script": "s.py"}},
    ]

    def test_everything_that_reads_the_live_site_is_undecided(self):
        skips = unreachable_skips(self.ITEMS, "HTTP 503")
        for item_id in ("F", "C", "A"):
            self.assertEqual(skips[item_id][0], NO_DATA, item_id)
            self.assertIn("unreachable", skips[item_id][1])

    def test_undecided_not_out_of_scope(self):
        """NO_DATA, never N/A: an unreadable site must cost coverage. N/A would
        drop these out of the denominator and report thin air as full cover."""
        skips = unreachable_skips(self.ITEMS, "HTTP 503")
        self.assertNotIn(NA, {v[0] for v in skips.values()})

    def test_search_console_still_answers(self):
        """Google's stored history does not stop existing because the site is
        down today, so gating it would throw away the only evidence left."""
        self.assertNotIn("G", unreachable_skips(self.ITEMS, "HTTP 503"))

    def test_no_live_site_check_reaches_the_plan(self):
        skips = unreachable_skips(self.ITEMS, "HTTP 503")
        plan, _ = build_plan(self.ITEMS, {}, {"offline", "fetch", "crawl", "api"},
                             "live", skips, True)
        planned = {i for ids in plan.values() for i in ids}
        self.assertEqual(planned & {"F", "C", "A"}, set(),
                         "a script ran against a site that could not be read")

    def test_offline_checks_fall_out_on_their_missing_input(self):
        """Offline items are not gated by reachability — they read a local file,
        not the site. Every one of them takes that file as its first argument,
        so when the fetch failed and there is no HTML to hand them, they drop out
        as NO_DATA on the missing input instead."""
        item = [{"id": "O", "check": {"requires": "offline", "script": "parse_html.py",
                                      "args": ["{html}", "--url", "{url}"]}}]
        _, skipped = build_plan(item, {"url": "https://e.com"}, {"offline"}, "live",
                                unreachable_skips(item, "HTTP 503"), False)
        self.assertEqual(skipped["O"][0], NO_DATA)
        self.assertIn("html", skipped["O"][1])


class SearchConsoleBoundary(unittest.TestCase):
    ITEM = [{"id": "G", "source": "script", "check": {"requires": "gsc", "script": "g.py"}}]

    def test_missing_credentials_is_undecided_not_out_of_scope(self):
        """live mode could have asked Search Console; it just had no key. That
        is NO_DATA. Reporting N/A hides seven items from the coverage
        denominator and raises coverage exactly where the audit is thinnest."""
        _, skipped = build_plan(self.ITEM, {}, {"offline", "fetch", "crawl", "api"},
                                "live", None, False)
        self.assertEqual(skipped["G"][0], NO_DATA)

    def test_a_mode_without_network_puts_it_out_of_scope(self):
        """archive promises no network at all, so the item genuinely does not
        apply — that one is N/A."""
        _, skipped = build_plan(self.ITEM, {}, {"offline"}, "archive", None, False)
        self.assertEqual(skipped["G"][0], NA)

    def test_credentials_present_means_it_runs(self):
        plan, skipped = build_plan(self.ITEM, {}, {"offline", "fetch", "crawl", "api"},
                                   "live", None, True)
        self.assertEqual(skipped, {})
        self.assertEqual(len(plan), 1)

    def _impossible(self, has_gsc):
        items = [{"id": i, "source": "gsc", "category": "c", "category_label": "C",
                  "title": "t", "severity": "low", "plerdy_ref": 0, "fix": ""}
                 for i in GSC_UNAVAILABLE]
        return grade(items, {}, {}, {}, has_gsc)

    def test_impossible_items_never_blame_missing_credentials(self):
        """Three items have no API endpoint at all. Telling someone without a key
        to set GSC_CREDENTIALS_PATH sends them to configure something that cannot
        decide them — the setup finishes and the status does not move."""
        for has_gsc in (True, False):
            for row in self._impossible(has_gsc):
                self.assertNotIn("GSC_CREDENTIALS_PATH", row["evidence"])
                self.assertIn("no ", row["evidence"].lower())

    def test_impossible_items_are_manual_not_undecided(self):
        """They are answerable today — by a person opening the UI. NO_DATA says
        the audit tried and failed, and invites somebody to fix the tool."""
        for has_gsc in (True, False):
            for row in self._impossible(has_gsc):
                self.assertEqual(row["status"], MANUAL)
                self.assertIn("UI", row["evidence"])

    def test_the_switch_to_manual_does_not_move_coverage(self):
        """Both statuses stay in the denominator and out of the decided count. If
        this ever diverges, the reclassification became a way to lift a number."""
        rows = [{"id": "X", "category": "c", "category_label": "C",
                 "severity": "high", "status": NO_DATA, "effort": "low"}]
        as_no_data = score(rows)
        as_manual = score([dict(rows[0], status=MANUAL)])
        self.assertEqual(as_no_data["coverage_pct"], as_manual["coverage_pct"])
        self.assertEqual(as_no_data["applicable"], as_manual["applicable"])
        self.assertEqual(as_no_data["decided"], as_manual["decided"])

    def test_a_future_gsc_item_without_an_entry_still_reports_undecided(self):
        """The fallback is not dead code: it is what an item added to the registry
        before anyone writes its reason falls back to."""
        item = [{"id": "GO-999", "source": "gsc", "category": "c",
                 "category_label": "C", "title": "t", "severity": "low",
                 "plerdy_ref": 0, "fix": ""}]
        self.assertEqual(grade(item, {}, {}, {}, True)[0]["status"], NO_DATA)


class SecretsStayOutOfTheOutput(unittest.TestCase):
    """checklist-results.json and .seo-runs/ are what gets shared. The run log is
    built from each script's argv, so a key passed as an argument lands in it."""

    def test_secret_values_are_replaced_everywhere(self):
        payload = {"runs": {"indexnow_checker.py --key ABC123": {"error": None}},
                   "items": [{"evidence": "failed: bad key ABC123"}],
                   "nested": [{"deep": {"k": "ABC123"}}]}
        out = redact(payload, ("ABC123",))
        self.assertNotIn("ABC123", json.dumps(out))
        self.assertIn("<redacted>", list(out["runs"])[0])

    def test_nothing_is_touched_without_secrets(self):
        payload = {"runs": {"a.py --flag v": {}}}
        self.assertEqual(redact(payload, ()), payload)


class SampleDiscovery(unittest.TestCase):
    """A sampled asset fails every page-level check, and sampling aggregates on
    the worst verdict — so one stylesheet in the sample condemns the site."""

    def test_assets_are_not_pages(self):
        for url in ("https://e.com/assets/app.css", "https://e.com/logo.png",
                    "https://e.com/f.pdf", "https://e.com/bundle.js"):
            self.assertFalse(looks_like_a_page(url), url)

    def test_real_pages_survive(self):
        for url in ("https://e.com/about", "https://e.com/blog/post?id=7",
                    "https://e.com/", "https://e.com/index.html",
                    "https://e.com/v1.2/guide"):
            self.assertTrue(looks_like_a_page(url), url)

    def test_only_anchors_are_followed(self):
        """The old pattern matched every href in the document, so stylesheets,
        icons and preload hints filled the sample before any real page."""
        html = ('<link rel="stylesheet" href="/app.css">'
                '<link rel="icon" href="/fav.ico">'
                '<a href="/about">a</a>')
        self.assertEqual(ANCHOR_RE.findall(html), ["/about"])

    def test_the_query_string_is_kept(self):
        """Cutting at `?` produced a different URL that frequently 404s, and on
        many sites the query is what makes it a distinct page at all."""
        self.assertEqual(ANCHOR_RE.findall('<a href="/p?id=7#top">x</a>'), ["/p?id=7#top"])


def _page(title="Example", body="Hello there.", head="", extra=""):
    return (f"<!doctype html><html><head><title>{title}</title>{head}</head>"
            f"<body><h1>{title}</h1><p>{body}</p>{extra}</body></html>")


class PageGuard(unittest.TestCase):
    """The hole the reachability gate left open.

    A challenge page and a soft 404 both answer 200 with well-formed HTML, so
    every evidence script runs against a page that is not the site and the
    registry grades whatever the interstitial contains. The gate on status codes
    cannot see either one.
    """

    def test_a_normal_page_passes(self):
        self.assertEqual(page_guard(_page())[0], "")

    def test_cloudflare_challenge_is_caught(self):
        html = _page("Just a moment...", "",
                     extra='<script src="/cdn-cgi/challenge-platform/h/b/orch"></script>')
        kind, detail = page_guard(html)
        self.assertEqual(kind, "bot_challenge")
        self.assertIn("Cloudflare", detail)

    def test_vendor_challenges_are_caught_from_their_markup(self):
        """Where these strings actually live on a block page: a script src, a
        stylesheet href, an element id — never the prose."""
        for tag, vendor in (
                ('<script src="/_Incapsula_Resource?SWJIYLWA=719">', "Imperva"),
                ('<div id="px-captcha"></div>', "PerimeterX"),
                ('<script src="https://ct.datado.me/c.js">', "DataDome"),
                ('<script src="https://token.awswaf.com/x/challenge.js">', "AWS WAF"),
                ('<script src="/sucuri_cloudproxy_js/x.js">', "Sucuri"),
                ('<img src="//errors.edgesuite.net/18.abcd.ip">', "Akamai")):
            kind, detail = page_guard(_page("Blocked", "", extra=tag))
            self.assertEqual(kind, "bot_challenge", tag)
            self.assertIn(vendor.split()[0], detail, tag)

    def test_vendors_that_name_themselves_in_the_text_are_caught_there(self):
        """Imperva and Sucuri print their name on the block page itself, so for
        those two the visible text is the right place to look."""
        for phrase, vendor in (("Incapsula incident ID: 282-31", "Imperva"),
                               ("Access Denied - Sucuri Website Firewall", "Sucuri")):
            kind, detail = page_guard(_page("Blocked", phrase))
            self.assertEqual(kind, "bot_challenge", phrase)
            self.assertIn(vendor, detail, phrase)

    def test_challenge_title_without_a_vendor_string(self):
        self.assertEqual(page_guard(_page("Checking your browser", ""))[0],
                         "bot_challenge")
        self.assertEqual(page_guard(_page("Attention Required!", ""))[0],
                         "bot_challenge")

    def test_a_short_article_quoting_a_vendor_string_is_not_a_challenge(self):
        """The mirror-image failure, and the one an end-to-end run actually hit:
        a 90-word article quoting `cdn-cgi/challenge-platform` in its prose was
        called an interstitial. Word count alone cannot separate the two, because
        real articles are often short. Placement can: on a challenge page the
        vendor string is a script src, in an article it is text."""
        html = _page("How Cloudflare bot protection works",
                     "Cloudflare serves its interstitial from "
                     "cdn-cgi/challenge-platform, which is why a crawler sees "
                     "something different from a browser.")
        self.assertLess(visible_words(html), 120)
        self.assertEqual(page_guard(html)[0], "")

    def test_a_content_page_with_the_marker_in_its_markup_survives(self):
        """Cloudflare's JS detections inject that script into ordinary pages, so
        a marker in the markup cannot condemn a page on its own either — the word
        count is the second condition on every branch."""
        html = _page("A real page", "Words that make this a page. " * 40,
                     extra='<script src="/cdn-cgi/challenge-platform/h/b/jsd"></script>')
        self.assertGreater(visible_words(html), 120)
        self.assertEqual(page_guard(html)[0], "")

    def test_script_bulk_does_not_make_a_challenge_look_content_rich(self):
        """Word counting has to ignore script bodies: a challenge page is mostly
        JavaScript, and counting it would push every one of them over the line."""
        js = "var a=1; function f(){return 'x';} " * 60
        html = _page("Just a moment...", "", extra=f"<script>{js}</script>")
        self.assertLessEqual(visible_words(html), 120)
        self.assertEqual(page_guard(html)[0], "bot_challenge")

    def test_soft_404_is_caught(self):
        for title in ("404 Not Found", "Page not found", "404", "Oops",
                      "Page Not Found | Example Shop", "Страница не найдена",
                      "Nothing found — Example Blog"):
            self.assertEqual(page_guard(_page(title))[0], "soft_404", title)

    def test_an_article_about_404s_is_not_a_soft_404(self):
        """`404` appears in the title of every article ever written about broken
        links. Substring matching would refuse to audit all of them."""
        for title in ("How to fix 404 errors on your site",
                      "The 404 page as a conversion opportunity",
                      "Room 404 | Hotel Beispiel",
                      "Error handling in Django"):
            self.assertEqual(page_guard(_page(title))[0], "", title)

    def test_soft_404_does_not_depend_on_page_size(self):
        """Templated error pages carry the site's whole nav and footer, so they
        are not small — the title is the signal, not the word count."""
        html = _page("404 Not Found", "Try the homepage. " * 200)
        self.assertGreater(visible_words(html), 120)
        self.assertEqual(page_guard(html)[0], "soft_404")


class History(unittest.TestCase):
    """Two runs in one second used to write the same file, so the history lost the
    entry the next diff would have compared against."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_the_stamp_is_sub_second(self):
        self.assertRegex(run_stamp(), r"^\d{8}T\d{9}Z$")

    def test_two_runs_in_one_stamp_do_not_share_a_file(self):
        stamp = run_stamp()
        first = history_path("e.com", stamp)
        with open(first, "w", encoding="utf-8") as f:
            json.dump({"marker": 1}, f)
        second = history_path("e.com", stamp)
        self.assertNotEqual(first, second)
        with open(first, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["marker"], 1,
                             "the earlier run was overwritten")

    def test_the_newest_run_wins_regardless_of_filename_format(self):
        """A directory holding both stamp formats must still order correctly. By
        name every legacy file outranks every current one, because `-` in an ISO
        timestamp sorts below `0`."""
        os.makedirs(os.path.join(".seo-runs", "e.com"))
        for name, started in (("20260803T094000Z.json", "2026-08-03T09:40:00+00:00"),
                              ("20260803T094100500Z.json", "2026-08-03T09:41:00.5+00:00")):
            with open(os.path.join(".seo-runs", "e.com", name), "w", encoding="utf-8") as f:
                json.dump({"started_at": started, "name": name}, f)
        self.assertEqual(previous_run("e.com", "")["name"], "20260803T094100500Z.json")

    def test_a_corrupt_history_file_is_skipped_not_fatal(self):
        """A broken record of an old run is no reason to abandon the current one."""
        os.makedirs(os.path.join(".seo-runs", "e.com"))
        with open(os.path.join(".seo-runs", "e.com", "20260803T094000Z.json"), "w") as f:
            f.write("{not json")
        with open(os.path.join(".seo-runs", "e.com", "20260803T093000Z.json"), "w") as f:
            json.dump({"started_at": "2026-08-03T09:30:00+00:00", "name": "good"}, f)
        self.assertEqual(previous_run("e.com", "")["name"], "good")

    def test_the_current_run_is_excluded(self):
        os.makedirs(os.path.join(".seo-runs", "e.com"))
        path = os.path.join(".seo-runs", "e.com", "20260803T094000Z.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"started_at": "2026-08-03T09:40:00+00:00"}, f)
        self.assertIsNone(previous_run("e.com", path))

    def test_an_unparseable_name_without_a_timestamp_never_wins(self):
        os.makedirs(os.path.join(".seo-runs", "e.com"))
        for name in ("notes.json", "20260803T094000Z.json"):
            with open(os.path.join(".seo-runs", "e.com", name), "w", encoding="utf-8") as f:
                json.dump({"name": name}, f)
        self.assertEqual(previous_run("e.com", "")["name"], "20260803T094000Z.json")


class LabCoreWebVitals(unittest.TestCase):
    """Lab metrics from a browser trace. The risks are units and silence: a
    misread unit turns a failing page into a passing one, and a metric nobody
    measured must not read as a perfect score."""

    def _file(self, payload):
        path = os.path.join(tempfile.mkdtemp(), "cwv.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload if isinstance(payload, str) else json.dumps(payload))
        return path

    def test_good_metrics_are_rated(self):
        out = cwv_read(self._file({"url": "https://e.com/", "lcp_ms": 2100,
                                   "cls": 0.04, "tbt_ms": 150}))
        self.assertEqual(out["lcp_ms_rating"], "good")
        self.assertTrue(out["all_good"])

    def test_the_thresholds_are_googles(self):
        out = cwv_read(self._file({"lcp_ms": 2600, "cls": 0.2, "tbt_ms": 700}))
        self.assertEqual(out["lcp_ms_rating"], "needs_improvement")
        self.assertEqual(out["cls_rating"], "needs_improvement")
        self.assertEqual(out["tbt_ms_rating"], "poor")

    def test_an_unmeasured_metric_is_absent_not_zero(self):
        """Absent is NO_DATA to the runner. Zero would be a perfect score for a
        measurement nobody took."""
        out = cwv_read(self._file({"lcp_ms": 2100}))
        self.assertNotIn("cls", out)
        self.assertEqual(out["missing"], ["cls", "tbt_ms"])
        self.assertIsNone(evaluate({"path": "cls", "lte": 0.1}, out)[0])

    def test_all_good_covers_only_what_was_measured(self):
        out = cwv_read(self._file({"lcp_ms": 2100}))
        self.assertTrue(out["all_good"], "one good metric, and only one was taken")
        self.assertEqual(out["measured"], ["lcp_ms"])

    def test_a_value_with_units_in_it_is_refused(self):
        """"2.1s" cannot be compared with anything, and coercing it would invent a
        number. The file is rejected with the key naming convention explained."""
        with self.assertRaises(ValueError) as caught:
            cwv_read(self._file({"lcp_ms": "2.1s"}))
        self.assertIn("must be a number", str(caught.exception))

    def test_a_file_with_no_metrics_at_all_is_refused(self):
        with self.assertRaises(ValueError):
            cwv_read(self._file({"lcp": 2.1}))

    def test_a_negative_value_is_refused(self):
        with self.assertRaises(ValueError):
            cwv_read(self._file({"lcp_ms": -5}))

    def test_a_missing_file_says_so(self):
        with self.assertRaises(ValueError) as caught:
            cwv_read("/nowhere/cwv.json")
        self.assertIn("no such file", str(caught.exception))

    def test_broken_json_says_so(self):
        with self.assertRaises(ValueError) as caught:
            cwv_read(self._file("{not json"))
        self.assertIn("not JSON", str(caught.exception))

    def test_one_level_of_nesting_is_tolerated(self):
        out = cwv_read(self._file({"url": "https://e.com/",
                                   "metrics": {"lcp_ms": 900, "cls": 0.01,
                                               "tbt_ms": 20}}))
        self.assertEqual(out["measured"], ["lcp_ms", "cls", "tbt_ms"])

    def test_the_registry_keeps_lab_and_field_apart(self):
        """Separate items because they are separate claims. If a lab item ever
        started answering SP-108 or SP-113, one number would stand for both a
        controlled run and what real visitors got."""
        with open(os.path.join(SCRIPTS, "..", "resources", "config",
                               "checklist.json"), encoding="utf-8") as f:
            items = json.load(f)["items"]
        by_id = {i["id"]: i for i in items}
        for lab in ("SP-214", "SP-215", "SP-216"):
            self.assertEqual(by_id[lab]["check"]["script"], "cwv_metrics.py")
        for field in ("SP-108", "SP-113"):
            self.assertEqual(by_id[field]["check"]["script"], "pagespeed.py")


class ThinEntryPage(unittest.TestCase):
    """A page with no prose is flagged, not refused.

    An interstitial from a vendor the guard does not recognise and a
    client-rendered shell are indistinguishable from here — and the second is a
    real page with a real finding that the JS-rendering items exist to report.
    Refusing to score would hide that finding behind a guess; scoring silently
    would present a shell's verdicts as the site's. So: audit, and say the number.
    """

    def test_the_threshold_is_lower_than_the_challenge_one(self):
        """Two different questions. The challenge guard asks "is this page an
        interstitial", and needs room for a challenge's own prose; this asks "is
        there anything here to audit at all"."""
        from checklist_runner import CHALLENGE_MAX_WORDS
        self.assertLess(THIN_ENTRY_WORDS, CHALLENGE_MAX_WORDS)

    def test_a_shell_is_thin_and_an_article_is_not(self):
        shell = ('<!doctype html><html><head><title>App</title></head>'
                 '<body><div id="root"></div><script>var a=1;</script></body></html>')
        self.assertLess(visible_words(shell), THIN_ENTRY_WORDS)
        article = _page("Real", "Words that make this a page. " * 20)
        self.assertGreaterEqual(visible_words(article), THIN_ENTRY_WORDS)

    def test_a_shell_is_not_treated_as_an_interstitial(self):
        """It carries no vendor fingerprint and no challenge title, so the guard
        must leave it alone — otherwise the audit refuses every SPA."""
        shell = ('<!doctype html><html><head><title>App</title></head>'
                 '<body><div id="root"></div></body></html>')
        self.assertEqual(page_guard(shell)[0], "")


class PublicSuffixStaleness(unittest.TestCase):
    """The snapshot is a dated artifact, and its age only mattered when somebody
    thought to ask. A stale list is missing suffixes registered since it was taken,
    and the only symptom is a Search Console property that answers nothing."""

    def _snapshot(self, header):
        path = os.path.join(tempfile.mkdtemp(), "psl.dat")
        with open(path, "w", encoding="utf-8") as f:
            f.write(header + "com\nco.uk\n")
        return path

    def test_the_bundled_snapshot_declares_its_date(self):
        taken, age = psl_staleness()
        self.assertRegex(taken, r"^\d{4}-\d{2}-\d{2}$")
        self.assertGreaterEqual(age, 0)

    def test_the_date_is_read_from_the_header(self):
        path = self._snapshot("// snapshot taken 2020-01-01\n")
        self.assertEqual(psl_snapshot_date(path), "2020-01-01")
        self.assertGreater(psl_staleness(path)[1], 365)

    def test_a_snapshot_without_a_date_reports_unknown_age(self):
        """-1, not 0: "we cannot tell how old this is" must not read as "fresh"."""
        self.assertEqual(psl_staleness(self._snapshot("// no stamp here\n")), ("", -1))

    def test_an_unparseable_date_keeps_the_text_and_drops_the_age(self):
        taken, age = psl_staleness(self._snapshot("// snapshot taken last Tuesday\n"))
        self.assertEqual((taken, age), ("last Tuesday", -1))


class WrongPageWidensTheGate(unittest.TestCase):
    """A page that read fine and is the wrong page is not the same as a page that
    could not be read, and the offline checks are where the difference shows."""

    ITEMS = [
        {"id": "F", "check": {"requires": "fetch", "script": "s.py"}},
        {"id": "O", "check": {"requires": "offline", "script": "s.py"}},
        {"id": "G", "check": {"requires": "gsc", "script": "s.py"}},
    ]

    def test_offline_checks_are_gated_when_the_page_is_wrong(self):
        """An interstitial parses perfectly, so the offline scripts grade its 12
        words as the site. In archive mode that produced 6 passes and 10 failures
        before this gate existed."""
        skips = unreachable_skips(self.ITEMS, "soft 404", wrong_page=True)
        self.assertEqual(skips["O"][0], NO_DATA)
        self.assertIn("not the site", skips["O"][1])

    def test_offline_checks_are_not_gated_when_the_fetch_merely_failed(self):
        """There is no HTML to hand them in that case, so they already drop out on
        their missing input, with a reason that says which input."""
        self.assertNotIn("O", unreachable_skips(self.ITEMS, "HTTP 503"))

    def test_search_console_answers_either_way(self):
        for kwargs in ({}, {"wrong_page": True}):
            self.assertNotIn("G", unreachable_skips(self.ITEMS, "x", **kwargs))


class CrossHostRedirect(unittest.TestCase):
    """`fetch_page` used to discard the URL it actually landed on."""

    def test_another_host_wins(self):
        self.assertEqual(audit_target("https://old.com/", "https://new.com/"),
                         "https://new.com/")

    def test_a_same_host_hop_keeps_the_requested_url(self):
        """So redirect_checker.py still sees the hop it exists to report; nothing
        downstream is confused by a path-only redirect."""
        self.assertEqual(audit_target("https://e.com/a", "https://e.com/b"),
                         "https://e.com/a")

    def test_www_counts_as_another_host(self):
        """discover_urls filters on netloc, so www.example.com vs example.com is
        the difference between an eight-page sample and a one-page one."""
        self.assertEqual(audit_target("https://e.com/", "https://www.e.com/"),
                         "https://www.e.com/")

    def test_no_final_url_changes_nothing(self):
        self.assertEqual(audit_target("https://e.com/", ""), "https://e.com/")

    def test_the_search_console_property_follows_the_destination(self):
        """The bug this fixes: sc-domain: was derived from the domain that
        redirected away, and Search Console answered nothing for it."""
        dest = audit_target("https://old.com/", "https://shop.new.co.uk/")
        from urllib.parse import urlparse as _p
        self.assertEqual(registrable_domain(_p(dest).netloc), "new.co.uk")


class FetchCarriesTheDestination(unittest.TestCase):
    """fetch_page against a stubbed transport — the guard and the final URL are
    decided here, so they are worth pinning without a network."""

    class _Resp:
        def __init__(self, text, url, code=200, ctype="text/html"):
            self.text, self.url, self.status_code = text, url, code
            self.headers = {"Content-Type": ctype}

    def _fetch(self, resp, **kw):
        import lib.safe_http as sh
        from checklist_runner import fetch_page
        original = sh.safe_get
        sh.safe_get = lambda url, **_: resp
        try:
            return fetch_page("https://asked.example/", **kw)
        finally:
            sh.safe_get = original

    def test_the_final_url_is_reported(self):
        out = self._fetch(self._Resp(_page(), "https://landed.example/en/"))
        self.assertEqual(out.final_url, "https://landed.example/en/")
        self.assertEqual(out.error, "")
        os.unlink(out.path)

    def test_a_challenge_page_is_an_error_not_a_page(self):
        html = _page("Just a moment...", "")
        out = self._fetch(self._Resp(html, "https://asked.example/"))
        self.assertEqual(out.path, "")
        self.assertEqual(out.guard, "bot_challenge")
        self.assertIn("bot protection", out.error)

    def test_no_page_guard_records_the_suspicion_instead_of_erasing_it(self):
        """An escape hatch that forgets why it was needed is how a challenge page
        ends up scored as a site with nobody able to tell afterwards."""
        html = _page("Just a moment...", "")
        out = self._fetch(self._Resp(html, "https://asked.example/"),
                          enforce_guard=False)
        self.assertTrue(out.path)
        self.assertEqual(out.error, "")
        self.assertEqual(out.guard, "bot_challenge")
        os.unlink(out.path)


class ScriptFailureKind(unittest.TestCase):
    """A timeout and a crash both end as NO_DATA, and until now the report could
    not tell you which. Only one of the two is worth retrying."""

    ITEM = [{"id": "X", "source": "script", "severity": "high", "category": "c",
             "category_label": "C", "plerdy_ref": "", "title": "t",
             "check": {"script": "s.py", "assert": {"path": "n", "eq": 1}}}]

    def _graded(self, result):
        plan = {("s.py", ("s.py",)): ["X"]}
        return grade(self.ITEM, plan, {("s.py", ("s.py",)): result}, {}, False)[0]

    def test_timeout_is_labelled_and_marked_retryable(self):
        row = self._graded({"__error__": "no result after 180s; retryable",
                            "__error_kind__": "timeout"})
        self.assertEqual(row["status"], NO_DATA)
        self.assertEqual(row["error_kind"], "timeout")
        self.assertIn("timed out", row["evidence"])

    def test_crash_is_labelled_a_failure(self):
        row = self._graded({"__error__": "[s.py] Traceback", "__error_kind__": "crash"})
        self.assertEqual(row["error_kind"], "crash")
        self.assertIn("script failed", row["evidence"])

    def test_an_unlabelled_error_is_treated_as_a_crash(self):
        """Older history and any script path that forgets to set a kind must not
        be silently reported as a timeout — a crash is the honest default."""
        row = self._graded({"__error__": "something"})
        self.assertEqual(row["error_kind"], "crash")

    def test_every_kind_run_script_produces_has_a_label(self):
        """The labels live next to the code that raises them; a list kept in a
        test drifts exactly the way the bug did."""
        with open(os.path.join(SCRIPTS, "checklist_runner.py"), encoding="utf-8") as f:
            src = f.read()
        kinds = set(re.findall(r'"error_kind":\s*"(\w+)"', src))
        self.assertTrue(kinds)
        self.assertEqual(kinds - set(FAILURE_LABEL), set())

    def test_a_missing_script_says_so(self):
        out = run_script("definitely_not_a_script.py", [])
        self.assertEqual(out["error_kind"], "missing")


if __name__ == "__main__":
    unittest.main()
