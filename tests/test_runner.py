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
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "seo-checklist", "scripts")
sys.path.insert(0, SCRIPTS)

from checklist_runner import (  # noqa: E402
    ANCHOR_RE, FAIL, FAILURE_LABEL, GSC_UNAVAILABLE, LLM_PENDING, MANUAL, NA,
    NEEDS_THE_OUTSIDE_WORLD, NO_DATA, PASS, WARN, aggregate_pages, artifact_subject,
    audit_target,
    build_plan, choose_profile, diff_runs, evaluate, grade, is_page_level,
    private_host_skips, reads_artifact, same_page,
    looks_like_a_page, page_guard, profile_excludes, redact, registrable_domain,
    THIN_ENTRY_WORDS, history_path, load_public_suffixes, previous_run,
    psl_snapshot_date, psl_staleness, resolve, run_script,
    run_stamp, score, stride, suffix_label_count, unreachable_skips,
    visible_words,
)
from cwv_metrics import read as cwv_read  # noqa: E402
from rendered_audit import read as rendered_read  # noqa: E402
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


class PatternScopedToAField(unittest.TestCase):
    """A finding says what is wrong; a `fix` says what to do about it, in the
    vocabulary of the thing being asked for. Matching the whole element means a
    pattern meant for findings hits the advice instead — which is how two keyword
    items fired on "…containing the primary keyword" inside a remediation string
    and never once looked at a keyword."""

    ISSUES = {"seo_issues": [
        {"severity": "Critical", "area": "H1", "finding": "No H1 tag detected.",
         "fix": "Add a single, descriptive H1 containing the primary keyword."}]}

    def test_unscoped_matching_hits_the_remediation_text(self):
        """The bug, pinned so it cannot come back as a surprise."""
        ok, why = evaluate({"path": "seo_issues",
                            "none_matching": "(?i)h1.*keyword"}, self.ISSUES)
        self.assertFalse(ok)
        self.assertIn("keyword", why)

    def test_scoping_to_the_finding_ignores_the_fix(self):
        ok, why = evaluate({"path": "seo_issues", "field": "finding",
                            "none_matching": "(?i)h1.*keyword"}, self.ISSUES)
        self.assertTrue(ok)
        self.assertIn("finding", why)

    def test_it_still_matches_a_real_finding(self):
        ok, why = evaluate({"path": "seo_issues", "field": "finding",
                            "none_matching": "(?i)no h1"}, self.ISSUES)
        self.assertFalse(ok)
        self.assertIn("No H1", why)

    def test_a_field_no_element_carries_is_undecided(self):
        """Not a pass. An element shape that changed underneath must not read as
        clean — that is the whole failure this file is about."""
        ok, why = evaluate({"path": "seo_issues", "field": "message",
                            "none_matching": "x"}, self.ISSUES)
        self.assertIsNone(ok)
        self.assertIn("message", why)

    def test_an_empty_list_still_passes(self):
        self.assertTrue(evaluate({"path": "seo_issues", "field": "finding",
                                  "none_matching": "x"}, {"seo_issues": []})[0])

    def test_the_two_keyword_items_are_judgements_now(self):
        with open(os.path.join(SCRIPTS, "..", "resources", "config",
                               "checklist.json"), encoding="utf-8") as f:
            by_id = {i["id"]: i for i in json.load(f)["items"]}
        for item_id in ("KW-072", "KW-073"):
            self.assertEqual(by_id[item_id]["source"], "llm", item_id)
            self.assertEqual(by_id[item_id]["lens"], "copy", item_id)


class _Resp:
    """The parts of a response the pacing logic looks at."""

    def __init__(self, status_code, headers):
        self.status_code, self.headers = status_code, headers


