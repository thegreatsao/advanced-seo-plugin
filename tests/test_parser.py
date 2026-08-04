"""Which HTML parser reads a page, and what changes when it is the other one.

KNOWN-ISSUES carried this as "it needs measuring on real sites, not a default". This
file is that measurement, taken against a committed corpus instead of a crawl, and the
reasoning for the substitution is worth stating because it is a judgement, not a
shortcut:

- **A crawl is evidence that decays.** The sites would change, the numbers behind the
  decision could not be re-derived by anyone reading this later, and nothing could be
  committed. This project already made that call once, for the Public Suffix List:
  bundle a dated snapshot rather than fetch at audit time, because a run must answer
  the same offline and next month. Evidence behind a *decision* deserves the same
  treatment as evidence behind a verdict.
- **The suite is offline and stays offline.** Loopback only. A test that reached
  en.wikipedia.org to decide a parser would make every future contributor's CI depend
  on somebody else's uptime, and `broken_links.py` requests every link it finds.
- **What a corpus cannot do** is contain a divergence nobody thought of. So the
  decision is also made *cheap to revisit*: `SEO_HTML_PARSER` switches the parser, the
  run records which one produced its verdicts, and an operator who suspects the parser
  on a real site can re-run and diff. That override is the honest half of a
  fixture-measured decision — it is what makes being wrong here recoverable.

The shapes are chosen for what real generators emit, not for what breaks a parser:
unclosed `<p>` and `<li>` (WordPress themes, hand-written HTML), 300-deep `<div>`
nesting (React/Tailwind output), an inline `<svg>` carrying its own `<title>` (icon
sprites), `<template>` and `<noscript>` (component frameworks), a `<div>` inside
`<head>` (injected tags), `<picture>` (responsive images), a bare fragment (a CMS
partial), duplicate attributes and unquoted values (CDN rewriting).

**The result.** Every field the registry reads is identical under both parsers across
all fifteen shapes. The divergence is structural — parent/child, not values — and it
reaches exactly two call sites, both pinned below with the numbers.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "seo-checklist", "scripts")
sys.path.insert(0, SCRIPTS)

import bs4  # noqa: E402
import seo_common  # noqa: E402

PARSERS = ("lxml", "html.parser")

# Every field `seo_common.parse_html` returns that a registry rule reads. Not a
# hand-picked subset: the assertion below is that *all* of them agree, so a field
# added to the parser output joins this test by existing.
SKIP_FIELDS = {"soup", "body_text"}          # not JSON-serialisable / whitespace-only


CORPUS = {
    "picture_source": """<html><head><title>T</title></head><body>
<picture><source srcset="a.webp" type="image/webp"><source srcset="a.avif">
<img src="a.jpg" alt="A"></picture></body></html>""",

    "unclosed_p_li": """<html><head><title>T</title></head><body>
<p>one<p>two<ul><li>a<li>b</ul><div><span>x</div></body></html>""",

    "inline_svg_title": """<html><head><title>Real page title</title></head><body>
<svg viewBox="0 0 10 10"><title>Icon label</title><path d="M0 0"/></svg>
<h1>H</h1></body></html>""",

    "div_in_head": """<html><head><div>junk in head</div>
<title>T</title><meta name="description" content="D">
<meta name="viewport" content="width=device-width"></head><body><h1>H</h1></body></html>""",

    "template_and_noscript": """<html><head><title>T</title></head><body>
<h1>Real</h1><template><h1>In template</h1></template>
<noscript><h1>In noscript</h1><a href="/ns">ns</a></noscript></body></html>""",

    "deep_nesting_300": ("<html><head><title>T</title>"
                         '<meta name="description" content="D"></head><body>'
                         + "<div>" * 300 + '<h1>Deep heading</h1><a href="/deep">deep</a>'
                         + "</div>" * 300 + "</body></html>"),

    "deep_nesting_60": ("<html><head><title>T</title></head><body>"
                        + "<div>" * 60 + "<h1>Deep heading</h1>"
                        + "</div>" * 60 + "</body></html>"),

    "nested_form": """<html><head><title>T</title></head><body>
<form action="/a"><input name="x"><form action="/b"><input name="y"></form></form>
</body></html>""",

    "table_implied_tbody": """<html><head><title>T</title></head><body>
