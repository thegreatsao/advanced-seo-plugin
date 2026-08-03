#!/usr/bin/env python3
"""Find registry assertions that can never fire.

`none_matching` returns PASS when nothing matches. So an assertion aimed at
wording its script does not emit — or emits in a different word order — reports
PASS for every site, forever, silently. Fifteen of the registry's twenty-one
pattern assertions were in exactly that state when this was first run: three
asked an accessibility checker about font sizes it never measures, two asked a
mobile checker about interstitials it never looks for, and one wanted "lazy"
before "LCP" in a message that says "LCP image is lazy-loaded".

This scans each producing script for the strings it can actually emit and reports
any pattern that matches none of them.

    python3 tools/audit_assertions.py            # report, exit 1 if any are dead
    python3 tools/audit_assertions.py --verbose   # show every assertion

Prose is not the only way to answer an item and usually not the best one: prefer
a counted field or a `value_map` over the script's own vocabulary, both of which
report NO_DATA when the field is absent instead of passing.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL_DIR, "scripts")
REGISTRY = os.path.join(SKILL_DIR, "resources", "config", "checklist.json")

PATTERN_OPS = ("matching", "none_matching", "any_matching", "matches")

# Paths whose value comes from the audited page rather than from the script's own
# vocabulary. A pattern over one of these is checking the site, not the script's
# wording, so there is nothing in the source to match it against.
PAGE_DERIVED = {
    ("parse_html.py", "meta_robots"),
}


def assertions(registry_path: str = REGISTRY) -> list[dict]:
    """Every pattern assertion in the registry, with the script that answers it."""
    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)
    found: list[dict] = []

    def walk(node, item):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in PATTERN_OPS:
                    pattern = value[0] if key == "count_matching_lte" else value
                    found.append({"id": item["id"], "script": item["check"]["script"],
                                  "path": node.get("path"), "op": key,
                                  "pattern": pattern})
                else:
                    walk(value, item)
        elif isinstance(node, list):
            for value in node:
                walk(value, item)

    for item in registry["items"]:
        if item.get("check"):
            walk(item["check"], item)
    return found


def emittable_strings(script: str) -> list[str]:
    """String literals a script can put in its output.

    Docstrings and argparse text are excluded. Both describe what a script is
    for using the same words its findings would, and counting them made dead
    assertions look alive: the one pattern this tool initially cleared was
    matching `robots_checker.py`'s module docstring, which mentions CSS and
    JavaScript while the script itself never reports on either.
    """
    with open(os.path.join(SCRIPTS, script), encoding="utf-8") as f:
        tree = ast.parse(f.read())

    documentation: set[int] = set()
    for node in ast.walk(tree):
        # Docstrings: the first statement of a module, class or function.
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                documentation.add(id(first.value))
        # Argparse prose: --help text says the same things the output does.
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name in ("add_argument", "ArgumentParser", "add_parser", "print_help"):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        documentation.add(id(sub))

    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in documentation]


def audit(registry_path: str = REGISTRY) -> list[dict]:
    """Every assertion whose pattern cannot match anything its script emits."""
    dead = []
    for row in assertions(registry_path):
        if (row["script"], row["path"]) in PAGE_DERIVED:
            continue
        try:
            candidates = emittable_strings(row["script"])
        except (OSError, SyntaxError) as exc:
            dead.append(dict(row, reason=f"cannot read script: {exc}"))
            continue
        if not any(re.search(row["pattern"], text) for text in candidates):
            dead.append(dict(row, reason="matches nothing the script emits"))
    return dead


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", default=REGISTRY)
    ap.add_argument("--verbose", action="store_true",
                    help="list every pattern assertion, not just the dead ones")
    a = ap.parse_args()

    every = assertions(a.registry)
    dead = audit(a.registry)
    if a.verbose:
        bad = {(d["id"], d["pattern"]) for d in dead}
        for row in sorted(every, key=lambda r: r["script"]):
            mark = "DEAD" if (row["id"], row["pattern"]) in bad else "ok  "
            print(f"{mark} {row['id']:9}{row['script']:30}{row['pattern'][:40]}")

    print(f"\n{len(every)} pattern assertion(s), {len(dead)} that can never fire")
    for d in dead:
        print(f"  {d['id']} {d['script']} {d['path']} "
              f"{d['op']}={d['pattern']!r} — {d['reason']}", file=sys.stderr)
    if dead:
        print("\nEach of these reports PASS for every site. Replace the pattern "
              "with a counted field or a value_map over the script's own "
              "vocabulary, or move the item to whoever can answer it.",
              file=sys.stderr)
    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())