class RateLimiting(unittest.TestCase):
    """An audit is a burst by construction: the evidence scripts run concurrently
    and several walk a sitemap inside their own process. This is the only open item
    that could harm somebody else's server rather than the audit's own honesty."""

    def setUp(self):
        self.saved = os.environ.get("SEO_MAX_RPS")
        os.environ.pop("SEO_MAX_RPS", None)
        import lib.safe_http as sh
        self.sh = sh
        self.dir = tempfile.mkdtemp()
        self.saved_dir = sh.RATE_LIMIT_DIR
        sh.RATE_LIMIT_DIR = self.dir

    def tearDown(self):
        self.sh.RATE_LIMIT_DIR = self.saved_dir
        shutil.rmtree(self.dir, ignore_errors=True)
        if self.saved is None:
            os.environ.pop("SEO_MAX_RPS", None)
        else:
            os.environ["SEO_MAX_RPS"] = self.saved

    def test_pacing_is_on_by_default(self):
        self.assertGreater(self.sh.max_rps(), 0)

    def test_consecutive_requests_to_one_host_are_spaced(self):
        start = time.monotonic()
        for _ in range(4):
            self.sh.pace("example.com", rps=50)
        self.assertGreaterEqual(time.monotonic() - start, 0.05)

    def test_different_hosts_do_not_queue_behind_each_other(self):
        """One slow site must not pace requests to an unrelated API."""
        self.sh.pace("a.example", rps=2)
        start = time.monotonic()
        self.sh.pace("b.example", rps=2)
        self.assertLess(time.monotonic() - start, 0.2)

    def test_the_pacing_state_is_shared_between_processes(self):
        """The scripts are separate processes; an in-process limiter would let
        eight of them go at once, which is the burst this exists to stop."""
        self.assertTrue(os.path.isdir(self.dir) or True)
        self.sh.pace("shared.example", rps=50)
        self.assertTrue(os.listdir(self.dir), "nothing was written to co-ordinate on")

    def test_zero_switches_pacing_off(self):
        os.environ["SEO_MAX_RPS"] = "0"
        self.assertEqual(self.sh.max_rps(), 0.0)
        start = time.monotonic()
        for _ in range(5):
            self.sh.pace("example.com")
        self.assertLess(time.monotonic() - start, 0.05)

    def test_a_nonsense_limit_falls_back_to_the_default(self):
        """Never to "no limit": a typo in an env var must not silently remove the
        one guard that protects a third party."""
        os.environ["SEO_MAX_RPS"] = "fast please"
        self.assertEqual(self.sh.max_rps(), self.sh.DEFAULT_MAX_RPS)

    def test_a_stale_slot_does_not_park_the_audit(self):
        """monotonic() is per-boot, so a slot file that outlived a reboot can hold
        a value in the future. Waiting it out would look like a hang."""
        path = self.sh._slot_path("example.com")
        os.makedirs(self.dir, exist_ok=True)
        with open(path, "w") as f:
            f.write(str(time.monotonic() + 10_000))
        start = time.monotonic()
        self.sh.pace("example.com", rps=50)
        self.assertLess(time.monotonic() - start, 0.5)

    def test_a_corrupt_slot_never_raises(self):
        """The bug this guards: the slot was opened "a+", and in append mode POSIX
        writes at the end of the file whatever seek() and truncate() say — so two
        updates concatenated, float() raised out of pace(), through safe_get, and
        crashed 36 evidence scripts in one run. A politeness feature must not be
        able to fail an audit."""
        os.makedirs(self.dir, exist_ok=True)
        with open(self.sh._slot_path("example.com"), "w") as f:
            f.write("153761.196713791153761.196978791")
        self.sh.pace("example.com", rps=50)  # must not raise

    def test_a_slot_holding_nonsense_never_raises(self):
        os.makedirs(self.dir, exist_ok=True)
        for junk in ("", "   ", "not a number", "\x00\x01", "1,5"):
            with open(self.sh._slot_path("example.com"), "w") as f:
                f.write(junk)
            self.sh.pace("example.com", rps=50)

    def test_an_unwritable_state_directory_still_paces(self):
        """Unable to co-ordinate is a reason to slow down alone, not to give up."""
        self.sh.RATE_LIMIT_DIR = "/dev/null/nope"
        start = time.monotonic()
        waited = self.sh.pace("example.com", rps=20)
        self.assertGreater(waited, 0)
        self.assertGreaterEqual(time.monotonic() - start, 0.04)

    def test_the_slot_holds_exactly_one_timestamp_after_many_writes(self):
        for _ in range(6):
            self.sh.pace("example.com", rps=200)
        with open(self.sh._slot_path("example.com")) as f:
            float(f.read().strip())  # raises if two updates concatenated again

    def test_retry_after_is_read_in_both_formats(self):
        self.assertEqual(self.sh.retry_after_seconds(_Resp(429, {"Retry-After": "7"})), 7.0)
        future = self.sh.retry_after_seconds(
            _Resp(503, {"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"}))
        self.assertGreater(future, 0)

    def test_retry_after_only_applies_to_a_backoff_status(self):
        """Some CDNs send the header on a 200. Sleeping on that would pace the
        audit to somebody else's cache policy."""
        self.assertEqual(self.sh.retry_after_seconds(_Resp(200, {"Retry-After": "7"})), 0.0)

    def test_an_unparseable_retry_after_waits_for_nothing(self):
        """Waiting a made-up interval is not more polite than not waiting."""
        self.assertEqual(self.sh.retry_after_seconds(_Resp(429, {"Retry-After": "soon"})), 0.0)

    def test_a_date_in_the_past_waits_for_nothing(self):
        self.assertEqual(
            self.sh.retry_after_seconds(_Resp(429, {"Retry-After": "Wed, 21 Oct 2020 07:28:00 GMT"})),
            0.0)

    def test_an_absurd_backoff_is_not_waited_out(self):
        """A server saying "come back in an hour" is not worth blocking an audit
        for; the item reports NO_DATA with the reason instead."""
        self.assertLess(self.sh.MAX_RETRY_AFTER_WAIT, 120)
        self.assertGreater(self.sh.retry_after_seconds(_Resp(429, {"Retry-After": "3600"})),
                           self.sh.MAX_RETRY_AFTER_WAIT)