<table><tr><td><a href="/in-table">link</a></td></tr></table></body></html>""",

    "custom_elements": """<html><head><title>T</title></head><body>
<my-widget><h1>Inside a custom element</h1><a href="/ce">x</a></my-widget>
<slot name="s"><p>slotted</p></slot></body></html>""",

    "conditional_comment": """<html><head><title>T</title></head><body>
<!--[if IE]><p>old</p><![endif]--><h1>H</h1></body></html>""",

    "bad_attrs": """<html><head><title>T &amp; more</title></head><body>
<a href="/q?a=1&b=2" class="x" class="y">link</a><img src=a.jpg alt=Unquoted>
</body></html>""",

    "fragment_no_html": "<title>T</title><h1>H</h1><p>A CMS partial, no html or body.</p>",

    "ldjson_in_body": """<html><head><title>T</title></head><body>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article"}</script>
<h1>H</h1></body></html>""",

    "two_titles": """<html><head><title>First</title><title>Second</title></head>
<body><h1>H</h1></body></html>""",
}


def parse_with(html: str, parser: str) -> dict:
    """`seo_common.parse_html`, forced onto one parser.

    Patched at `seo_common.BeautifulSoup` rather than through `SEO_HTML_PARSER`,
    because this has to keep working if `html_parser()` is ever changed — the point of
    the test is the two parsers' behaviour, not the function that picks between them.
    """
    saved = seo_common.BeautifulSoup
    seo_common.BeautifulSoup = lambda markup, _parser: bs4.BeautifulSoup(markup, parser)
    try:
        return seo_common.parse_html(html, "https://example.com/")
    finally:
        seo_common.BeautifulSoup = saved


def executable_source(path: str) -> str:
    """A file's code with every comment and string literal removed.

    `tokenize` rather than a regex or the AST: the AST would need a visitor per node
    type to reconstruct the expression, and a regex cannot tell code from the prose
    beside it — which is the whole reason this function exists.
    """
    import io
    import tokenize
    kept = []
    with open(path, "rb") as f:
        for token in tokenize.tokenize(io.BytesIO(f.read()).readline):
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            kept.append(token.string)
    return " ".join(kept)


def comparable(parsed: dict) -> dict:
    out = {}
    for key, value in parsed.items():
        if key in SKIP_FIELDS:
            continue
        out[key] = json.dumps(value, default=str, sort_keys=True)
    return out


class TheChoiceIsDeliberate(unittest.TestCase):
    """The defect, separately from which parser wins it.

    `"lxml" if "lxml" in sys.modules else "html.parser"` asks whether something
    imported lxml first, not whether lxml is installed — so the same page could be
    parsed two ways on one machine, and `parse_html.py` and `seo_common` could
    disagree inside a single audit.
    """

    def setUp(self):
        self.saved = os.environ.get("SEO_HTML_PARSER")
        os.environ.pop("SEO_HTML_PARSER", None)

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("SEO_HTML_PARSER", None)
        else:
            os.environ["SEO_HTML_PARSER"] = self.saved

    def test_no_script_decides_the_parser_by_import_order_any_more(self):
        """Source-level, and deliberately so: a behavioural test cannot see a second
        copy of the pattern in a script nobody thought to import here.

        Comments and string literals are stripped first, and that is not fussiness —
        the first version of this test failed on `seo_common.py` and `parse_html.py`
        because their new docstrings *quote* the old expression while explaining why it
        was wrong. Same trap `audit_assertions.py` fell into: a scan for "strings this
        file contains" counts the paragraph describing what the code used to do.
        """
        offenders = []
        for name in sorted(os.listdir(SCRIPTS)):
            if not name.endswith(".py"):
                continue
            code = executable_source(os.path.join(SCRIPTS, name))
            if "sys.modules" in code and "lxml" in code:
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_lxml_is_preferred_when_it_imports(self):
        self.assertEqual(seo_common.html_parser(), "lxml")

    def test_the_override_is_honoured_and_a_typo_is_not(self):
        os.environ["SEO_HTML_PARSER"] = "html.parser"
        self.assertEqual(seo_common.html_parser(), "html.parser")
        # Same rule as a nonsense SEO_MAX_RPS falling back to the default rather than
        # to no limit: a typo must never quietly change what a run measures.
        os.environ["SEO_HTML_PARSER"] = "lxlm"
        self.assertEqual(seo_common.html_parser(), "lxml")

    def test_the_run_records_which_parser_produced_its_verdicts(self):
        """A reader comparing two runs that disagree has to be able to rule this out."""
        from checklist_runner import html_parser as recorded
        self.assertEqual(recorded(), seo_common.html_parser())

    def test_both_html_parsing_entry_points_agree(self):
        """`parse_html.py` had its own copy of the import-order test, so one audit
        could parse the same page two ways depending on which check reached it."""
        import parse_html
        self.assertIs(parse_html.html_parser, seo_common.html_parser)


class EveryFieldTheRegistryReadsIsParserIndependent(unittest.TestCase):
    """The measurement. Fifteen shapes, every returned field, both parsers.

    This is what licenses choosing lxml on fixtures rather than on a crawl: the
    disagreement is not in the values any rule reads. If a future bs4 or libxml2
    release changes that, this fails and the decision gets revisited with evidence.
    """

    def test_all_fields_match_on_every_shape(self):
        divergences = []
        for name, html in CORPUS.items():
            a, b = comparable(parse_with(html, "lxml")), comparable(parse_with(html, "html.parser"))
            self.assertEqual(sorted(a), sorted(b), f"{name}: different fields emitted")
            for field in sorted(a):
                if a[field] != b[field]:
                    divergences.append(f"{name}.{field}: lxml={a[field][:60]} "
                                       f"html.parser={b[field][:60]}")
        self.assertEqual(divergences, [],
                         "the parsers disagree about a field a rule reads:\n"
                         + "\n".join(f"  {d}" for d in divergences))

    def test_the_corpus_covers_the_shapes_the_docstring_claims(self):
        """A corpus is only evidence for what is in it, so what is in it is asserted
        rather than described. Dropping a shape has to be a visible act."""
        self.assertEqual(len(CORPUS), 15)
        for required in ("picture_source", "unclosed_p_li", "deep_nesting_300",
                         "inline_svg_title", "template_and_noscript",
                         "fragment_no_html", "div_in_head"):
            self.assertIn(required, CORPUS)


class WhereTheParsersActuallyDiverge(unittest.TestCase):
    """The two structural call sites, pinned with their numbers.

    Both are recorded rather than fixed-and-forgotten: these are the facts that would
    have to be re-measured if the parser choice were ever revisited, and a test is the
    only place a number like that stays true.
    """

    def scan(self, html: str, parser: str) -> dict:
        """`answer_block_scanner` over fixed markup with a fixed parser.

        The patch goes at `seo_common.BeautifulSoup` and `_load_source`, so the script
        runs its real logic over a document it cannot fetch and a parser it did not
        choose. Restored in `finally` because leaving either patched changes every
        test that runs after this one in the same process.
        """
        import answer_block_scanner as scanner
        saved_load, saved_bs = scanner._load_source, seo_common.BeautifulSoup
        scanner._load_source = lambda source, timeout: (html, "https://example.com/", {})
        seo_common.BeautifulSoup = (
            lambda markup, _p, _parser=parser: bs4.BeautifulSoup(markup, _parser))
        try:
            return scanner.scan_answer_blocks("https://example.com/")
        finally:
            scanner._load_source, seo_common.BeautifulSoup = saved_load, saved_bs

    PICTURE = """<picture><source srcset="a.webp" type="image/webp">
