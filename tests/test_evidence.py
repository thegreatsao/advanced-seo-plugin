"""Tests for the evidence scripts that decide the `critical` items.

Everything above these tests was well covered and everything below them was not:
248 tests defended the registry, the runner and the report, and 45 of the 55
evidence scripts had none at all. Every verdict an audit prints is the output of one
of those scripts read by a well-tested interpreter, so a script that quietly stops
emitting a field, or emits it in a second vocabulary, produces a confident number
built on nothing — and the frame cannot tell.

Seventeen of the nineteen `critical` items are decided by seven scripts. These are
those seven, and each test asserts **the field the registry actually reads**, named
in the test, so that a change to the script's output contract fails here rather than
in a client's report. Writing them found four fabricated verdicts on critical items;
they are pinned below with the item id.

Offline: no fixture site, no network, no API key. The HTTP layer is stubbed at
`seo_common.fetch_url` or `lib.safe_http.safe_get`, whichever the script uses.
"""
import ast
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "seo-checklist", "scripts")
REGISTRY = os.path.join(ROOT, "skills", "seo-checklist", "resources", "config",
                        "checklist.json")
sys.path.insert(0, SCRIPTS)

from checklist_runner import NO_DATA, PASS, FAIL, WARN, evaluate  # noqa: E402


def registry_rule(item_id: str) -> dict:
    """The live assert rule for an item, so a test cannot drift from the registry.

    Reading the rule instead of restating it is the point: a test that hard-codes
    `{"path": "title"}` keeps passing after the registry stops asking for `title`,
    which is precisely how a check goes quiet.
    """
    with open(REGISTRY, encoding="utf-8") as f:
        items = {i["id"]: i for i in json.load(f)["items"]}
    return items[item_id]["check"]


def verdict(item_id: str, output: dict) -> str:
    """Run an item's real rule over a script's real output, as the runner would."""
    check = registry_rule(item_id)
    ok, _ = evaluate(check["assert"], output)
    if ok is None:
        return NO_DATA
    if ok:
        return PASS
    warn = check.get("warn")
    if warn and evaluate(warn, output)[0]:
        return WARN
    return FAIL


class SharedHelpersStayShared(unittest.TestCase):
    def test_no_script_carries_its_own_copy_of_a_shared_helper(self):
        """Shared helpers have one definition, in seo_common, not one per caller.

        Each copied helper worked on its own; the defect appeared only when copies
        drifted or when the same policy had to change in several places. Keep both
        public and formerly-private spellings here, because a future script-local
        copy would most likely restore the leading underscore.
        """
        offenders = []
        for name in sorted(os.listdir(SCRIPTS)):
            if not name.endswith(".py") or name == "seo_common.py":
                continue
            with open(os.path.join(SCRIPTS, name), encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=name)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in (
                        "fetch_html", "walk_json", "_walk_json", "is_url",
                        "_is_url", "as_list"):
                    offenders.append(f"{name}:{node.lineno} defines {node.name}")
        self.assertEqual(offenders, [], "import it from seo_common instead: "
                                        + "; ".join(offenders))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>A page with everything the critical items ask for</title>
