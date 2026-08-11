"""The five evidence scripts that talk to somebody else, and one that reads an export.

`test_evidence_scripts.py` serves a real origin, because that is better than a stub
wherever the thing being tested is a request. These five cannot be served: three ask
Search Console, one asks the W3C validator, one reads a file a human downloads from
the Search Console UI, and one needs a secret. So the *one* call that leaves the
machine is stubbed, in the module that makes it, and everything on this side of that
call runs unmodified.

That is a weaker test and it is the honest limit rather than a shortcut: nothing here
can prove the plugin reads Google's real response shape correctly, only that it reads
the shape it was written for. What these tests do cover is every line that turns a
response into the field a registry rule asserts on — which is where the last three
defects in this family were.

Offline: no credentials, no network, no API key. `test_evidence_scripts.script_env`
clears them for the subprocess runs; here the stub is the boundary.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "seo-checklist")
SCRIPTS = os.path.join(SKILL, "scripts")
REGISTRY = os.path.join(SKILL, "resources", "config", "checklist.json")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checklist_runner import NO_DATA, PASS, FAIL, WARN, evaluate  # noqa: E402

with open(REGISTRY, encoding="utf-8") as f:
    ITEMS = {i["id"]: i for i in json.load(f)["items"]}


def verdict(item_id: str, output: dict) -> str:
    check = ITEMS[item_id]["check"]
    ok, _ = evaluate(check["assert"], output)
    if ok is None:
        return NO_DATA
    if ok:
        return PASS
    warn = check.get("warn")
    if warn and evaluate(warn, output)[0]:
        return WARN
    return FAIL


def verdicts(items, output: dict) -> dict:
    """Every item's verdict at once, so a scenario can pin all of them.

    The GSC scenarios used to accept `PASS` **or** `NO_DATA` on their positive
    fixtures and "at least one of the group failed" on their negative ones. Both are
    satisfied by a rule that has stopped deciding anything: a path renamed out from
    under an assertion reports `NO_DATA` forever, which is the exact failure this
    file's docstring says the last three defects in this family were. A full map
    fails on the difference between deciding and not.
    """
    return {i["id"]: verdict(i["id"], output) for i in items}


def tmpfile(name: str, content) -> str:
    path = os.path.join(tempfile.mkdtemp(), name)
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(path, mode, **({} if isinstance(content, bytes)
                             else {"encoding": "utf-8"})) as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# The Search Console Links export: a file, not an API
# ---------------------------------------------------------------------------

class LinksExport(unittest.TestCase):
    """BL-084 `concentration.top1_share_pct`, BL-086 `total_links`,
    BL-087 `linking_domains`.

    The Links report has no API — a human clicks Export in the UI — which is why
    these three items are `NO_DATA` on every run that does not supply the file, and
    why the contract pair exempts them. The reader itself needs no network at all, so
    there is no excuse for it to be untested.
    """

    SITES = ("Top linking sites,Linking pages\n"
             "partner.example,30\n"
             "directory.example,26\n"
             "forum.example,9\n"
             "blog.example,4\n"
             "news.example,3\n")

    def analyze(self, name="top-linking-sites.csv", content=None, site=""):
        import gsc_links_csv
        return gsc_links_csv.analyze(tmpfile(name, content or self.SITES), site)

    def test_a_spread_link_profile_passes_all_three(self):
        out = self.analyze()
        self.assertEqual(out["total_links"], 72)
        self.assertEqual(out["linking_domains"], 5)
        self.assertEqual(verdict("BL-086", out), PASS)
        self.assertEqual(verdict("BL-087", out), PASS)
        self.assertEqual(verdict("BL-084", out), PASS)

    def test_one_domain_supplying_most_of_the_links_is_a_concentration(self):
        out = self.analyze(content="Top linking sites,Linking pages\n"
                                   "one.example,900\n"
                                   "two.example,10\n")
        self.assertGreater(out["concentration"]["top1_share_pct"], 50)
        self.assertEqual(verdict("BL-084", out), FAIL)
        self.assertEqual(verdict("BL-087", out), FAIL)

    def test_a_header_row_is_dropped_rather_than_counted_as_a_domain(self):
        """The shape check that lets this work in any language: Google localises the
        export, so a row is a header when its second column is not a number, not when
        it says "Top linking sites"."""
        out = self.analyze(content="Сайты со ссылками,Связывающие страницы\n"
                                   "partner.example,42\n"
                                   "directory.example,18\n")
        self.assertEqual(out["linking_domains"], 2)
        self.assertEqual(out["total_links"], 60)

    def test_a_zip_of_sheets_is_read_the_same_way(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("top-linking-sites.csv", self.SITES)
            archive.writestr("top-linking-text.csv",
                             "Link text,Links\nfixture bakery,30\nsourdough,12\n")
        out = self.analyze("example.com-Links.zip", buffer.getvalue())
        self.assertEqual(out["linking_domains"], 5)
        self.assertTrue(out["anchors"])

    def test_an_empty_export_is_undecided_rather_than_zero_links(self):
        """`total_links: 0` from an empty file would read as "this site has no
        backlinks", which is a verdict. The absence of data is not that."""
        out = self.analyze(content="Top linking sites,Linking pages\n")
        self.assertEqual(verdict("BL-086", out), FAIL)
        self.assertIsNone(out["concentration"]["top1_share_pct"])
        self.assertEqual(verdict("BL-084", out), NO_DATA)


