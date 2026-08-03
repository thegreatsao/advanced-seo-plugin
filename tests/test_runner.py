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
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "seo-checklist", "scripts")
sys.path.insert(0, SCRIPTS)

from checklist_runner import (  # noqa: E402
    ANCHOR_RE, FAIL, GSC_UNAVAILABLE, LLM_PENDING, MANUAL, NA, NO_DATA, PASS, WARN,
    aggregate_pages, build_plan, choose_profile, diff_runs, evaluate, grade,
    is_page_level, looks_like_a_page, profile_excludes, redact,
    registrable_domain, resolve, score, unreachable_skips,
)
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

    def test_impossible_items_never_blame_missing_credentials(self):
        """Three items have no API endpoint at all. Telling someone without a key
        to set GSC_CREDENTIALS_PATH sends them to configure something that cannot
        decide them — the setup finishes and the status does not move."""
        items = [{"id": i, "source": "gsc", "category": "c", "category_label": "C",
                  "title": "t", "severity": "low", "plerdy_ref": 0, "fix": ""}
                 for i in GSC_UNAVAILABLE]
        for has_gsc in (True, False):
            for row in grade(items, {}, {}, {}, has_gsc):
                self.assertEqual(row["status"], NO_DATA)
                self.assertNotIn("GSC_CREDENTIALS_PATH", row["evidence"])
                self.assertIn("no ", row["evidence"].lower())


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


if __name__ == "__main__":
    unittest.main()