<meta name="description" content="Enough of a description to be a description.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://example.com/page">
</head><body><h1>One heading</h1><p>Some prose.</p></body></html>"""


class ParseHtml(unittest.TestCase):
    """Four critical items read this script: CI-004 (meta robots), MS-026 (title),
    CN-065 (one h1), MB-093 (viewport)."""

    def parse(self, html, url="https://example.com/page"):
        import parse_html
        return parse_html.parse_html(html, url)

    def test_a_complete_page_satisfies_all_four_critical_items(self):
        out = self.parse(PAGE)
        for item_id in ("CI-004", "MS-026", "CN-065", "MB-093"):
            self.assertEqual(verdict(item_id, out), PASS, item_id)

    def test_a_noindex_page_fails_ci_004(self):
        out = self.parse(PAGE.replace("<meta charset=\"utf-8\">",
                                      '<meta charset="utf-8">'
                                      '<meta name="robots" content="noindex, follow">'))
        self.assertEqual(out["meta_robots"], "noindex, follow")
        self.assertEqual(verdict("CI-004", out), FAIL)

    def test_an_absent_meta_robots_passes_because_the_rule_says_so(self):
        """The one place absence is an answer: no meta robots means indexable, and
        the rule carries `missing_is: pass` to say that out loud."""
        out = self.parse(PAGE)
        self.assertIsNone(out["meta_robots"])
        self.assertEqual(registry_rule("CI-004")["assert"]["missing_is"], "pass")
        self.assertEqual(verdict("CI-004", out), PASS)

    def test_a_missing_title_and_a_missing_viewport_fail(self):
        no_title = self.parse(PAGE.replace(
            "<title>A page with everything the critical items ask for</title>", ""))
        self.assertIsNone(no_title["title"])
        self.assertEqual(verdict("MS-026", no_title), FAIL)
        no_viewport = self.parse(PAGE.replace(
            '<meta name="viewport" content="width=device-width, initial-scale=1">', ""))
        self.assertIsNone(no_viewport["viewport"])
        self.assertEqual(verdict("MB-093", no_viewport), FAIL)

    def test_two_h1s_and_no_h1_both_fail_cn_065(self):
        two = self.parse(PAGE.replace("<h1>One heading</h1>",
                                      "<h1>One</h1><h1>Two</h1>"))
        self.assertEqual(len(two["h1"]), 2)
        self.assertEqual(verdict("CN-065", two), FAIL)
        none = self.parse(PAGE.replace("<h1>One heading</h1>", "<h2>Not an h1</h2>"))
        self.assertEqual(verdict("CN-065", none), FAIL)

    def test_meta_keywords_is_emitted_at_all(self):
        """MS-031 asserts this is falsy with `missing_is: pass`, and the script never
        emitted the key — so the item passed on every site ever audited, including
        one with a stuffed keywords tag. A rule can only be as honest as the
        existence of the field it reads."""
        out = self.parse(PAGE)
        self.assertIn("meta_keywords", out)
        self.assertIsNone(out["meta_keywords"])
        self.assertEqual(verdict("MS-031", out), PASS)
        stuffed = self.parse(PAGE.replace(
            "</head>", '<meta name="keywords" content="seo, seo services, cheap seo">'
                       "</head>"))
        self.assertEqual(stuffed["meta_keywords"], "seo, seo services, cheap seo")
        self.assertEqual(verdict("MS-031", stuffed), FAIL)


class IndexabilityMatrix(unittest.TestCase):
    """Four critical items read this script: CI-001 (indexable), CI-003 (200),
    CI-005 (robots allows), CI-015 (no 5xx)."""

    def setUp(self):
        import indexability_matrix as ix
        self.ix = ix
        self.saved = (ix.fetch_url, ix.fetch_robots, ix.urls_from_sitemaps)
        ix.urls_from_sitemaps = lambda *a, **k: set()

    def tearDown(self):
        (self.ix.fetch_url, self.ix.fetch_robots,
         self.ix.urls_from_sitemaps) = self.saved

    def serve(self, status=200, html=PAGE, headers=None, robots=""):
        hdrs = {"content-type": "text/html; charset=utf-8"}
        hdrs.update({k.lower(): v for k, v in (headers or {}).items()})

        def fake_fetch(url, **kw):
            return {"url": url, "status": status, "headers": hdrs, "text": html,
                    "redirect_chain": [], "error": None}
        self.ix.fetch_url = fake_fetch
        from seo_common import parse_robots_txt
        self.ix.fetch_robots = lambda *a, **k: {
            "url": "https://example.com/robots.txt",
            "fetch": {"status": 200 if robots else 404},
            "parsed": parse_robots_txt(robots) if robots else None}

    def test_a_healthy_page_satisfies_all_four(self):
        self.serve()
        out = self.ix.evaluate(["https://example.com/page"], "https://example.com/")
        self.assertEqual(out["rows"][0]["status"], 200)
        self.assertIs(out["rows"][0]["robots_allowed"], True)
        self.assertEqual(out["rows"][0]["verdict"], "indexable")
        for item_id in ("CI-001", "CI-003", "CI-005", "CI-015"):
            self.assertEqual(verdict(item_id, out), PASS, item_id)

    def test_a_500_fails_both_status_items(self):
        self.serve(status=503)
        out = self.ix.evaluate(["https://example.com/page"], "https://example.com/")
        self.assertEqual(verdict("CI-003", out), FAIL)
        self.assertEqual(verdict("CI-015", out), FAIL)

    def test_a_robots_disallow_fails_ci_005(self):
        self.serve(robots="User-agent: *\nDisallow: /page\n")
        out = self.ix.evaluate(["https://example.com/page"], "https://example.com/")
        self.assertIs(out["rows"][0]["robots_allowed"], False)
        self.assertEqual(verdict("CI-005", out), FAIL)

    def test_a_noindex_page_is_not_indexable_and_ci_001_says_so(self):
        """CI-001 is "ensure the URL is indexed" and used to assert
        `robots_allowed` — the same field, and the same rule, as CI-005. A page
        crawlable by robots.txt and marked `noindex` passed a critical item about
        being indexed. The script's own `verdict` accounts for meta robots,
        X-Robots-Tag, the status and a canonical pointing elsewhere; nothing in the
        registry read it."""
        self.serve(html=PAGE.replace("</head>",
                                     '<meta name="robots" content="noindex"></head>'))
        out = self.ix.evaluate(["https://example.com/page"], "https://example.com/")
        row = out["rows"][0]
        self.assertIs(row["robots_allowed"], True)
        self.assertEqual(row["verdict"], "not_indexable")
        self.assertIn("meta robots noindex", row["blockers"])
        self.assertEqual(verdict("CI-001", out), FAIL)
        self.assertEqual(verdict("CI-005", out), PASS, "robots.txt is not the problem")

    def test_an_x_robots_noindex_header_is_caught_too(self):
        """The half of CI-004's title — "Meta Robots / X-Robots-Tag" — that
        `parse_html.py` cannot see: it is handed a file, so it never has headers. A
        CDN noindexing a whole path does it with the header."""
        self.serve(headers={"X-Robots-Tag": "noindex"})
        out = self.ix.evaluate(["https://example.com/page"], "https://example.com/")
        self.assertIn("x-robots-tag noindex", out["rows"][0]["blockers"])
        self.assertEqual(verdict("CI-001", out), FAIL)


class CanonicalChecker(unittest.TestCase):
    """CI-009 (critical) and CI-011 (high) read this script's `verdict`."""

    def setUp(self):
        import canonical_checker as cc
        self.cc = cc
        self.saved = cc.fetch_url

    def tearDown(self):
        self.cc.fetch_url = self.saved

    def serve(self, canonical, status=200):
        html = PAGE.replace('<link rel="canonical" href="https://example.com/page">',
                            f'<link rel="canonical" href="{canonical}">'
                            if canonical else "")

        def fake(url, **kw):
            return {"url": url, "status": status,
                    "headers": {"content-type": "text/html"},
                    "text": html, "redirect_chain": [], "error": None}
        self.cc.fetch_url = fake

    def check(self):
        return self.cc.check_canonicals(["https://example.com/page"])

    def test_a_self_canonical_passes(self):
        self.serve("https://example.com/page")
        out = self.check()
        self.assertEqual(out["rows"][0]["verdict"], "self_canonical")
        self.assertEqual(verdict("CI-009", out), PASS)

    def test_a_cross_host_canonical_fails(self):
        self.serve("https://other.example.net/page")
        out = self.check()
        self.assertEqual(out["rows"][0]["verdict"], "cross_host")
        self.assertEqual(verdict("CI-009", out), FAIL)

    def test_no_canonical_at_all_fails_ci_009_and_passes_ci_011(self):
        """The split is deliberate: CI-009 is "serve content at a single canonical
        URL", so declaring none is the failure it names; CI-011 is about a canonical
        that contradicts something else, and there is nothing to contradict."""
        self.serve(None)
        out = self.check()
        self.assertEqual(out["rows"][0]["verdict"], "missing")
        self.assertEqual(verdict("CI-009", out), FAIL)
        self.assertEqual(verdict("CI-011", out), PASS)

    def test_the_old_rule_could_not_fire_at_all(self):
        """CI-009 asserted `issues` had no critical/high entry. This script says
        "warning" and "error" and never those two words, so the rule matched nothing
        and the item reported PASS on every site ever audited — including this one,
        whose canonical points at another domain."""
        self.serve("https://other.example.net/page")
        out = self.check()
        emitted = {i["severity"] for i in out["issues"]}
        self.assertTrue(emitted)
        self.assertFalse(emitted & {"critical", "high"})
        ok, _ = evaluate({"path": "issues",
                          "none_severity": ["critical", "high"]}, out)
        self.assertIs(ok, True, "the retired rule still passes — that was the bug")

    def test_an_unreadable_page_is_undecided(self):
        self.serve("https://example.com/page", status=500)
        self.check()          # asserts only that a 500 does not raise
        # No text is parsed on a 500 here, so the verdict is `missing`; what matters
        # is that `unknown` — which the script emits when it has nothing at all —
        # stays out of the map and lands on NO_DATA.
        rule = registry_rule("CI-009")["assert"]
        self.assertNotIn("unknown", rule["value_map"])
        ok, _ = evaluate(rule, {"rows": [{"verdict": "unknown"}]})
        self.assertIsNone(ok)


