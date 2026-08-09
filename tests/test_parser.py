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
reached exactly two call sites, both pinned below.

One of the two used to change a *verdict*: `answer_block_scanner.py` scored the same
page 10 or 32 depending on the parser. 0.15.0 fixed it rather than recording it, and
the tests below now assert the two parsers **agree**. That is a stronger pin than the
numbers were: a divergence recorded as a pair of numbers goes stale the moment either
side moves, while an equality assertion fails the day a new structural query is
written against sibling position again.
"""
import json
import os
import sys
import unittest
from unittest import mock

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

    def test_an_unimportable_seo_common_costs_a_label_and_not_the_run(self):
        """Why the import stays inside the function, asserted rather than commented.

        The runner is importable without bs4 or lxml on purpose: `--archive` has to
        run on a bare checkout, and this label is one field in the artifact. Hoisting
        `from seo_common import html_parser` to module level would read as a tidy-up
        and would turn a missing optional dependency into a runner that cannot start.
        """
        import checklist_runner
        with mock.patch.dict(sys.modules, {"seo_common": None}):
            self.assertEqual(checklist_runner.html_parser(), "unknown")

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
    """The two structural call sites, and what each one does about it.

    The first — `<picture>` — is a divergence the code copes with, pinned with its
    numbers because those are the facts that would have to be re-measured if the
    parser choice were revisited.

    The second used to be pinned the same way, at 10 against 32, and that was the
    wrong thing to do with it. A verdict that depends on which parser is installed is
    not a fact worth recording; it is a defect, and 0.15.0 fixed the instrument that
    caused it. The tests below assert agreement now.
    """

    def scan(self, html: str, parser: str) -> dict:
        """`answer_block_scanner` over fixed markup with a fixed parser.

        The patch goes at `seo_common.BeautifulSoup` and `load_source`, so the script
        runs its real logic over a document it cannot fetch and a parser it did not
        choose. Restored in `finally` because leaving either patched changes every
        test that runs after this one in the same process.

        Patched on the module that imported it, not on `seo_common`: the scripts do
        `from seo_common import load_source`, so each holds its own reference and
        rebinding the source module would not reach them.
        """
        import answer_block_scanner as scanner
        saved_load, saved_bs = scanner.load_source, seo_common.BeautifulSoup
        scanner.load_source = lambda source, timeout: (html, "https://example.com/", {})
        seo_common.BeautifulSoup = (
            lambda markup, _p, _parser=parser: bs4.BeautifulSoup(markup, _parser))
        try:
            return scanner.scan_answer_blocks("https://example.com/")
        finally:
            scanner.load_source, seo_common.BeautifulSoup = saved_load, saved_bs

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

    VALID_ANSWER = """<html><head><title>T</title></head><body>
<h2>How long does bread keep?</h2><p>Three days in paper, a week in the freezer,
because the acidity in sourdough slows staling down considerably.</p>
<h2>What is a starter?</h2><ul><li>flour</li><li>water</li><li>time</li></ul></body></html>"""

    UNCLOSED_LI = """<html><head><title>T</title></head><body>
<h2>How long does bread keep?</h2><p>Three days in paper, a week in the freezer,
because the acidity in sourdough slows staling down considerably.</p>
<h2>What is a starter?</h2><ul><li>flour<li>water<li>time</ul></body></html>"""

    def test_the_answer_block_score_no_longer_depends_on_closing_tags(self):
        """The one place the parser used to change a *verdict*, and now the one place
        this file proves a fix rather than records a fact.

        Three documents that a browser renders identically — one closing every tag,
        one leaving `<p>` open, one leaving `<li>` open. They used to score 10, 32 and
        0 across the two parsers, because `html.parser` applies none of HTML's implied
        end tags: an unclosed paragraph swallows the heading and list that follow it,
        and three list items nest three deep. Every one of those numbers was wrong
        about the page.

        All nine readings are the same now, and it is the same reading a browser gives:
        one three-item list, no direct answer — the paragraph is 18 words, under the
        20-word floor. The assertion is *equality between the parsers and between the
        three shapes*, which is a stronger statement than the old pair of pinned
        numbers: it fails on any new structural query that trusts sibling position,
        not only on the two that did.
        """
        shapes = {"valid": self.VALID_ANSWER,
                  "unclosed_p": self.UNCLOSED_ANSWER,
                  "unclosed_li": self.UNCLOSED_LI}
        seen = {}
        for shape, html in shapes.items():
            for parser in PARSERS:
                out = self.scan(html, parser)
                seen[f"{shape}/{parser}"] = (out["score"], len(out["direct_answers"]),
                                             len(out["definitions"]), len(out["lists"]))
        self.assertEqual(set(seen.values()), {(10, 0, 0, 1)}, seen)

    def test_a_list_item_reports_its_own_text_under_either_parser(self):
        """Not only the count. `html.parser`'s nested items make each `<li>`'s
        `get_text()` include every item after it, so the first item of a three-item
        list read "flour water time" — the evidence string a report shows a client,
        wrong in a way the score could not reveal."""
        for html in (self.VALID_ANSWER, self.UNCLOSED_LI, self.UNCLOSED_ANSWER):
            for parser in PARSERS:
                out = self.scan(html, parser)
                self.assertEqual(out["lists"][0]["sample"], ["flour", "water", "time"],
                                 parser)

    WRAPPED_ANSWER = """<html><body><h2>How long does bread keep?</h2>
<div class="entry-content"><p>Three days in paper, a week in the freezer, because the
acidity in a sourdough starter slows the staling process down very considerably.</p>
<p>Longer if you slice it first and freeze the slices, which also means you can toast
straight from frozen without waiting for a whole loaf to thaw on the counter.</p></div>
</body></html>"""

    def test_a_wrapped_answer_is_the_paragraph_and_not_the_wrapper(self):
        """The second defect the sibling walk was hiding, and it needed no invalid
        markup at all.

        A `<div>` between the heading and the paragraph — every themed CMS on the web
        — was itself read as the answer, so the word count was the whole section's.
        Two paragraphs measured 53 words and squeezed under the 70-word ceiling with
        the wrong text attached; three or more went over it and the page had no direct
        answer. Walking through wrappers to the prose gives the paragraph, 23 words,
        under both parsers.
        """
        for parser in PARSERS:
            out = self.scan(self.WRAPPED_ANSWER, parser)
            self.assertEqual(len(out["direct_answers"]), 1, parser)
            answer = out["direct_answers"][0]
            self.assertEqual(answer["word_count"], 23, parser)
            self.assertTrue(answer["answer"].endswith("considerably."), answer)

    def test_no_structural_query_trusts_sibling_position(self):
        """What actually keeps the fix from being written back.

        `find_next_sibling` asks the parser where an element's parent ends, and that
        is the one question the two parsers answer differently. Read from the tokens
        rather than the text, because this file's own prose names the method and the
        first version of a grep test in this tree matched its own docstring.
        """
        path = os.path.join(SCRIPTS, "answer_block_scanner.py")
        self.assertNotIn("find_next_sibling", executable_source(path))


if __name__ == "__main__":
    unittest.main()