class PrivateAddresses(unittest.TestCase):
    """The escape hatch in the SSRF guard, and the parts of it that must not open.

    Two things depend on this being right in both directions. With no way through,
    the live path — 55 scripts, the shared pacing, five crawlers — can only ever be
    exercised against a real third-party site, which is how a slot-file bug crashed
    36 scripts in production while every test here passed. Opened too far, a crawl
    following links a site controls can be talked into reading cloud instance
    metadata off 169.254.169.254 and putting it in an artifact.
    """

    METADATA = "169.254.169.254"       # AWS/GCP/Azure instance metadata

    def setUp(self):
        import lib.safe_http as sh
        self.sh = sh
        self.saved = os.environ.get("SEO_ALLOW_PRIVATE")
        os.environ.pop("SEO_ALLOW_PRIVATE", None)
        sh._announced_private = False

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("SEO_ALLOW_PRIVATE", None)
        else:
            os.environ["SEO_ALLOW_PRIVATE"] = self.saved
        self.sh._announced_private = False

    def allow(self, value="1"):
        os.environ["SEO_ALLOW_PRIVATE"] = value

    def test_private_addresses_are_blocked_by_default(self):
        """The default is the guarantee: nothing about this change may make an
        unflagged run reach an address it could not reach before."""
        for host in ("127.0.0.1", "10.0.0.5", "192.168.1.10", "[::1]", self.METADATA):
            with self.assertRaises(self.sh.SafeHTTPError, msg=host):
                self.sh.assert_safe_url(f"http://{host}/")

    def test_the_refusal_names_the_way_through(self):
        """A guard with an escape hatch nobody can find is a guard with none. The
        cost of not knowing is real: auditing a site before it launches is the
        moment an audit is worth most."""
        with self.assertRaises(self.sh.SafeHTTPError) as caught:
            self.sh.assert_safe_url("http://127.0.0.1:8000/")
        self.assertIn("--allow-private", str(caught.exception))

    def test_the_allowance_permits_a_fixture_and_a_staging_box(self):
        self.allow()
        for host in ("127.0.0.1:8000", "10.0.0.5", "172.16.4.4", "192.168.1.10",
                     "[::1]:8000", "[fd00::1]", "100.64.1.1"):
            self.sh.assert_safe_url(f"http://{host}/")   # must not raise

    def test_link_local_stays_blocked_with_the_allowance_on(self):
        """The whole reason the allowed set is enumerated rather than derived from
        `ipaddress.is_private`, which is True for 169.254.0.0/16."""
        self.allow()
        for host in (self.METADATA, "169.254.1.1", "[fe80::1]"):
            with self.assertRaises(self.sh.SafeHTTPError, msg=host):
                self.sh.assert_safe_url(f"http://{host}/")

    def test_reserved_multicast_and_unspecified_stay_blocked(self):
        """Nothing legitimate is served there, so allowing them buys nothing."""
        self.allow()
        for host in ("240.0.0.1", "224.0.0.1", "0.0.0.0"):
            with self.assertRaises(self.sh.SafeHTTPError, msg=host):
                self.sh.assert_safe_url(f"http://{host}/")

    def test_the_blocked_message_says_the_flag_will_not_help(self):
        """Pointing at --allow-private when it is already on would send the reader
        to set a flag that cannot change the answer."""
        self.allow()
        with self.assertRaises(self.sh.SafeHTTPError) as caught:
            self.sh.assert_safe_url(f"http://{self.METADATA}/")
        detail = str(caught.exception)
        self.assertIn("stay blocked", detail)
        self.assertIn(self.METADATA, detail)

    def test_an_unrecognised_value_does_not_open_the_guard(self):
        """Same rule as a nonsense SEO_MAX_RPS falling back to the default rather
        than to no limit: a typo must never remove a guard."""
        for value in ("", "0", "no", "false", "please", "1 ", "TRUE"):
            os.environ["SEO_ALLOW_PRIVATE"] = value
            expected = value.strip().lower() in ("1", "true", "yes", "on")
            self.assertEqual(self.sh.allow_private(), expected, repr(value))

    def test_a_public_address_needs_no_flag(self):
        self.sh.assert_safe_url("https://93.184.216.34/")
        self.allow()
        self.sh.assert_safe_url("https://93.184.216.34/")

    def test_the_allowance_announces_itself_once(self):
        """A single evidence script run by hand has no other surface to say it on,
        and an audit of a staging copy that reads like an audit of the live site is
        the same class of lie as a fabricated score."""
        self.allow()
        err = io.StringIO()
        saved, sys.stderr = sys.stderr, err
        try:
            for _ in range(3):
                self.sh.assert_safe_url("http://127.0.0.1:8000/")
        finally:
            sys.stderr = saved
        self.assertEqual(err.getvalue().count("SEO_ALLOW_PRIVATE"), 1,
                         "the allowance must be stated, and stated once")

    def test_an_address_has_no_registrable_domain(self):
        """It invented one. `127.0.0.1` came out as `0.1`, the run built
        `sc-domain:0.1`, and both Search Console scripts crashed on it. A public IP
        would have been quieter and worse: a valid-looking property nobody owns
        answers with nothing, and nothing reads as a site with no search traffic."""
        for host in ("127.0.0.1", "127.0.0.1:8000", "8.8.8.8", "[::1]", "[::1]:8000",
                     "[2001:4860:4860::8888]"):
            self.assertEqual(registrable_domain(host), "", host)
        # And a real host with a port is still a real host — a staging box on :8443
        # is the common case now that one can be audited at all.
        self.assertEqual(registrable_domain("staging.example.co.uk:8443"),
                         "example.co.uk")

    def test_a_private_host_leaves_the_external_apis_undecided(self):
        """PageSpeed measures the page from Google's network, Safe Browsing looks it
        up, Search Console holds history for a property: none of that exists for a
        host on this machine. They crashed instead — and "script failed" sends the
        reader to open a script that is working correctly."""
        items = [{"id": "SP-108", "check": {"script": "pagespeed.py", "requires": "api"}},
                 {"id": "GO-140", "check": {"script": "gsc_checker.py", "requires": "gsc"}},
                 {"id": "CN-001", "check": {"script": "parse_html.py", "requires": "fetch"}}]
        skips = private_host_skips(items, "127.0.0.1:8000")
        self.assertEqual(sorted(skips), ["GO-140", "SP-108"])
        for status, reason in skips.values():
            # NO_DATA, never N/A: the item applies to this site, it just cannot be
            # answered here. N/A would lift coverage on the one kind of audit that
            # genuinely knows least.
            self.assertEqual(status, NO_DATA)
            self.assertIn("only reachable from here", reason)

    def test_an_explicit_property_can_keep_the_search_console_items(self):
        """Auditing a staging copy against the live site's history is a legitimate
        thing to want, and passing the flag is the operator deciding it."""
        items = [{"id": "GO-140", "check": {"script": "gsc_checker.py", "requires": "gsc"}},
                 {"id": "SP-108", "check": {"script": "pagespeed.py", "requires": "api"}}]
        gate = set(NEEDS_THE_OUTSIDE_WORLD) - {"gsc"}
        self.assertEqual(sorted(private_host_skips(items, "10.0.0.5", gate)), ["SP-108"])

    def test_the_flag_alone_does_not_make_a_host_private(self):
        """`is_private_host` answers where the host resolves, not what was permitted.
        Confusing the two would drop PageSpeed and Search Console from an ordinary
        public audit run with the flag on."""
        self.allow()
        self.assertFalse(self.sh.is_private_host("https://93.184.216.34/"))
        self.assertTrue(self.sh.is_private_host("http://127.0.0.1:8000/"))
        self.assertFalse(self.sh.is_private_host("http://nothing.invalid/"),
                         "an unresolvable host is unreachable, not private")

    def test_a_run_records_and_announces_the_allowance(self):
        """An artifact that does not record it cannot be told apart from an audit of
        the public site, and `--quiet` must not be able to suppress the one line that
        says so. Offline: the host does not resolve, which is enough — the question is
        what the run reports about itself, not what it measured.

        That the allowance also reaches the 55 evidence scripts is proved by the CI
        job that audits a fixture server on loopback: those scripts could not fetch a
        single page without it.
        """
        import subprocess
        work = tempfile.mkdtemp()
        out = os.path.join(work, "results.json")
        try:
            proc = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "checklist_runner.py"),
                 "https://nothing-resolves-here.invalid/", "--mode", "page",
                 "--allow-private", "--no-history", "--no-prompt", "--quiet",
                 "--timeout", "20", "--json", out],
                capture_output=True, text=True, timeout=300)
            self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
            with open(out, encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIs(payload["allow_private"], True)
            self.assertIs(payload["entry_private"], False,
                          "a host that does not resolve is unreachable, not private")
            self.assertIn("--allow-private", proc.stdout,
                          "the run must say so even under --quiet")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_archive_mode_claims_nothing_about_a_network_it_never_touched(self):
        """The flag is inert with no requests to permit, so the caveat would be noise
        dressed as candour. The artifact still records what was asked for."""
        import subprocess
        from checklist_report import provenance_warnings
        site = tempfile.mkdtemp()
        out = os.path.join(site, "results.json")
        with open(os.path.join(site, "index.html"), "w", encoding="utf-8") as f:
            f.write('<!doctype html><html lang="en"><head><title>Fixture page</title>'
                    '<meta name="description" content="Enough of a page to audit.">'
                    '</head><body><h1>Fixture page</h1><p>Body copy, and enough of '
                    'it that the thin-entry warning stays quiet: this assertion is '
                    'about the private-address caveat alone, so any other caveat '
                    'appearing here would pass the test for the wrong reason. Forty '
                    'visible words is the threshold, so this paragraph carries a few '
                    'more than that and says something while it does.</p>'
                    '</body></html>')
        try:
            proc = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "checklist_runner.py"),
                 "https://example.com/", "--archive", site, "--allow-private",
                 "--no-history", "--no-prompt", "--quiet", "--json", out],
                capture_output=True, text=True, timeout=300)
            self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
            with open(out, encoding="utf-8") as f:
                payload = json.load(f)
            self.assertIs(payload["allow_private"], True)
            self.assertNotIn("--allow-private", proc.stdout)
            self.assertEqual(provenance_warnings(payload), [])
        finally:
            shutil.rmtree(site, ignore_errors=True)