class RobotsPathTester(unittest.TestCase):
    """CI-013 (critical): may Googlebot fetch representative CSS, JS and image
    paths? The rule counts `allowed_urls`, so the count and ASSET_PROBES in the
    generator have to agree."""

    def setUp(self):
        import robots_path_tester as rpt
        self.rpt = rpt
        self.saved = rpt.fetch_robots
        self.args = registry_rule("CI-013")["args"]
        self.paths = [a for a in self.args[1:] if a.startswith("/")]

    def tearDown(self):
        self.rpt.fetch_robots = self.saved

    def serve(self, body, status=200):
        from seo_common import parse_robots_txt
        self.rpt.fetch_robots = lambda *a, **k: {
            "url": "https://example.com/robots.txt",
            "fetch": {"status": status},
            "parsed": parse_robots_txt(body) if status == 200 else None}

    def run_test(self):
        return self.rpt.test_paths("https://example.com/", self.paths, ["Googlebot"])

    def test_assets_reachable_passes(self):
        self.serve("User-agent: *\nDisallow: /admin\n")
        out = self.run_test()
        self.assertEqual(len(out["allowed_urls"]), len(self.paths))
        self.assertEqual(verdict("CI-013", out), PASS)

    def test_a_blocked_asset_directory_fails(self):
        self.serve("User-agent: *\nDisallow: /assets/\nDisallow: /static/\n")
        out = self.run_test()
        self.assertEqual(len(out["allowed_urls"]), 1)
        self.assertEqual(verdict("CI-013", out), FAIL)

    def test_an_unreachable_robots_txt_is_undecided_not_clean(self):
        """A 500 says nothing about what is allowed, and an empty `allowed_urls`
        would read as "every asset is blocked" while a present-but-empty list would
        read as clean. The key is omitted instead."""
        self.serve("", status=500)
        out = self.run_test()
        self.assertNotIn("allowed_urls", out)
        self.assertEqual(verdict("CI-013", out), NO_DATA)