# ---------------------------------------------------------------------------
# The W3C validator
# ---------------------------------------------------------------------------

class HtmlValidator(unittest.TestCase):
    """TE-171 and TE-176 — whichever items read this script's counts.

    One stubbed call: the POST to validator.w3.org. Everything that turns its
    response into counts is real.
    """

    def setUp(self):
        import html_validator
        self.mod = html_validator
        self.saved = html_validator.requests.get

    def tearDown(self):
        self.mod.requests.get = self.saved

    def serve(self, messages, status=200):
        class Response:
            status_code = status
            headers = {"Content-Type": "application/json"}
            text = json.dumps({"messages": messages})

            def json(self):
                return {"messages": messages}

        self.mod.requests.get = lambda *a, **k: Response()

    def items_for(self):
        return [i for i in ITEMS.values()
                if (i.get("check") or {}).get("script") == "html_validator.py"]

    def test_a_clean_document_reports_no_errors(self):
        self.serve([])
        out = self.mod.validate("https://example.com/")
        self.assertEqual(out["summary"]["errors"], 0)
        for item in self.items_for():
            self.assertEqual(verdict(item["id"], out), PASS, item["id"])

    def test_errors_and_warnings_are_counted_apart(self):
        """Apart, because one of these two items reads each. Collapsing them would
        make a document with fifty warnings and no errors indistinguishable from a
        broken one."""
        self.serve([
            {"type": "error", "message": "Stray end tag div.", "lastLine": 12},
            {"type": "error", "message": "Duplicate ID footer.", "lastLine": 40},
            {"type": "warning", "message": "Empty heading.", "lastLine": 7},
        ])
        out = self.mod.validate("https://example.com/")
        self.assertEqual(out["summary"]["errors"], 2)
        self.assertEqual(out["summary"]["warnings"], 1)
        failing = [i["id"] for i in self.items_for()
                   if verdict(i["id"], out) in (FAIL, WARN)]
        self.assertTrue(failing, f"nothing failed on two errors: {out}")

    def test_a_validator_outage_is_undecided_rather_than_clean(self):
        """The failure this family keeps producing: a service that answers with
        nothing, read as a site with nothing wrong. `errors` must be absent, not 0.
        """
        def boom(*a, **k):
            raise self.mod.requests.RequestException("503 Service Unavailable")
        self.mod.requests.get = boom
        out = self.mod.validate("https://example.com/")
        self.assertTrue(out.get("error"))
        for item in self.items_for():
            self.assertEqual(verdict(item["id"], out), NO_DATA, item["id"])

    def test_the_validator_failing_to_fetch_the_page_is_not_a_clean_document(self):
        """The same failure one step further in, and it needs no outage to happen.

        Nu answers 200 with a `non-document-error` when *it* could not read the URL —
        a 403 aimed at its user agent, a timeout, a TLS problem, a host it cannot
        reach. That is not a document error, so `errors` was 0 and two items reported
        "your HTML validates" about a page the validator never saw. Found by pointing
        the dead-origin sweep at a real validator by accident, which is also why that
        sweep now leaves the API scripts alone.
        """
        self.serve([{"type": "non-document-error", "subType": "io",
                     "message": "HTTP resource not retrievable. "
                                "The HTTP status from the remote server was: 403."}])
        out = self.mod.validate("https://example.com/")
        self.assertIn("could not read the page", out.get("error") or "")
        self.assertEqual(out["summary"], {})
        for item in self.items_for():
            self.assertEqual(verdict(item["id"], out), NO_DATA, item["id"])

    def test_a_warning_alongside_a_fetch_problem_is_still_read(self):
        """Only an answer that is *entirely* non-document errors means the document
        was not seen. A page that validated and also produced one odd transport
        message is a page that validated."""
        self.serve([{"type": "non-document-error", "subType": "warning",
                     "message": "The Content-Type was text/html with no charset."},
                    {"type": "error", "message": "Stray end tag div.", "lastLine": 3}])
        out = self.mod.validate("https://example.com/")
        self.assertIsNone(out.get("error"))
        self.assertEqual(out["summary"]["errors"], 1)


