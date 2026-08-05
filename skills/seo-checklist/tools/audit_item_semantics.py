#!/usr/bin/env python3
"""Does each item assert what its title says, and does any pair assert the same thing?

Two questions the registry has never been asked, both found by one live audit in
0.20 and neither catchable by the fixture pair — the good fixture is *built* to
satisfy the registry, so an item that accuses every real site passes on it as long
as somebody tuned the fixture for that item. `tests/fixtures/good/robots.txt`
disallows exactly the four paths CI-019 tests, with a comment saying so.

1. DUPLICATES are mechanical and exact: two items sharing script, args and
   assertion are one check scored twice. CI-016/MD-186 do, both `high`, so one
   image missing an `alt` produced two high FAILs on a real site — double weight in
   the headline and two rows in --fixes.

2. VOCABULARY is a heuristic and says so. It compares the words in what an item
   *claims* (title + fix text) against the words in what it *does* (script name +
   assertion path). No overlap is not proof of a defect — plenty of correct items
   name a field nothing in their prose could mention. It is a reading list, and
   REVIEWED below is where a human's answer goes so the list does not have to be
   re-read every run.

Exit 1 on any duplicate, or on an unreviewed vocabulary miss. Reviewing an item is
writing down which of the three is wrong, or that none of them is.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent.parent / "resources/config/checklist.json"

# Words that carry no discriminating meaning in either half of the comparison.
STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "check", "checks", "do", "does",
    "for", "from", "has", "have", "in", "is", "it", "not", "of", "on", "or", "own",
    "py", "review", "run", "set", "site", "the", "them", "then", "there", "to", "up",
    "use", "used", "using", "via", "want", "was", "with", "your", "avoid", "ensure",
    "keep", "make", "provide", "raw", "summary", "value", "values", "len", "count",
    "counts", "total", "all", "any", "each", "every", "no", "none", "one", "only",
}

# A vocabulary miss that a human has read and ruled on. The value is the ruling —
# what is wrong, or why nothing is. An id here is not silenced, it is answered.
REVIEWED: dict[str, str] = {
    "CI-019": "DEFECT (0.20). Title and fix say noindex; the assertion tests robots.txt "
              "allow/deny, and the script never fetches the path so a 404 counts as "
              "exposed. Two repairs: existence, and decide which check this is.",
    "CN-053": "DEFECT (0.20). Title and fix are about iframes; the assertion counts "
              "words (raw.word_count >= 300). Nothing in the item observes an iframe.",
    "TE-179": "DEFECT (0.20). 'Domain history and reputation' is asserted as "
              "whois.age_days >= 90. A new domain is not a reputation problem and no "
              "work closes the item; it closes itself.",
    "GO-134": "DEFECT (0.20). 'Resolve Search Console issues' reads `opportunities` "
              "through a severity gate, so position 4.0 with 115 impressions printed "
              "as a high failure. An opportunity is not a defect at any threshold.",
}


def tokens(text: str) -> set[str]:
    """Words, with snake_case and dotted paths split and camelCase broken up."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text or "")
    return {w for w in re.split(r"[^a-zA-Z0-9]+", text.lower()) if len(w) > 2 and w not in STOP}


def assertion_paths(rule: object) -> list[str]:
    """Every `path` in an assertion, including inside any/all branches."""
    found = []
    if isinstance(rule, dict):
        if isinstance(rule.get("path"), str):
            found.append(rule["path"])
        for value in rule.values():
            found.extend(assertion_paths(value))
    elif isinstance(rule, list):
        for value in rule:
            found.extend(assertion_paths(value))
    return found


def main() -> int:
    items = json.loads(REGISTRY.read_text())["items"]
    failures = []

    # 1. Duplicates — exact, no judgement involved.
    by_shape = defaultdict(list)
    for item in items:
        check = item.get("check") or {}
        if not check.get("script"):
            continue
        shape = (check["script"],
                 json.dumps(check.get("args"), sort_keys=True),
                 json.dumps(check.get("assert"), sort_keys=True))
        by_shape[shape].append(item)

    print("== items sharing script, args and assertion ==")
    duplicates = {shape: group for shape, group in by_shape.items() if len(group) > 1}
    if not duplicates:
        print("  none")
    for shape, group in sorted(duplicates.items(), key=lambda kv: kv[1][0]["id"]):
        ids = ", ".join(f"{i['id']} ({i['severity']})" for i in group)
        print(f"  {ids}")
        print(f"      {shape[0]} {shape[1]}  assert {shape[2]}")
        for item in group:
            print(f"      {item['id']}: {item['title']}")
        failures.append(f"{ids} are one check scored {len(group)} times")

    # 2. Vocabulary — a heuristic, and the output is a reading list.
    print("\n== items whose assertion shares no vocabulary with their own title ==")
    unreviewed = []
    for item in items:
        check = item.get("check") or {}
        paths = assertion_paths(check.get("assert"))
        if not check.get("script") or not paths:
            continue
        claims = tokens(item["title"]) | tokens(item.get("fix", ""))
        does = tokens(check["script"]) | {t for p in paths for t in tokens(p)}
        if claims & does:
            continue
        ruling = REVIEWED.get(item["id"])
        mark = "reviewed" if ruling else "UNREVIEWED"
        print(f"  [{mark}] {item['id']} ({item['severity']}) {item['title']}")
        print(f"      {check['script']} asserts {', '.join(sorted(set(paths)))}")
        if ruling:
            print(f"      -> {ruling}")
        else:
            unreviewed.append(item["id"])

    for item_id in unreviewed:
        failures.append(f"{item_id} asserts nothing its title mentions and nobody has ruled on it")

    total = len(items)
    print(f"\n{total} items · {len(duplicates)} duplicate group(s) · "
          f"{len(REVIEWED)} reviewed · {len(unreviewed)} unreviewed")

    if failures:
        print("\nFAIL")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