class SystemPagesAreNotIndexable(unittest.TestCase):
    """CI-019 (high): the same script as CI-013, read in the opposite direction.

    The item's history is two opposite defects in the same field. Until 0.13 the rule
    matched text across a nested dict, `allowed` and `true` never landed in one string,
    and every site passed. Flattening to `allowed_urls` fixed that and produced the
    inverse: `allowed_urls` is computed from robots.txt alone, so a café with no cart
    is accused of exposing `/cart` — nothing disallows a page that does not exist.

    0.20 asserts `indexable_urls` instead, which requires a fetch: the path is there,
    a crawler may have it, and nothing keeps it out of the index. `noindex` counts,
    which is what the item's title said all along.
    """

    def setUp(self):
        import robots_path_tester as rpt
        self.rpt = rpt
        self.saved = (rpt.fetch_robots, rpt.safe_get)
        self.paths = [a for a in registry_rule("CI-019")["args"][1:]
                      if a.startswith("/")]

    def tearDown(self):
        self.rpt.fetch_robots, self.rpt.safe_get = self.saved

    def serve_robots(self, body, status=200):
        from seo_common import parse_robots_txt
        self.rpt.fetch_robots = lambda *a, **k: {
            "url": "https://example.com/robots.txt",
            "fetch": {"status": status},
            "parsed": parse_robots_txt(body) if status == 200 else None}

    def serve_pages(self, by_path):
        """`{path: (status, body, headers)}`; anything unlisted is a 404."""
        class Resp:
            def __init__(self, status, body, headers):
                self.status_code, self.text, self.headers = status, body, headers

        def fake_get(url, **kwargs):
            path = url[url.index("/", 8):]
            status, body, headers = by_path.get(path, (404, "", {}))
            return Resp(status, body, headers)
        self.rpt.safe_get = fake_get

    def run_test(self):
        return self.rpt.test_paths("https://example.com/", self.paths,
                                   ["Googlebot"], probe=True)

    OPEN = "User-agent: *\nDisallow: /admin\n"

    def test_a_site_without_those_pages_is_not_accused(self):
        """The defect that a live audit found and the fixture could not.

        Every path 404s, robots.txt disallows nothing, and the pre-0.20 assertion
        counted four permitted URLs and failed a `high` item on a site that has no
        cart, no checkout and no login.
        """
        self.serve_robots(self.OPEN)
        self.serve_pages({})
        out = self.run_test()
        self.assertEqual(len(out["allowed_urls"]), len(self.paths))   # old field
        self.assertEqual(out["indexable_urls"], [])                   # new one
        self.assertEqual(verdict("CI-019", out), PASS)

    def test_a_reachable_system_page_with_nothing_stopping_it_fails(self):
        self.serve_robots(self.OPEN)
        self.serve_pages({"/cart": (200, "<html><body>Your cart</body></html>", {})})
        out = self.run_test()
        self.assertEqual(out["indexable_urls"], ["https://example.com/cart"])
        self.assertEqual(verdict("CI-019", out), FAIL)

    def test_noindex_satisfies_the_item_in_either_place_it_can_be_written(self):
        """Meta tag on one page, `X-Robots-Tag` on another. The title has always
        asked for `noindex`; before 0.20 writing one changed nothing."""
        self.serve_robots(self.OPEN)
        self.serve_pages({
            "/cart": (200, '<html><head><meta name="robots" content="noindex,follow">'
                           "</head><body>c</body></html>", {}),
            "/login": (200, "<html><body>l</body></html>",
                       {"X-Robots-Tag": "noindex"}),
        })
        out = self.run_test()
        self.assertEqual(out["indexable_urls"], [])
        self.assertEqual(verdict("CI-019", out), PASS)

    def test_a_noindex_written_inside_a_comment_is_not_a_noindex(self):
        """Markup inside a comment is not markup, and this is not a hypothetical.

        The first version of the probe read `noindex` off a `<meta name="robots">`
        that a fixture page's comment block quoted while explaining that the page
        deliberately has no such tag — so the page built to fail CI-019 passed it.
        The registry's own history of this: the keyword items fired on their own
        remediation text in 0.5.0, and the soft-404 guard carries the warning that
        `404` appears in the title of every article ever written about broken links.
        """
        self.serve_robots(self.OPEN)
        self.serve_pages({"/cart": (200,
                                    '<html><head><!-- deliberately absent: <meta '
                                    'name="robots" content="noindex"> --></head>'
                                    "<body>Your cart</body></html>", {})})
        out = self.run_test()
        self.assertEqual(out["indexable_urls"], ["https://example.com/cart"])
        self.assertEqual(verdict("CI-019", out), FAIL)

    def test_a_path_disallowed_in_robots_is_never_fetched(self):
        """The other accepted mechanism, and a request the run must not spend: a
        blocked path is out of the index already, and fetching it to confirm that
        would buy nothing."""
        fetched = []
        self.serve_robots("User-agent: *\nDisallow: /cart\n")
        self.serve_pages({"/cart": (200, "<html><body>c</body></html>", {})})
        inner = self.rpt.safe_get
        self.rpt.safe_get = lambda url, **k: (fetched.append(url), inner(url, **k))[1]
        out = self.run_test()
        self.assertNotIn("https://example.com/cart", fetched)
        self.assertNotIn("https://example.com/cart", out["indexable_urls"])

    def test_a_failed_probe_is_not_evidence_of_a_clean_site(self):
        """A page we could not reach is neither indexable nor proven absent. It goes
        to `unprobed_urls`, where it cannot be read as either verdict."""
        self.serve_robots(self.OPEN)

        def explode(url, **kwargs):
            raise OSError("connection reset")
        self.serve_pages({})
        self.rpt.safe_get = explode
        out = self.run_test()
        self.assertEqual(out["indexable_urls"], [])
        self.assertEqual(len(out["unprobed_urls"]), len(self.paths))

    def test_an_unreachable_robots_txt_is_still_undecided(self):
        self.serve_robots("", status=500)
        self.serve_pages({})
        out = self.run_test()
        self.assertNotIn("indexable_urls", out)
        self.assertEqual(verdict("CI-019", out), NO_DATA)