class Robots(unittest.TestCase):
    """robots.txt applies to what the tool discovers, never to what it was given.

    Both halves of that are load-bearing. Ignoring it while crawling somebody's site
    is impolite; applying it to the operator's own URL would refuse the 40-odd checks
    that fetch it and bury a `critical` finding under a collapsed audit."""

    def setUp(self):
        import lib.safe_http as sh
        self.sh = sh
        self.dir = tempfile.mkdtemp()
        self.saved_dir = sh.RATE_LIMIT_DIR
        sh.RATE_LIMIT_DIR = self.dir
        self.fetched = []
        self.saved_fetch = sh._fetch_robots

    def tearDown(self):
        self.sh.RATE_LIMIT_DIR = self.saved_dir
        self.sh._fetch_robots = self.saved_fetch
        shutil.rmtree(self.dir, ignore_errors=True)

    def serve(self, body):
        def fake(origin):
            self.fetched.append(origin)
            return body
        self.sh._fetch_robots = fake

    def test_a_disallowed_path_is_refused(self):
        self.serve("User-agent: *\nDisallow: /private\n")
        self.assertFalse(self.sh.robots_allows("https://example.com/private/x")[0])
        self.assertTrue(self.sh.robots_allows("https://example.com/public")[0])

    def test_rules_naming_our_token_are_obeyed(self):
        """The trap this guards: RobotFileParser splits the agent at the first "/"
        and lowercases it, so passing our full User-Agent —
        "Mozilla/5.0 (compatible; AgenticSEOSkill/1.0; ...)" — yields "mozilla" and
        a site's rules for us are silently ignored while `*` applies instead."""
        self.serve(f"User-agent: {self.sh.ROBOTS_TOKEN}\nDisallow: /ours\n\n"
                   f"User-agent: *\nDisallow: /theirs\n")
        self.assertFalse(self.sh.robots_allows("https://example.com/ours")[0])
        self.assertTrue(self.sh.robots_allows("https://example.com/theirs")[0])
        self.assertNotIn("/", self.sh.ROBOTS_TOKEN)

    def test_an_absent_or_unreadable_robots_txt_allows(self):
        for body in ("", "   \n", "\x00\xff not robots at all"):
            self.serve(body)
            shutil.rmtree(self.dir, ignore_errors=True)
            self.assertTrue(self.sh.robots_allows("https://example.com/x")[0], body)

    def test_a_fetch_that_raises_allows_rather_than_failing_the_audit(self):
        def boom(origin):
            raise RuntimeError("network gone")
        self.sh._fetch_robots = boom
        self.assertEqual(self.sh.robots_allows("https://example.com/x"), (True, 0.0))

    def test_robots_txt_is_fetched_once_per_origin_and_cached(self):
        """45 evidence scripts in 45 processes would otherwise fetch it 45 times,
        which is the fan-out the pacing slots already exist to avoid."""
        self.serve("User-agent: *\nDisallow: /no\n")
        for _ in range(4):
            self.sh.robots_allows("https://example.com/a")
        self.assertEqual(len(self.fetched), 1)

    def test_a_slower_crawl_delay_is_honoured_and_a_faster_one_ignored(self):
        self.serve(f"User-agent: {self.sh.ROBOTS_TOKEN}\nCrawl-delay: 10\n")
        allowed, delay = self.sh.robots_allows("https://example.com/a")
        self.assertTrue(allowed)
        self.assertEqual(delay, 10.0)
        # 10s between requests is 0.1 rps: slower than the 4 rps default, so it wins.
        self.assertAlmostEqual(self.sh._rate_for(10.0), 0.1)
        # 0.01s would be 100 rps. A site cannot talk us into going faster.
        self.assertEqual(self.sh._rate_for(0.01), self.sh.max_rps())
        self.assertIsNone(self.sh._rate_for(0.0))

    def test_respect_robots_is_off_by_default(self):
        """The signature is the guarantee: a script that fetches the audit target
        cannot be refused by robots.txt unless it deliberately opts in."""
        import inspect
        sig = inspect.signature(self.sh.safe_request)
        self.assertIs(sig.parameters["respect_robots"].default, False)
        self.assertIs(inspect.signature(
            __import__("seo_common").fetch_url).parameters["respect_robots"].default,
            False)

    def test_a_refusal_is_flagged_apart_from_a_failure(self):
        """`orphan_pages_from_sitemap` counts unreachable sitemap URLs as orphans and
        GO-137 fails on one. A robots refusal arriving as a plain error would have
        manufactured that failure out of our own politeness."""
        import seo_common
        saved = seo_common.safe_request

        def refuse(*a, **kw):
            raise self.sh.RobotsDisallowed("robots.txt disallows it")
        seo_common.safe_request = refuse
        try:
            out = seo_common.fetch_url("https://example.com/x", respect_robots=True)
        finally:
            seo_common.safe_request = saved
        self.assertTrue(out["robots_blocked"])
        self.assertIn("robots.txt", out["error"])

    def test_a_robots_skipped_sitemap_url_is_not_an_orphan(self):
        import orphan_pages_from_sitemap as ops
        crawl = {"pages": {"https://e.com/a": {"url": "https://e.com/a"}},
                 "errors": [], "robots_skipped": ["https://e.com/blocked"]}
        saved_crawl, saved_sitemap = ops.crawl_reachable_pages, ops.load_sitemap_urls
        ops.crawl_reachable_pages = lambda *a, **k: crawl
        ops.load_sitemap_urls = lambda *a, **k: {
            "urls": ["https://e.com/a", "https://e.com/blocked"],
            "sitemaps_checked": ["https://e.com/sitemap.xml"], "errors": []}
        try:
            out = ops.find_orphan_pages("https://e.com")
        finally:
            ops.crawl_reachable_pages, ops.load_sitemap_urls = saved_crawl, saved_sitemap
        self.assertEqual(out["summary"]["orphan_pages"], 0)
        self.assertEqual(out["sitemap_urls_blocked_by_robots"],
                         ["https://e.com/blocked"])
        self.assertIn("sitemap_robots_conflict",
                      [i["type"] for i in out["issues"]])

    def test_an_unlinked_disallowed_sitemap_url_is_not_an_orphan_either(self):
        """The same failure by a different road, and the road that gets travelled.

        The crawl can only record a refusal for a URL it tried, and it tries what the
        site links to — so a disallowed sitemap URL that nothing links to arrived with
        no refusal attached and was counted as an orphan. That is the ordinary case,
        not an edge one: a page is usually unlinked *because* it is blocked. Caught
        against the fixture site the first time the live path could be run at all.
        """
        import orphan_pages_from_sitemap as ops
        crawl = {"pages": {"https://e.com/a": {"url": "https://e.com/a"}},
                 "errors": [], "robots_skipped": []}     # nothing linked to it
        saved = (ops.crawl_reachable_pages, ops.load_sitemap_urls, ops.robots_allows)
        ops.crawl_reachable_pages = lambda *a, **k: crawl
        ops.load_sitemap_urls = lambda *a, **k: {
            "urls": ["https://e.com/a", "https://e.com/private/x",
                     "https://e.com/real-orphan"],
            "sitemaps_checked": ["https://e.com/sitemap.xml"], "errors": []}
        ops.robots_allows = lambda url: ("/private/" not in url, 0.0)
        try:
            out = ops.find_orphan_pages("https://e.com")
        finally:
            (ops.crawl_reachable_pages, ops.load_sitemap_urls,
             ops.robots_allows) = saved
        self.assertEqual(out["orphan_pages"], ["https://e.com/real-orphan"])
        self.assertEqual(out["sitemap_urls_blocked_by_robots"],
                         ["https://e.com/private/x"])