# ---------------------------------------------------------------------------
# Search Console
# ---------------------------------------------------------------------------

class _Query:
    """The two call chains these scripts use, and nothing else.

    `service.searchanalytics().query(...).execute()` and
    `service.urlInspection().index().inspect(...).execute()`. Written out rather than
    produced by a mocking library so that a change in either chain fails here loudly
    instead of being absorbed by an auto-generated attribute.
    """

    def __init__(self, rows=None, inspection=None, sitemaps=None):
        self._rows = rows or []
        self._inspection = inspection or {}
        self._sitemaps = sitemaps or {}
        self.calls = []

    # searchanalytics
    def searchanalytics(self):
        return self

    def query(self, siteUrl=None, body=None):  # noqa: N803 - Google's spelling
        self.calls.append(("query", siteUrl, body))
        return _Executable({"rows": self._rows})

    # urlInspection
    def urlInspection(self):  # noqa: N802 - Google's spelling
        return self

    def index(self):
        return self

    def inspect(self, body=None):
        self.calls.append(("inspect", body))
        return _Executable(self._inspection)

    # sitemaps
    def sitemaps(self):
        return self

    def list(self, siteUrl=None):  # noqa: N803
        return _Executable(self._sitemaps)


class _Executable:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class Cannibalization(unittest.TestCase):
    """The four items reading `gsc_cannibalization.py`.

    Two URLs competing for one query is the thing this measures, and it cannot be
    measured from a page: it needs a property's history. Which is why these are
    `NO_DATA` without credentials — and why the arithmetic that turns rows into a
    verdict had never been exercised.
    """

    def setUp(self):
        import gsc_cannibalization
        self.mod = gsc_cannibalization
        self.saved = gsc_cannibalization.build_service

    def tearDown(self):
        self.mod.build_service = self.saved

    def rows(self, triples):
        return [{"keys": list(keys), "clicks": clicks, "impressions": impressions,
                 "ctr": 0.05, "position": position}
                for keys, clicks, impressions, position in triples]

    def analyze(self, rows, alternate_urls=None):
        self.mod.build_service = lambda *a, **k: _Query(rows=rows)
        return self.mod.analyze("https://example.com/", "/dev/null", 90,
                                alternate_urls=alternate_urls)

    def items_for(self):
        return [i for i in ITEMS.values()
                if (i.get("check") or {}).get("script") == "gsc_cannibalization.py"]

    def test_one_url_per_query_is_not_cannibalisation(self):
        out = self.analyze(self.rows([
            (("fixture bakery", "https://example.com/"), 400, 2000, 1.1),
            (("sourdough starter", "https://example.com/starter"), 90, 1000, 3.1),
            (("proofing times", "https://example.com/guide"), 40, 600, 5.4),
        ]))
        self.assertEqual(out["cannibalized"], [])
        self.assertEqual(verdicts(self.items_for(), out),
                         {"GO-139": PASS, "KW-070": PASS, "KW-071": NO_DATA,
                          "MS-023": PASS})

    def test_two_urls_ranking_for_one_query_are_found(self):
        out = self.analyze(self.rows([
            (("fixture bakery", "https://example.com/"), 400, 2000, 1.1),
            (("sourdough starter", "https://example.com/starter"), 50, 900, 4.2),
            (("sourdough starter", "https://example.com/blog/starter"), 30, 800, 6.9),
            (("sourdough starter", "https://example.com/faq"), 5, 400, 18.0),
        ]))
        self.assertTrue(out["cannibalized"])
        found = out["cannibalized"][0]
        self.assertEqual(found["query"], "sourdough starter")
        self.assertGreaterEqual(found["page_count"], 2)
        self.assertGreaterEqual(len(found["pages"]), 2)
        # Pinned per item rather than "something failed": which one fails is the
        # content of the check. KW-071's registry claim is deliberately unanswered:
        # raw spread has no failing direction, and repointing the registry is a
        # separate contract change. MS-023 still counts genuine split queries.
        self.assertEqual(verdicts(self.items_for(), out),
                         {"GO-139": PASS, "KW-070": PASS, "KW-071": NO_DATA,
                          "MS-023": WARN})

    def test_an_owned_brand_and_its_variants_move_to_branded_spread(self):
        out = self.analyze(self.rows([
            (("acme valley riverside", "https://example.com/"), 400, 2000, 1.2),
            (("acme valley riverside", "https://example.com/menu"), 30, 500, 1.4),
            (("acme valley riversidė", "https://example.com/"), 90, 600, 1.1),
            (("acme valley riversidė", "https://example.com/gallery"), 10, 100, 2.0),
            (("acmevalley reviews", "https://example.com/"), 50, 400, 1.3),
            (("acmevalley reviews", "https://example.com/reviews"), 8, 80, 4.0),
        ]))
        self.assertEqual(out["cannibalized"], [])
        self.assertEqual({row["query"] for row in out["branded_spread"]},
                         {"acme valley riverside", "acme valley riversidė",
                          "acmevalley reviews"})
        self.assertEqual(out["summary"]["contested_queries"], 0)

    def test_a_brand_the_homepage_does_not_own_still_cannibalizes(self):
        out = self.analyze(self.rows([
            (("acme valley", "https://example.com/other"), 400, 2000, 1.2),
            (("acme valley", "https://example.com/"), 30, 500, 2.0),
        ]))
        self.assertFalse(out["branded"]["owns_homepage"])
        self.assertEqual([row["query"] for row in out["cannibalized"]],
                         ["acme valley"])

    def test_hreflang_alternates_count_as_one_logical_page(self):
        out = self.analyze(self.rows([
            (("acme valley", "https://example.com/"), 400, 2000, 1.2),
            (("acme valley", "https://example.com/en/"), 30, 500, 1.4),
            (("acme valley", "https://example.com/ru/"), 20, 300, 1.5),
        ]), alternate_urls=["https://example.com/", "https://example.com/en/",
                            "https://example.com/ru/"])
        self.assertEqual(out["cannibalized"], [])
        self.assertEqual(out["branded_spread"][0]["page_count"], 1)

    def test_close_nonbrand_competition_is_contested_but_a_wide_spread_is_not(self):
        out = self.analyze(self.rows([
            (("fixture bakery", "https://example.com/"), 500, 3000, 1.0),
            (("close query", "https://example.com/a"), 40, 500, 1.2),
            (("close query", "https://example.com/b"), 30, 400, 1.4),
            (("wide query", "https://example.com/a"), 20, 300, 1.5),
            (("wide query", "https://example.com/c"), 10, 200, 11.2),
        ]))
        self.assertEqual(out["summary"]["contested_queries"], 1)
        self.assertEqual([row["query"] for row in out["contested"]], ["close query"])
        self.assertNotIn("worst_spread", out["summary"])

    def test_no_credentials_is_undecided_and_says_so(self):
        """Not an empty history. A property nobody could open and a property with no
        traffic produce the same-shaped result and mean opposite things, and only one
        of them is a fact about the site."""
        def refuse(*a, **k):
            raise RuntimeError("credentials file not found")
        self.mod.build_service = refuse
        out = self.mod.analyze("https://example.com/", "/nonexistent.json", 90)
        self.assertTrue(out.get("error"))
        for item in self.items_for():
            self.assertEqual(verdict(item["id"], out), NO_DATA, item["id"])