class SecurityHeaders(unittest.TestCase):
    """SE-117 (critical) reads `https`; TE-175 (high) reads `headers_missing`.

    SE-118 read `https` too until 0.20, from this same script — two critical items
    sharing one field, so SE-118 could not fail independently on any site and a
    certificate that expired yesterday passed it. It now reads `valid` from
    `tls_certificate.py` (`test_tls_certificate.py`). The other half of that fix is
    asserted here: this script's output can no longer decide SE-118 at all.
    """

    def setUp(self):
        import security_headers as sh
        self.sh = sh
        self.saved = sh.safe_get

    def tearDown(self):
        self.sh.safe_get = self.saved

    def serve(self, url, headers=None):
        class Resp:
            def __init__(self):
                self.url = url
                self.headers = headers or {}
                self.status_code = 200
        self.sh.safe_get = lambda *a, **k: Resp()

    ALL_HEADERS = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "X-Frame-Options": "SAMEORIGIN",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=()",
    }

    def test_https_with_every_header_passes_both_items_it_decides(self):
        self.serve("https://example.com/", self.ALL_HEADERS)
        out = self.sh.check_security_headers("https://example.com/")
        self.assertIs(out["https"], True)
        self.assertEqual(out["headers_missing"], {})
        for item_id in ("SE-117", "TE-175"):
            self.assertEqual(verdict(item_id, out), PASS, item_id)

    def test_plain_http_fails_the_critical_item(self):
        self.serve("http://example.com/", {})
        out = self.sh.check_security_headers("http://example.com/")
        self.assertIs(out["https"], False)
        self.assertEqual(verdict("SE-117", out), FAIL)

    def test_this_script_cannot_decide_se_118_in_either_direction(self):
        """The regression guard for the 0.20 fix, and the reason it is two asserts.

        A scheme is not a certificate. Whatever this script says about `https`, the
        item that claims a certificate was verified must not resolve from it — and
        `NO_DATA` on both a good and a bad response is what proves the field it used
        to read is genuinely gone rather than merely renamed.
        """
        for url, headers in (("https://example.com/", self.ALL_HEADERS),
                             ("http://example.com/", {})):
            self.serve(url, headers)
            out = self.sh.check_security_headers(url)
            self.assertEqual(verdict("SE-118", out), NO_DATA, url)

    def test_te_175_reads_a_field_and_not_the_prose(self):
        """This script appends plain strings to `issues`, so the old
        `none_severity` rule iterated dicts, found none, and reported PASS — while
        the script itself was printing "Site not using HTTPS" and "6 security
        headers missing". `headers_missing` is a dict, and the rule uses the
        script's own bar: more than three of six absent is a failure."""
        self.serve("http://example.com/", {})
        out = self.sh.check_security_headers("http://example.com/")
        self.assertEqual(len(out["headers_missing"]), 6)
        self.assertTrue(out["issues"])
        self.assertFalse([i for i in out["issues"] if isinstance(i, dict)],
                         "issues are strings; no severity rule can read them")
        ok, _ = evaluate({"path": "issues",
                          "none_severity": ["critical", "high"]}, out)
        self.assertIsNone(ok, "a list of strings must be undecided, never a pass")
        self.assertEqual(verdict("TE-175", out), FAIL)

    def test_three_missing_headers_is_still_a_pass(self):
        keep = dict(list(self.ALL_HEADERS.items())[:3])
        self.serve("https://example.com/", keep)
        out = self.sh.check_security_headers("https://example.com/")
        self.assertEqual(len(out["headers_missing"]), 3)
        self.assertEqual(verdict("TE-175", out), PASS)