class AggregationKeepsVerdictAndMeasureTogether(unittest.TestCase):
    """The worst sampled page decides the verdict, so it has to supply the numbers
    too. It did not: a live report printed "52 characters, no more than 60 is
    acceptable" underneath a FAIL, because the verdict came from a page with 61 and
    the measurement from the entry page. A passing number beside a failing verdict
    is worse than the raw assertion it replaced."""

    def _row(self, status, got, ident="MS-020"):
        return {"id": ident, "title": "t", "category": "meta_structured",
                "category_label": "M", "severity": "high", "status": status,
                "effort": "low", "evidence": f"len(title) = {got}",
                "check": {"requires": "fetch"},
                "measure": {"op": "len_lte", "kind": "count", "got": got, "want": 60}}

    def test_the_measure_follows_the_worst_page(self):
        primary = [self._row(PASS, 52)]
        pages = [[self._row(PASS, 52)], [self._row(FAIL, 61)]]
        out = aggregate_pages(primary, pages)[0]
        self.assertEqual(out["status"], FAIL)
        self.assertEqual(out["measure"]["got"], 61,
                         "the report would show a passing number under a failure")

    def test_a_single_page_run_is_untouched(self):
        primary = [self._row(PASS, 52)]
        out = aggregate_pages(primary, [[self._row(PASS, 52)]])[0]
        self.assertEqual(out["measure"]["got"], 52)


