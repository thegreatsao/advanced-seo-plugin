"""The two defects a real trilingual site found, pinned so they cannot come back.

Both were reported by auditing the café — 24 pages, three languages, one of the plainest
link structures a site can have. It collected a `high` failure for its best search
result and a `medium` failure for its navigation menu. Neither defect is visible on a
monolingual fixture, which is why neither was caught by 629 tests:

- `BL-081` asked "does this (target, anchor) pair appear on more than half the crawled
  pages" of the whole site, and a translated site has one menu per language. Three
  languages puts every menu entry on at most a third of the pages, so no pair was
  classified as navigation and the header came back as exact-match anchor spam.
- `GO-134` read `opportunities[]` through a severity gate, so "position 4.2, within
  striking distance" was a `high` failure ranked first in the fix list.

The scope test below is the load-bearing one: it fails on any future rule that asks the
sitewide question only once, however that rule is written.

Offline. `navigation_links` and `detect_issues` are pure functions over a crawl
inventory and a sitemap list, so neither test needs a fixture site or a network.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "seo-checklist", "scripts")
sys.path.insert(0, SCRIPTS)

import anchor_text_audit  # noqa: E402
import gsc_checker  # noqa: E402


def trilingual(sections=("lt", "en", "ru"), per_section=8) -> tuple[dict, list]:
    """A site with one navigation bar per language, and nothing else.

    Menu targets are shared across languages — `/bbq` is linked from the Lithuanian,
    English and Russian menus — but the anchor is the language's own word, so each
    (target, anchor) pair reaches exactly one section. That is the shape the whole
    defect lives in: shared targets, per-language anchors.
    """
    pages, links = {}, []
    menu = ["bbq", "fishing", "menu", "gallery"]
    for lang in sections:
        prefix = "" if lang == sections[0] else f"/{lang}"
        for n in range(per_section):
            url = f"https://example.com{prefix}/page{n}"
            pages[url] = {"status": 200, "html": True, "lang": lang}
            for target in menu:
                links.append({"source": url,
                              "target": f"https://example.com/{target}",
                              "anchor": f"{lang}-{target}"})
    return pages, links


class NavigationIsAskedPerLanguageSection(unittest.TestCase):
    """`anchor_text_audit.navigation_links` — BL-081's classifier."""

    def test_a_per_language_menu_is_navigation(self):
        """The defect itself. 8 of 24 pages is 33%, under any sitewide share, so the
        whole-site question answers "no navigation here" and every menu link is graded
        as an editorial anchor."""
        pages, links = trilingual()
        chrome = anchor_text_audit.navigation_links(links, pages)
        self.assertEqual(len(chrome), 12, "4 menu entries x 3 languages")

    def test_the_menu_does_not_reach_a_sitewide_share_of_the_whole_crawl(self):
        """Pins *why* the fix is needed rather than the fix's own arithmetic. If this
        ever fails, the fixture stopped reproducing the bug and the test above is
        passing for a reason that has nothing to do with language sections."""
        pages, links = trilingual()
        html = [k for k, r in pages.items() if r["status"] == 200]
        reach = max(len({link["source"] for link in links
                         if (link["target"], link["anchor"]) == pair})
                    for pair in {(link["target"], link["anchor"]) for link in links})
        self.assertLess(reach, len(html) * anchor_text_audit.SITEWIDE_PAGE_SHARE)

    def test_a_monolingual_site_is_unchanged(self):
        """One language is one group, and the group is the whole crawl."""
        pages, links = trilingual(sections=("en",), per_section=10)
        self.assertEqual(len(anchor_text_audit.navigation_links(links, pages)), 4)

    def test_a_site_declaring_no_language_is_one_group(self):
        """An inventory written before `lang` existed, or a site with no `<html lang>`.
        Absence must not split every page into its own section."""
        pages, links = trilingual(sections=("en",), per_section=10)
        for row in pages.values():
            row["lang"] = None
        self.assertEqual(len(anchor_text_audit.navigation_links(links, pages)), 4)

    def test_region_subtags_are_one_section(self):
        """`en-GB` and `en-US` are one navigation. Splitting them would put a site that
        writes both back where it started, with each half under the floor."""
        pages, links = trilingual(sections=("en-GB",), per_section=4)
        more_pages, more_links = trilingual(sections=("en-US",), per_section=4)
        pages.update({k.replace("/page", "/us"): v for k, v in more_pages.items()})
        links += [dict(link, source=link["source"].replace("/page", "/us"),
                       anchor=link["anchor"].replace("en-US-", "en-GB-"))
                  for link in more_links]
        self.assertEqual(len(anchor_text_audit.navigation_links(links, pages)), 4)

    def test_stuffing_cannot_hide_in_a_language_section(self):
        """The thing BL-081 exists for. Five identical links from one page are five
        links from one source, and one page is never more than half of a section."""
        pages, links = trilingual()
        source = next(iter(pages))
        for _ in range(5):
            links.append({"source": source, "target": "https://example.com/money",
                          "anchor": "cheap flights"})
        chrome = anchor_text_audit.navigation_links(links, pages)
        self.assertNotIn(("https://example.com/money", "cheap flights"), chrome)

    def test_a_section_below_the_floor_is_not_generalised_from(self):
        """A two-page language stub is not evidence of a menu, for the same reason two
        pages are not evidence of one site-wide."""
        pages, links = trilingual(sections=("lt",), per_section=8)
        stub, stub_links = trilingual(sections=("de",), per_section=2)
        pages.update(stub)
        links += stub_links
        chrome = anchor_text_audit.navigation_links(links, pages)
        self.assertFalse([p for p in chrome if p[1].startswith("de-")])


