"""The recorded verdict census, kept in step with the registry it describes.

`tests/census.json` is a measurement, not a declaration: it records what every item
answered on every tree this repository can serve. Its value is the range — an item
that gave one answer everywhere is either a rule that cannot give another or a
question every site answers the same way, and those two are worth telling apart.

Recomputing it costs four full audits, so this module does not do that. It checks the
cheap invariants that make a stale record impossible to ignore: the census describes
*this* registry, and it describes every item in it. Re-record with

    python tests/verdict_census.py --out tests/census.json

whenever the registry moves, and read the report it prints while you are there.
"""
from __future__ import annotations

import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CENSUS = os.path.join(ROOT, "tests", "census.json")
REGISTRY = os.path.join(ROOT, "skills", "seo-checklist", "resources", "config",
                        "checklist.json")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


class RecordedCensus(unittest.TestCase):

    def setUp(self):
        self.census = load(CENSUS)
        self.registry = load(REGISTRY)

    def test_it_describes_this_registry(self):
        """A census taken against an older contract describes a checklist that no
        longer exists, and the difference is invisible from inside the file."""
        self.assertEqual(self.census["registry_version"],
                         self.registry["registry_version"],
                         "tests/census.json was taken against a different registry — "
                         "re-record it with tests/verdict_census.py")

    def test_every_item_is_accounted_for(self):
        self.assertEqual(set(self.census["items"]),
                         {i["id"] for i in self.registry["items"]})
        self.assertEqual(self.census["item_count"], self.registry["item_count"])

    def test_every_item_was_asked_on_every_site(self):
        """A missing answer is the census failing to run an item, not an item
        declining to answer; the two must not be readable as the same thing."""
        sites = set(self.census["sites"])
        self.assertTrue(sites, "the census names no site")
        for item_id, row in self.census["items"].items():
            self.assertEqual(set(row["answers"]), sites, item_id)
            self.assertNotIn("MISSING", row["distinct"], item_id)


if __name__ == "__main__":
    unittest.main()