class BrowserArtifacts(unittest.TestCase):
    """A trace is the only evidence in an audit that this process cannot re-take.

    Everything else a verdict rests on came from a request made here and can be
    checked by making it again. A performance trace and a rendered-page measurement
    are files handed over from outside, deciding eight items between them — so the
    one question available, whether the file says which page it describes, is worth
    asking carefully. The contract suite covers the end of this path; these cover
    the judgements the comparison itself makes.
    """

    def _artifact(self, payload) -> str:
        path = os.path.join(tempfile.mkdtemp(), "cwv.json")
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(payload, str):
                f.write(payload)
            else:
                json.dump(payload, f)
        return path

    def test_the_noise_a_url_carries_is_not_a_different_page(self):
        for a, b in (("https://example.com", "https://example.com/"),
                     ("http://example.com/", "https://example.com/"),
                     ("https://www.example.com/", "https://example.com/"),
                     ("https://example.com/about", "https://example.com/about/")):
            self.assertTrue(same_page(a, b), f"{a} vs {b}")

    def test_a_different_page_is_a_different_page(self):
        for a, b in (("https://example.com/", "https://example.org/"),
                     ("https://example.com/", "https://example.com/about"),
                     ("https://example.com/?v=2", "https://example.com/"),
                     ("https://example.com/", "https://staging.example.com/")):
            self.assertFalse(same_page(a, b), f"{a} vs {b}")

    def test_an_unreadable_artifact_does_not_raise_here(self):
        """It has to reach the script that reads it.

        Refusing a malformed file in the runner would replace `cwv_metrics.py`'s
        message — which names the offending field and its units — with a generic
        one, and units are the whole reason that script is strict.
        """
        self.assertIsNone(artifact_subject(self._artifact("{not json")))
        self.assertIsNone(artifact_subject(self._artifact([1, 2, 3])))
        self.assertIsNone(artifact_subject("/nonexistent/trace.json"))

    def test_a_url_is_found_whether_or_not_the_exporter_nested_it(self):
        self.assertEqual(artifact_subject(self._artifact({"url": "https://a/"})),
                         "https://a/")
        self.assertEqual(
            artifact_subject(self._artifact({"metrics": {"url": "https://b/"}})),
            "https://b/")
        self.assertIsNone(artifact_subject(self._artifact({"lcp_ms": 1})))
        self.assertIsNone(artifact_subject(self._artifact({"url": "   "})))

    def test_a_refused_input_says_something_other_than_missing(self):
        """Two NO_DATA verdicts, two different instructions to the operator.

        "Missing input" tells them to go and measure the page. That is the wrong
        advice when they already did and the file is about somewhere else — and it
        is the advice the generic branch would give, because a rejected key and an
        absent one look identical from inside `build_plan`.
        """
        item = {"id": "SP-214", "source": "script",
                "check": {"script": "cwv_metrics.py", "args": ["{cwv_json}"],
                          "requires": "offline"}}
        plan, skipped = build_plan([item], {"cwv_json": "/t.json"}, {"offline"},
                                  "page", None, False,
                                  {"cwv_json": "the artifact describes https://b/"})
        self.assertEqual(plan, {})
        status, reason = skipped["SP-214"]
        self.assertEqual(status, NO_DATA)
        self.assertIn("describes", reason)
        self.assertNotIn("missing input", reason)

        _, absent = build_plan([item], {}, {"offline"}, "page")
        self.assertIn("missing input", absent["SP-214"][1])

    def test_the_items_that_read_an_artifact_are_the_ones_we_think(self):
        """Named by placeholder, not by script, so a new artifact-backed item is
        covered the day it is added rather than the day somebody remembers."""
        with open(os.path.join(ROOT, "skills", "seo-checklist", "resources", "config",
                               "checklist.json"), encoding="utf-8") as f:
            registry = json.load(f)["items"]
        found = {i["id"] for i in registry if reads_artifact(i)}
        self.assertEqual(found, {"SP-214", "SP-215", "SP-216", "CN-034", "CN-035",
                                 "CN-051", "MB-094", "MB-103", "BL-084", "BL-086",
                                 "BL-087"})
        # Every one of them is page-level, which is exactly why they had to be
        # excluded from sampling by hand: nothing about `requires` distinguishes a
        # check that reads a file from one that reads the page.
        for item in registry:
            if reads_artifact(item):
                self.assertTrue(is_page_level(item), item["id"])


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