<source srcset="a.avif"><img src="a.jpg" alt="A"></picture>"""

    def test_lxml_nests_the_img_inside_the_first_source(self):
        """libxml2 predates `<picture>` and does not know `<source>` is void. This is
        the whole divergence, and it is why `picture_sources()` walks up to any
        ancestor and scans recursively instead of trusting the parent."""
        shapes = {}
        for parser in PARSERS:
            soup = bs4.BeautifulSoup(self.PICTURE, parser)
            img = soup.find("img")
            picture = soup.find("picture")
            shapes[parser] = (img.parent.name,
                              len(picture.find_all("source", recursive=False)),
                              len(picture.find_all("source")))
        self.assertEqual(shapes["lxml"], ("source", 1, 2))
        self.assertEqual(shapes["html.parser"], ("picture", 2, 2))

    def test_picture_sources_survives_both(self):
        """The function every responsive-image check goes through. It found two
        sources under both parsers before this test existed — by luck of being written
        defensively, which is not a property anybody should rely on twice."""
        for parser in PARSERS:
            soup = bs4.BeautifulSoup(self.PICTURE, parser)
            sources = seo_common.picture_sources(soup.find("img"), "https://example.com/")
            self.assertEqual(len(sources), 2, parser)
            self.assertEqual(sources[0]["type"], "image/webp", parser)

    UNCLOSED_ANSWER = """<html><head><title>T</title></head><body>