class TheLanguageReachesTheClassifier(unittest.TestCase):
    """From an inventory to a verdict, through the projection in between.

    Written because the fix above did not work the first time and the tests above all
    passed anyway. `anchors_from_inventory` copies five fields out of each crawled page
    into the rows the classifier sees, and `lang` was not one of them — so the crawl
    recorded it, `navigation_links` read it, and nothing carried it across. Every page
    arrived declaring nothing, the whole site was one group again, and BL-081 still
    reported 21 overused targets on the live site.

    Calling `navigation_links` directly cannot see that, which is the point: a unit test
    of the function I changed passed while the behaviour I changed it for did not. This
    goes through the same door the runner does.
    """

    def inventory(self) -> dict:
        pages, links = trilingual()
        return {"pages": {url: {"status": 200, "html": True, "lang": row["lang"],
                                "final_url": url, "error": None, "depth": 1,
                                "links": [{"internal": True, "target": link["target"],
                                           "anchor": link["anchor"]}
                                          for link in links if link["source"] == url]}
                          for url, row in pages.items()}}

    def test_lang_survives_the_projection(self):
        crawl = anchor_text_audit.anchors_from_inventory(self.inventory())
        self.assertEqual({anchor_text_audit._lang_key(r) for r in crawl["pages"].values()},
                         {"lt", "en", "ru"})

    def test_a_translated_menu_reaches_the_verdict_as_navigation(self):
        """The end of the chain: BL-081's own field, on a site whose links are fine."""
        result = anchor_text_audit.audit_anchor_text(
            "https://example.com/", inventory=self.inventory())
        self.assertEqual(result["summary"]["overused_exact_match_targets"], 0)
        self.assertGreater(result["summary"]["navigation_links"], 0)


class SearchConsoleIssuesAreNotOpportunities(unittest.TestCase):
    """`gsc_checker.detect_issues` — the field GO-134 should have been reading."""

    def test_a_clean_sitemap_report_is_an_empty_list(self):
        clean = [{"path": "https://example.com/sitemap.xml", "errors": "0",
                  "warnings": "0"}]
        self.assertEqual(gsc_checker.detect_issues(clean), [])

    def test_string_counts_are_read_as_numbers(self):
        """The API returns `"0"`, and every count is truthy as a string. This is the
        whole reason the helper is not `s.get("errors", 0) > 0`."""
        self.assertEqual(gsc_checker.detect_issues(
            [{"path": "s.xml", "errors": "0", "warnings": "0"}]), [])
        errors = gsc_checker.detect_issues(
            [{"path": "s.xml", "errors": "3", "warnings": "0"}])
        self.assertEqual([i["severity"] for i in errors], ["high"])

    def test_warnings_are_medium_so_they_warn_rather_than_fail(self):
        found = gsc_checker.detect_issues(
            [{"path": "s.xml", "errors": "0", "warnings": "2"}])
        self.assertEqual([i["severity"] for i in found], ["medium"])

    def test_an_unreadable_sitemap_report_is_none_not_clean(self):
        """`None` keeps the item at NO_DATA. `[]` would pass it on an answer nobody
        got, which is `missing_is: pass` one field along."""
        self.assertIsNone(gsc_checker.detect_issues([{"error": "403 forbidden"}]))
        self.assertIsNone(gsc_checker.detect_issues("not a list"))

    def test_every_issue_carries_a_finding_and_a_fix(self):
        """What the report prints. An issue without either is a line a reader cannot
        act on."""
        for issue in gsc_checker.detect_issues(
                [{"path": "s.xml", "errors": "1", "warnings": "1"}]):
            self.assertTrue(issue["finding"])
            self.assertTrue(issue["fix"])
            self.assertIn(issue["severity"], ("critical", "high", "medium", "low"))


if __name__ == "__main__":
    unittest.main()