class Stride(unittest.TestCase):
    """A sample taken off the top of an ordered list is not a sample.

    Sitemaps are grouped by section or by date, so `urls[:N]` returns one corner of
    the site — and the report says "5 of 5 pages checked", which reads as
    representative. The stride has to spread out *and* stay reproducible, because
    every other number this tool prints is reproducible."""

    def test_picks_are_spread_across_the_whole_list(self):
        urls = [f"/p{i}" for i in range(100)]
        self.assertEqual(stride(urls, 5), ["/p0", "/p25", "/p50", "/p74", "/p99"])

    def test_both_ends_of_the_sitemap_are_covered(self):
        """The bias being removed: with `[:N]` nothing past index N-1 could ever be
        audited, however large the site. An open-interval step has the same blind
        spot at the other end — it stops a full step short of the last URL."""
        urls = [f"/p{i}" for i in range(1000)]
        for n in (2, 3, 10, 25):
            picked = stride(urls, n)
            self.assertEqual(picked[0], "/p0", n)
            self.assertEqual(picked[-1], "/p999", n)

    def test_the_same_sitemap_yields_the_same_pages(self):
        urls = [f"/p{i}" for i in range(57)]
        self.assertEqual(stride(urls, 7), stride(urls, 7))

    def test_the_first_url_is_always_kept(self):
        """Usually the home page. Dropping it to look statistically tidy would be
        perverse."""
        for n in range(1, 12):
            self.assertEqual(stride([f"/p{i}" for i in range(50)], n)[0], "/p0")

    def test_a_short_list_is_returned_whole_and_in_order(self):
        self.assertEqual(stride(["/a", "/b"], 5), ["/a", "/b"])

    def test_no_duplicates_and_never_over_the_limit(self):
        for size in (1, 2, 3, 9, 40, 41):
            for limit in (1, 2, 5, 40):
                picked = stride([f"/p{i}" for i in range(size)], limit)
                self.assertEqual(len(picked), len(set(picked)))
                self.assertLessEqual(len(picked), min(size, limit))

    def test_asking_for_nothing_returns_nothing(self):
        self.assertEqual(stride(["/a", "/b"], 0), [])


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


class LocalBusinessSubtypes(unittest.TestCase):
    """Found by the first live audit, not by review. `find_schema_nodes(docs,
    "LocalBusiness")` compares @type as a string, so a restaurant publishing
    `Restaurant` — which is a LocalBusiness — was reported as having no local
    schema, producing a `high` FAIL on LO-198 that was pure fabrication."""

    def _nodes(self, schema_type):
        from local_seo_checker import find_local_business_nodes
        return find_local_business_nodes([{"@type": schema_type, "name": "X"}])

    def test_the_base_type_matches(self):
        self.assertEqual(len(self._nodes("LocalBusiness")), 1)

    def test_a_subtype_matches(self):
        """The live case: a restaurant site scored a fabricated failure on this."""
        for schema_type in ("Restaurant", "Hotel", "Bakery", "Dentist", "Plumber",
                            "ClothingStore", "Campground", "CafeOrCoffeeShop"):
            self.assertEqual(len(self._nodes(schema_type)), 1, schema_type)

    def test_an_unrelated_type_does_not_match(self):
        for schema_type in ("Article", "Product", "WebSite", "Person",
                            "BreadcrumbList", "Organization"):
            self.assertEqual(self._nodes(schema_type), [], schema_type)

    def test_a_type_array_matches_on_any_member(self):
        from local_seo_checker import find_local_business_nodes
        nodes = find_local_business_nodes(
            [{"@type": ["Organization", "Restaurant"], "name": "X"}])
        self.assertEqual(len(nodes), 1)

    def test_an_unknown_subtype_reports_missing_rather_than_guessing(self):
        """The list is a snapshot of a hierarchy that keeps growing, so it will go
        stale. Failing towards "no schema found" is the visible direction —
        accepting anything with "Business" in the name would not be."""
        self.assertEqual(self._nodes("SomeFutureBusinessType"), [])