<h2>How long does bread keep?</h2><p>Three days in paper, a week in the freezer,
because the acidity in sourdough slows staling down considerably.
<h2>What is a starter?</h2><ul><li>flour<li>water<li>time</ul></body></html>"""

    def test_an_unclosed_p_moves_the_answer_block_score(self):
        """The one place the parser changes a *verdict*, and the reason this file
        exists rather than a one-line default.

        `answer_block_scanner.py` finds the answer to a heading with
        `find_next_sibling()`. On markup with an unclosed `<p>` — the commonest
        invalidity on the web — lxml leaves the following `<h2>` inside the paragraph
        and `html.parser` closes it per the spec, so the two see different documents:
        one finds a list and no direct answer, the other a direct answer and no list.
        GO-144 asserts `score >= 70`, and the score is 10 against 32.

        **Neither is right**, which is the finding underneath the finding: the score
        is sensitive to markup validity under either parser, and that is recorded in
        KNOWN-ISSUES as its own defect rather than smuggled into a parser decision.
        """
        scores = {p: self.scan(self.UNCLOSED_ANSWER, p) for p in PARSERS}
        self.assertEqual(scores["lxml"]["score"], 10)
        self.assertEqual(scores["html.parser"]["score"], 32)
        # And the shape of the disagreement, so a change in *how* they differ is not
        # hidden by the totals happening to stay the same.
        self.assertEqual(len(scores["lxml"]["lists"]), 1)
        self.assertEqual(scores["lxml"]["direct_answers"], [])
        self.assertEqual(scores["html.parser"]["lists"], [])
        self.assertEqual(len(scores["html.parser"]["direct_answers"]), 1)

    VALID_ANSWER = """<html><head><title>T</title></head><body>
<h2>How long does bread keep?</h2><p>Three days in paper, a week in the freezer,
because the acidity in sourdough slows staling down considerably.</p>
<h2>What is a starter?</h2><ul><li>flour</li><li>water</li><li>time</li></ul></body></html>"""

    def test_valid_markup_gives_the_same_answer_blocks_either_way(self):
        """The reassuring half, and the reason this divergence is bounded: markup that
        closes its tags reads the same either way.

        Both tags, though. The first version of this test closed the `<p>` and left the
        `<li>`s open, and the scores came out 10 against 0 — so "valid enough" is not a
        category here, and an unclosed `<li>` is pinned as its own case below.
        """
        out = {p: self.scan(self.VALID_ANSWER, p) for p in PARSERS}
        self.assertEqual(out["lxml"]["score"], out["html.parser"]["score"])
        self.assertEqual(len(out["lxml"]["direct_answers"]),
                         len(out["html.parser"]["direct_answers"]))


    UNCLOSED_LI = """<html><head><title>T</title></head><body>
<h2>How long does bread keep?</h2><p>Three days in paper, a week in the freezer,
because the acidity in sourdough slows staling down considerably.</p>
<h2>What is a starter?</h2><ul><li>flour<li>water<li>time</ul></body></html>"""

    def test_an_unclosed_li_diverges_too(self):
        """The second half of the same defect, and the reason the first version of the
        test above passed for the wrong reason. An unclosed `<li>` is as common as an
        unclosed `<p>`, and it moves the same score."""
        scores = {p: self.scan(self.UNCLOSED_LI, p)["score"] for p in PARSERS}
        self.assertNotEqual(scores["lxml"], scores["html.parser"])
        self.assertEqual(scores, {"lxml": 10, "html.parser": 0})


if __name__ == "__main__":
    unittest.main()