class UrlInspection(unittest.TestCase):
    """The three items reading `gsc_url_inspection.py` — Google's own answer about
    whether a URL is indexed, which is the only place that answer exists.

    CI-002 joined them in 0.26.0 and immediately found that `indexed` was pre-seeded
    with `None` in the result, two lines under a comment explaining why
    `canonical_match` must not be: a `truthy` rule reads `None` as a failing value, so
    a property nobody could open reported the page as **not indexed** at `high`. The
    field is assigned only when the coverage wording is recognised, and
    `test_no_credentials_is_undecided` is the test that says so.
    """

    def setUp(self):
        import gsc_url_inspection
        self.mod = gsc_url_inspection
        self.saved = gsc_url_inspection.build_service

    def tearDown(self):
        self.mod.build_service = self.saved

    def inspect(self, verdict_text, coverage_state):
        payload = {"inspectionResult": {
            "indexStatusResult": {
                "verdict": verdict_text,
                "coverageState": coverage_state,
                "robotsTxtState": "ALLOWED",
                "indexingState": "INDEXING_ALLOWED",
                "lastCrawlTime": "2026-07-20T00:00:00Z",
                "googleCanonical": "https://example.com/",
                "userCanonical": "https://example.com/",
            }}}
        self.mod.build_service = lambda *a, **k: _Query(inspection=payload)
        return self.mod.analyze("https://example.com/", "https://example.com/",
                                "/dev/null", "en")

    def items_for(self):
        return [i for i in ITEMS.values()
                if (i.get("check") or {}).get("script") == "gsc_url_inspection.py"]

    def test_an_indexed_url_passes(self):
        out = self.inspect("PASS", "Submitted and indexed")
        self.assertEqual(verdicts(self.items_for(), out),
                         {"CI-002": PASS, "CI-010": PASS, "GO-135": PASS})

    def test_a_url_google_has_excluded_does_not(self):
        """CI-010 passing here is correct and is the reason to pin both. It asks
        whether Google's chosen canonical matches the declared one, which this URL
        answers yes to while not being indexed at all — a different question. An
        assertion of "at least one item failed" would have been satisfied by GO-135
        alone and would equally have been satisfied if CI-010 had stopped deciding.
        """
        out = self.inspect("FAIL", "Discovered - currently not indexed")
        self.assertEqual(verdicts(self.items_for(), out),
                         {"CI-002": FAIL, "CI-010": PASS, "GO-135": FAIL})

    def test_no_credentials_is_undecided(self):
        def refuse(*a, **k):
            raise RuntimeError("no credentials")
        self.mod.build_service = refuse
        out = self.mod.analyze("https://example.com/", "https://example.com/",
                               "/nonexistent.json", "en")
        self.assertTrue(out.get("error"))
        for item in self.items_for():
            self.assertEqual(verdict(item["id"], out), NO_DATA, item["id"])

    def test_text_output_survives_a_response_without_canonicals(self):
        payload = {"inspectionResult": {"indexStatusResult": {
            "verdict": "PASS",
            "coverageState": "Submitted and indexed",
            "robotsTxtState": "ALLOWED",
            "indexingState": "INDEXING_ALLOWED",
            "pageFetchState": "SUCCESSFUL",
        }}}
        self.mod.build_service = lambda *a, **k: _Query(inspection=payload)
        saved_argv = sys.argv
        sys.argv = ["gsc_url_inspection.py", "https://example.com/",
                    "--property", "sc-domain:example.com"]
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                self.mod.main()
        finally:
            sys.argv = saved_argv
        self.assertIn("canon match:   unknown", output.getvalue())