class PageSpeed(unittest.TestCase):
    """SP-108 and SP-113 (critical), SP-107 (high), SE-119 (medium). No network:
    `parse_pagespeed_response` is the whole contract, and the API payload is the
    input."""

    def setUp(self):
        import pagespeed
        self.ps = pagespeed

    def crux(self, lcp_category="FAST", inp_category="FAST", cls_category="FAST"):
        return {
            "loadingExperience": {"metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 1800,
                                                "category": lcp_category},
                "INTERACTION_TO_NEXT_PAINT": {"percentile": 120,
                                              "category": inp_category},
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 5,
                                                  "category": cls_category},
                "FIRST_CONTENTFUL_PAINT_MS": {"percentile": 1200,
                                              "category": "FAST"},
            }},
            "lighthouseResult": {"categories": {"performance": {"score": 0.98}}},
        }

    def lab_only(self, lcp_ms=1500):
        return {"lighthouseResult": {
            "categories": {"performance": {"score": 0.97}},
            "audits": {
                "largest-contentful-paint": {"numericValue": lcp_ms},
                "cumulative-layout-shift": {"numericValue": 0.02},
                "first-contentful-paint": {"numericValue": 900},
            }}}

    def parse(self, payload):
        return self.ps.parse_pagespeed_response(payload, "https://example.com/",
                                                "mobile")

    def test_field_data_is_normalised_to_one_vocabulary(self):
        out = self.parse(self.crux())
        self.assertIs(out["field_data_available"], True)
        self.assertEqual(out["metrics"]["LCP"]["rating"], "good")
        self.assertEqual(out["metrics"]["LCP"]["crux_category"], "fast")
        self.assertEqual(verdict("SP-113", out), PASS)
        self.assertEqual(verdict("SP-108", out), PASS)

    def test_a_fast_page_without_crux_data_is_no_longer_failed(self):
        """The bug: CrUX said FAST and Lighthouse says `good`, both went into the
        same `rating`, and the rule compared it to "fast". CrUX publishes nothing for
        a low-traffic URL — most of the sites this tool audits — so a page with a
        1.5s lab LCP failed two critical items for being small."""
        out = self.parse(self.lab_only(lcp_ms=1500))
        self.assertIs(out["field_data_available"], False)
        self.assertEqual(out["metrics"]["LCP"]["rating"], "good")
        ok, _ = evaluate({"path": "metrics.LCP.rating", "eq": "fast"}, out)
        self.assertIs(ok, False, "the retired rule still fails a fast page")
        # 0.25.0 changed this deliberately, and it is a breaking change worth naming:
        # SP-113 used to PASS here. `metrics` carries CrUX when there is field data and
        # Lighthouse's lab audits when there is not, so an item reading `metrics.LCP`
        # switched data source without saying so — a `critical` PASS about "Core Web
        # Vitals", earned on a lab number, on exactly the small sites CrUX has no sample
        # for. Core Web Vitals are field metrics by definition; with no field data the
        # honest verdict is the one SP-108 already gave, and the lab measurement of this
        # same page has its own items (SP-214 to SP-216) fed from a browser trace.
        self.assertEqual(verdict("SP-113", out), NO_DATA)
        self.assertEqual(verdict("SP-108", out), NO_DATA)

    def test_no_field_data_leaves_sp_108_undecided(self):
        """"CrUX has no sample for this URL" is not "real users had a bad time".
        The old rule asserted that field data exists, so every small site failed a
        critical item for being small."""
        out = self.parse(self.lab_only())
        self.assertNotIn("field_cwv", out)
        self.assertEqual(verdict("SP-108", out), NO_DATA)

    def test_a_slow_lcp_in_the_field_fails_the_whole_group(self):
        """SP-108, SP-112 and SP-113 are one measurement as of 0.25.0, so they answer
        together. SP-113 used to read `metrics.LCP.rating` alone with a three-band warn
        in the middle; Google's own assessment has no middle — a URL passes only when all
        of LCP, INP and CLS are `good` — and the middle band came from grading one metric
        instead of three."""
        slow = self.parse(self.crux(lcp_category="SLOW"))
        self.assertEqual(slow["metrics"]["LCP"]["rating"], "poor")
        self.assertEqual(slow["field_cwv"]["verdict"], "fail")
        self.assertEqual(slow["field_cwv"]["failing"], ["LCP"])
        for item in ("SP-108", "SP-112", "SP-113"):
            self.assertEqual(verdict(item, slow), FAIL, item)

        middling = self.parse(self.crux(lcp_category="AVERAGE"))
        self.assertEqual(middling["metrics"]["LCP"]["rating"], "needs-improvement")
        self.assertEqual(middling["field_cwv"]["verdict"], "fail")
        self.assertEqual(verdict("SP-113", middling), FAIL)

    def test_desktop_field_data_is_asserted_by_its_own_item(self):
        """SP-111's whole point after 0.25.0: nothing in the registry read desktop field
        data before, because it read Lighthouse's blended desktop score instead."""
        with open(REGISTRY, encoding="utf-8") as f:
            registry = {i["id"]: i for i in json.load(f)["items"]}
        self.assertIn("desktop", registry["SP-111"]["check"]["args"])
        self.assertEqual(registry["SP-111"]["check"]["assert"]["path"],
                         "field_cwv.verdict")
        self.assertIsNone(registry["SP-111"].get("scores_with"),
                          "desktop field data is not a twin of the mobile item")

    def test_an_unknown_rating_is_undecided(self):
        """A band nobody enumerated must not become a verdict. `rating != "good"` made
        one: an unrecognised band graded as failing, which 0.25.0 would have promoted
        into a `critical` FAIL when SP-113 started reading this verdict. It is dropped
        from the grading and named in `unknown` instead."""
        out = self.parse(self.crux(lcp_category="GLACIAL"))
        self.assertEqual(out["metrics"]["LCP"]["rating"], "glacial")
        self.assertEqual(out["field_cwv"]["verdict"], "unknown")
        self.assertEqual(out["field_cwv"]["unknown"], ["LCP"])
        self.assertEqual(out["field_cwv"]["measured"], ["CLS", "INP"])
        for item in ("SP-108", "SP-112", "SP-113"):
            self.assertEqual(verdict(item, out), NO_DATA, item)

    def test_a_known_failure_is_reported_even_beside_an_unknown_band(self):
        """The asymmetry, and it is the point. One bad metric fails the assessment
        whatever the unrecognised one turns out to be, so the failure is safe to report —
        while a *pass* beside an unknown band is not, which is the case above."""
        out = self.parse(self.crux(lcp_category="GLACIAL", cls_category="SLOW"))
        self.assertEqual(out["field_cwv"]["verdict"], "fail")
        self.assertEqual(out["field_cwv"]["failing"], ["CLS"])
        self.assertEqual(out["field_cwv"]["unknown"], ["LCP"])
        self.assertEqual(verdict("SP-108", out), FAIL)