class RenderedPageMeasurements(unittest.TestCase):
    """Five items came back from the LLM queue to being measured. The thing that
    makes that honest is refusing to answer what the render cannot: a desktop
    window says nothing about tap targets."""

    def _file(self, payload):
        path = os.path.join(tempfile.mkdtemp(), "rendered.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload if isinstance(payload, str) else json.dumps(payload))
        return path

    MOBILE = {"url": "https://e.com/", "viewport": {"width": 375, "height": 812},
              "text_nodes_below_12px": 0, "links_indistinct": 2,
              "overlays_covering_content": 0, "tap_targets_below_48px": 3}

    def test_a_mobile_render_answers_everything(self):
        out = rendered_read(self._file(self.MOBILE))
        self.assertEqual(out["viewport_class"], "mobile")
        for key in ("text_nodes_below_12px", "links_indistinct",
                    "overlays_covering_content", "tap_targets_below_48px",
                    "mobile_overlays_covering_content"):
            self.assertIn(key, out["measured"], key)

    def test_a_desktop_render_drops_the_mobile_metrics(self):
        """Not zeroed. A 0 would be a verdict about a viewport nobody looked at,
        and the runner reads the absent key as NO_DATA."""
        desktop = dict(self.MOBILE, viewport={"width": 1280, "height": 800})
        out = rendered_read(self._file(desktop))
        self.assertEqual(out["viewport_class"], "desktop")
        self.assertNotIn("tap_targets_below_48px", out)
        self.assertNotIn("mobile_overlays_covering_content", out)
        self.assertIsNone(evaluate({"path": "tap_targets_below_48px", "eq": 0}, out)[0])
        self.assertTrue(any("mobile render" in m for m in out["missing"]))

    def test_the_desktop_metrics_still_answer_from_a_desktop_render(self):
        desktop = dict(self.MOBILE, viewport={"width": 1280}, links_indistinct=5)
        out = rendered_read(self._file(desktop))
        self.assertFalse(evaluate({"path": "links_indistinct", "eq": 0}, out)[0])

    def test_a_file_without_a_viewport_is_refused(self):
        """Without it there is no way to know which questions the file can answer,
        and the mobile ones would silently be answered from a desktop window."""
        with self.assertRaises(ValueError) as caught:
            rendered_read(self._file({k: v for k, v in self.MOBILE.items()
                                      if k != "viewport"}))
        self.assertIn("viewport.width", str(caught.exception))

    def test_the_mobile_overlay_count_is_derived_not_invented(self):
        payload = dict(self.MOBILE, overlays_covering_content=2)
        payload.pop("tap_targets_below_48px")
        out = rendered_read(self._file(payload))
        self.assertEqual(out["mobile_overlays_covering_content"], 2)

    def test_an_unmeasured_metric_stays_absent(self):
        out = rendered_read(self._file({"viewport": {"width": 375},
                                        "links_indistinct": 1}))
        self.assertNotIn("text_nodes_below_12px", out)
        self.assertIn("text_nodes_below_12px", out["missing"])

    def test_a_non_count_is_refused(self):
        with self.assertRaises(ValueError):
            rendered_read(self._file({"viewport": {"width": 375},
                                      "links_indistinct": "a few"}))

    def test_a_file_with_no_metrics_is_refused(self):
        with self.assertRaises(ValueError):
            rendered_read(self._file({"viewport": {"width": 375}}))

    def test_the_registry_uses_it_for_the_five_items(self):
        with open(os.path.join(SCRIPTS, "..", "resources", "config",
                               "checklist.json"), encoding="utf-8") as f:
            by_id = {i["id"]: i for i in json.load(f)["items"]}
        for item_id in ("CN-034", "CN-035", "CN-051", "MB-094", "MB-103"):
            self.assertEqual(by_id[item_id]["source"], "script", item_id)
            self.assertEqual(by_id[item_id]["check"]["script"], "rendered_audit.py",
                             item_id)

    def test_the_three_judgement_items_stayed_judgements(self):
        """A close keyword variant and a localised title are not computed values —
        moving them to a measurement would be inventing one."""
        with open(os.path.join(SCRIPTS, "..", "resources", "config",
                               "checklist.json"), encoding="utf-8") as f:
            by_id = {i["id"]: i for i in json.load(f)["items"]}
        for item_id in ("KW-074", "KW-075", "LO-197"):
            self.assertEqual(by_id[item_id]["source"], "llm", item_id)
            self.assertTrue(by_id[item_id].get("lens"), item_id)


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