class SearchConsoleSummary(unittest.TestCase):
    """`gsc_checker.py`, which is the one that builds the service every other Search
    Console script borrows."""

    def setUp(self):
        import gsc_checker
        self.mod = gsc_checker

    def test_the_property_string_is_passed_through_untouched(self):
        """The bug this guards is not hypothetical: a run built `sc-domain:0.1` from
        `127.0.0.1`, and a property nobody owns answers with nothing, which reads as a
        site with no search traffic. The registrable-domain fix lives in the runner;
        this asserts the script does not re-derive one of its own.
        """
        service = _Query(rows=[{"keys": ["q", "https://example.com/"], "clicks": 1,
                                "impressions": 2, "ctr": 0.5, "position": 1.0}])
        # `get_performance_data`, not `fetch_search_analytics`. This test skipped itself
        # for eleven releases on `hasattr(mod, "fetch_search_analytics")` — a name the
        # module never had — and said so as "gsc_checker has no single-call entry point to
        # exercise", which was false: `main()` calls this one. A probe for a function that
        # does not exist reports the *subject* as missing, and the suite printed
        # "OK (skipped=1)" over an untested call into Search Console.
        result = self.mod.get_performance_data(service, "sc-domain:example.com", days=28)
        self.assertEqual(service.calls[0][1], "sc-domain:example.com")
        self.assertEqual([r["query"] for r in result["data"]], ["q"])


if __name__ == "__main__":
    unittest.main()