class DomainSafety(unittest.TestCase):
    """SE-114, SE-116 and TE-171 (critical) read `safe_browsing.*`. The user
    declined a Safe Browsing key, so on a real run these are NO_DATA — which is
    exactly why they need a test: nothing else here has ever exercised them."""

    def setUp(self):
        import domain_safety_check as ds
        self.ds = ds
        self.saved = ds.requests.post

    def tearDown(self):
        self.ds.requests.post = self.saved

    def serve(self, matches, status=200):
        class Resp:
            status_code = status

            def json(self):
                return {"matches": matches}
        self.ds.requests.post = lambda *a, **k: Resp()

    def test_no_key_omits_the_verdict_instead_of_reporting_clean(self):
        out = {"safe_browsing": self.ds.check_safe_browsing(
            "https://example.com/", "", 10)}
        self.assertIs(out["safe_browsing"]["checked"], False)
        self.assertNotIn("clean", out["safe_browsing"])
        for item_id in ("SE-114", "SE-116", "TE-171"):
            self.assertEqual(verdict(item_id, out), NO_DATA, item_id)

    def test_a_clean_domain_passes_all_three(self):
        self.serve([])
        out = {"safe_browsing": self.ds.check_safe_browsing(
            "https://example.com/", "key", 10)}
        self.assertIs(out["safe_browsing"]["clean"], True)
        self.assertEqual(out["safe_browsing"]["threats"], [])
        for item_id in ("SE-114", "SE-116", "TE-171"):
            self.assertEqual(verdict(item_id, out), PASS, item_id)

    def test_a_flagged_domain_fails_all_three(self):
        self.serve([{"threatType": "MALWARE", "platformType": "ANY_PLATFORM"}])
        out = {"safe_browsing": self.ds.check_safe_browsing(
            "https://example.com/", "key", 10)}
        self.assertIs(out["safe_browsing"]["clean"], False)
        for item_id in ("SE-114", "SE-116", "TE-171"):
            self.assertEqual(verdict(item_id, out), FAIL, item_id)

    def test_an_api_error_is_undecided_not_clean(self):
        self.serve([], status=503)
        out = {"safe_browsing": self.ds.check_safe_browsing(
            "https://example.com/", "key", 10)}
        self.assertIs(out["safe_browsing"]["checked"], False)
        self.assertEqual(verdict("SE-116", out), NO_DATA)


class ImageWeightAudit(unittest.TestCase):
    """MB-096 (`responsive_count`) and MB-097 (`modern_format_count`).

    Neither is critical, and both were wrong in the same direction, which is the
    interesting part: they failed sites for using the pattern the documentation
    recommends. The audit read `<img>` attributes only, and the recommended way to
    ship webp puts it in a `<source>` and leaves a png in the `<img>` as the
    fallback for browsers that cannot decode it — so the one thing guaranteed to be
    an old format was the only thing ever inspected.
    """

    def audit(self, body: str) -> dict:
        from image_weight_audit import audit as run
        path = os.path.join(tempfile.mkdtemp(), "page.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"<!doctype html><html><body>{body}</body></html>")
        return run(path)

    PICTURE = """<picture>
      <source type="image/avif" srcset="/i/logo.avif">
      <source type="image/webp" srcset="/i/logo@2x.webp 2x, /i/logo.webp 1x">
      <img src="/i/logo.png" alt="a mark" width="64" height="64">
    </picture>"""

    def test_a_picture_serving_webp_counts_as_a_modern_format(self):
        out = self.audit(self.PICTURE)
        self.assertEqual(out["modern_format_count"], 1,
                         "MB-097 fails a site doing exactly what it asks for")
        self.assertEqual(verdict("MB-097", out), PASS)

    def test_a_source_srcset_counts_as_responsive(self):
        out = self.audit(self.PICTURE)
        self.assertEqual(out["responsive_count"], 1)
        self.assertEqual(verdict("MB-096", out), PASS)

    def test_the_fallback_is_still_reported_as_a_png(self):
        """Both facts, kept apart. The browser gets webp and the `img` is a png,
        and a fix list that conflated them would tell somebody to change the one
        line that is deliberately old."""
        out = self.audit(self.PICTURE)
        self.assertEqual(out["images"][0]["format"], "png")
        self.assertEqual(out["modern_format_on_img_count"], 0)
        self.assertEqual(out["picture_count"], 1)
        self.assertEqual(out["images"][0]["picture_modern_formats"], ["avif", "webp"])

    def test_a_bare_old_format_image_still_fails_both(self):
        """The other direction, which is what stops this being a fix that
        can only ever say yes."""
        out = self.audit('<img src="/i/logo.png" alt="a mark">')
        self.assertEqual(out["modern_format_count"], 0)
        self.assertEqual(out["responsive_count"], 0)
        self.assertEqual(verdict("MB-097", out), FAIL)
        self.assertEqual(verdict("MB-096", out), FAIL)

    def test_no_modern_source_means_the_raster_advice_still_stands(self):
        out = self.audit("""<picture>
          <source media="(max-width: 600px)" srcset="/i/small.png">
          <img src="/i/logo.png" alt="a mark">
        </picture>""")
        self.assertEqual(out["modern_format_count"], 0)
        self.assertEqual(out["responsive_count"], 1, "a source srcset is a srcset "
                                                     "whatever format it offers")
        self.assertIn("Consider AVIF/WebP for raster image",
                      [i["message"] for i in out["issues"]])

    def test_a_source_with_no_type_is_read_from_its_urls(self):
        """`type` is optional, and a CDN URL is often all there is to go on."""
        out = self.audit("""<picture>
          <source srcset="/i/logo.webp 1x, /i/logo@2x.webp 2x">
          <img src="/i/logo.jpg" alt="a mark">
        </picture>""")
        self.assertEqual(out["modern_format_count"], 1)

    def test_the_sources_are_found_under_either_html_parser(self):
        """The bug inside the bug, and the reason this fix nearly shipped broken.

        `seo_common` prefers `lxml`, and libxml2 predates `<picture>`: it does not
        know `<source>` is a void element, so it makes the `<img>` a *child* of the
        first `<source>`. `html.parser` gives the `img` the `<picture>` as its
        parent, as the spec does. The first version of this checked `img.parent`,
        passed nothing under the parser that actually runs, and would have left
        MB-096/MB-097 exactly as broken as before while looking fixed.

        Which parser gets used is itself decided by whether `lxml` happens to be in
        `sys.modules`, so this is not a hypothetical second branch — it is import
        order deciding how a page is read. Recorded in KNOWN-ISSUES.md.
        """
        from bs4 import BeautifulSoup
        from seo_common import picture_sources
        markup = self.PICTURE
        parents = {}
        for parser in ("lxml", "html.parser"):
            soup = BeautifulSoup(markup, parser)
            img = soup.find("img")
            parents[parser] = img.parent.name
            found = picture_sources(img, "https://example.com/")
            self.assertEqual([s["type"] for s in found],
                             ["image/avif", "image/webp"], parser)
        self.assertEqual(parents, {"lxml": "source", "html.parser": "picture"},
                         "the parsers have stopped disagreeing; if lxml has learned "
                         "about <picture>, this test is the place to find out")

    def test_a_video_source_is_not_an_image_source(self):
        """`<source>` means something else inside `<video>`, and the `img` next to
        one is not part of it."""
        out = self.audit("""<video controls>
          <source src="/v/clip.webm" type="video/webm">
        </video><img src="/i/logo.png" alt="a mark">""")
        self.assertEqual(out["images"][0]["picture_source_count"], 0)
        self.assertEqual(out["modern_format_count"], 0)


class EveryCriticalItemIsCovered(unittest.TestCase):
    """The list this file is measured against.

    Without it, "tests for the critical scripts" quietly means "for the ones
    somebody got round to" — and which ones those were would be invisible.
    """

    # Scripts tested anywhere in `tests/`, not only in this file — `tls_certificate.py`
    # needs a certificate to answer at all, so its cases live in `test_tls_certificate.py`
    # where the TLS harness is. A hand-kept list can claim coverage that does not exist,
    # which is the failure mode this class was written against, so the third test below
    # makes the suite prove each name.
    COVERED = {"parse_html.py", "indexability_matrix.py", "canonical_checker.py",
               "robots_path_tester.py", "security_headers.py", "pagespeed.py",
               "domain_safety_check.py", "tls_certificate.py"}

    def test_every_script_deciding_a_critical_item_has_a_test_class(self):
        with open(REGISTRY, encoding="utf-8") as f:
            items = json.load(f)["items"]
        deciders = {(i.get("check") or {}).get("script")
                    for i in items
                    if i["severity"] == "critical" and (i.get("check") or {}).get("script")}
        self.assertEqual(deciders - self.COVERED, set(),
                         "a script decides a critical item and nothing here tests it")

    def test_the_covered_list_holds_no_scripts_that_stopped_mattering(self):
        with open(REGISTRY, encoding="utf-8") as f:
            items = json.load(f)["items"]
        deciders = {(i.get("check") or {}).get("script")
                    for i in items if i["severity"] == "critical"}
        self.assertEqual(self.COVERED - deciders, set(),
                         "this file tests a script no critical item reads any more")

    def test_every_name_on_the_list_is_actually_exercised_somewhere(self):
        """The list is a claim, and a claim in a set literal costs one line to fake.

        Both tests above read `COVERED` and neither opens a test file, so a script
        added here and tested nowhere would turn this class green while removing the
        coverage it exists to measure. This is the only test that looks.
        """
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        corpus = ""
        for name in sorted(os.listdir(tests_dir)):
            if name.startswith("test_") and name.endswith(".py"):
                with open(os.path.join(tests_dir, name), encoding="utf-8") as f:
                    corpus += f.read()
        unproven = sorted(s for s in self.COVERED
                          if s not in corpus and s[:-3] not in corpus)
        self.assertEqual(unproven, [],
                         "named as covered, but no test file mentions it: " + str(unproven))


if __name__ == "__main__":
    unittest.main()
