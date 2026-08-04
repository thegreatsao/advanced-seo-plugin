#!/usr/bin/env python3
"""Every number a verdict rests on, and what each one rests on in turn.

§2 of KNOWN-ISSUES.md names the gap this closes: **a test can show that a threshold
fires; it cannot show the threshold is right.** Four layers of tests prove that a
named field answers a named question, that a check can tell two sites apart, that
nothing is decided about a site which answered nothing. None of them argues with the
numbers. A site audited at the wrong threshold gets a confident verdict about the
wrong question, and that is what this suite is worst at seeing.

Calibration is not more tests. It is deciding, per threshold, what the number rests
on, and writing that down beside it — so a reader who disagrees can see the basis
instead of arguing with a verdict whose grounds are invisible. This tool is what
makes "written down beside it" checkable rather than aspirational.

    python3 tools/audit_thresholds.py            # the inventory, and the gaps
    python3 tools/audit_thresholds.py --check    # non-zero if any named one is bare

**The convention.** A module-level numeric constant that a comparison reads is a
threshold, and it must carry a line of the form

    # basis: <kind> — <what it rests on>

in the comment block above it, or in its own trailing comment. Four kinds, and the
distinction between them is the whole point:

  standard    An external published authority, named in the text. Google's Core Web
              Vitals bands, an RFC, a WCAG level. The number is not ours and a reader
              can go and check it.
  measured    Calibrated against something, and the text says against what. This is
              the only kind that is evidence rather than judgement.
  convention  A judgement made here. A round number, chosen because a line had to be
              somewhere. Saying so is the point: it invites the argument instead of
              hiding from it.
  inherited   Arrived with borrowed code and has not been examined. **Not an excuse —
              a to-do with a name.** The count is printed, and it is the honest
              measure of how much of this registry rests on numbers nobody here
              decided.

**Unnamed thresholds are counted separately and not excused.** A comparison against a
bare literal cannot carry a basis, because it has no name to hang one on — the first
step for those is a constant, not a comment. The count is a ceiling in CI rather than
a list, for the same reason the request count is: a printed number in a green build is
a number nobody reads.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")

BASIS = re.compile(r"#\s*basis:\s*(standard|measured|convention|inherited)\s*[—-]\s*(\S.*)",
                   re.I)
KINDS = ("standard", "measured", "convention", "inherited")

# Numbers that are not thresholds, and excluding them is what keeps this tool worth
# reading. An HTTP status code is an identity, not a limit: `status == 404` asks which
# answer arrived, and there is no version of it that could be "calibrated". Same for
# the arithmetic constants — a comparison against 0 or 1 is almost always "is there
# any" or "is there more than one".
HTTP_STATUS = frozenset(range(100, 600))
ARITHMETIC = frozenset({0, 1, 2, -1, 100, 1000, 1024})
# A comparison is about a status code when the other side says so. Checked by name
# rather than by value, because 200 is also a perfectly good byte count.
STATUS_WORDS = re.compile(r"\b(status|status_code|code|http_status|response_code)\b")


def _numeric(node: ast.AST) -> bool:
    """Whether an expression is, or contains, a number worth calling a threshold."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, (ast.Dict, ast.Tuple, ast.List, ast.Set)):
        parts = list(getattr(node, "values", [])) + list(getattr(node, "elts", []))
        return bool(parts) and any(_numeric(p) for p in parts)
    if isinstance(node, ast.BinOp):          # 5 * 1024 * 1024
        return _numeric(node.left) or _numeric(node.right)
    if isinstance(node, ast.UnaryOp):
        return _numeric(node.operand)
    return False


def _names_in(node: ast.AST) -> set[str]:
    """Every constant a comparison reads, including through a subscript.

    The subscript case is not an edge case — it is where the most consequential
    thresholds in this tree live. `cwv_metrics.THRESHOLDS["lcp_ms"]["good"]` is
    Google's LCP band, and a scan that only looked at bare `Name` nodes in a
    comparison would report it as absent while it decided three items.
    """
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            found.add(sub.id)
    return found


def _basis_for(src_lines: list[str], lineno: int) -> tuple[str, str]:
    """The `# basis:` line for an assignment at `lineno`, searching upward.

    Its own trailing comment first, then the contiguous comment block above it. A
    blank line ends the block: a basis three paragraphs up belongs to something else.
    """
    own = src_lines[lineno - 1]
    match = BASIS.search(own)
    if match:
        return match.group(1).lower(), match.group(2).strip()
    i = lineno - 2
    while i >= 0:
        line = src_lines[i].strip()
        if not line:
            break
        if not line.startswith("#"):
            break
        match = BASIS.search(line)
        if match:
            return match.group(1).lower(), match.group(2).strip()
        i -= 1
    return "", ""


def named_thresholds(path: str) -> list[dict]:
    """Module-level numeric constants that a comparison in this file reads."""
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    lines = src.splitlines()
    tree = ast.parse(src)

    consts: dict[str, int] = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id.isupper() and _numeric(node.value)):
            consts[node.targets[0].id] = node.lineno

    # Ordering comparisons only. A constant that is only ever tested for equality is
    # an **identity, not a threshold**: `inventory_version != INVENTORY_VERSION` asks
    # which format this file is, and there is no version of that question a
    # calibration could improve. Asking for a basis there would train the reader to
    # skim past the ones that have one.
    ordering = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
    compared: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if any(isinstance(op, ordering) for op in node.ops):
                compared |= _names_in(node)
        # A number handed to min/max is a bound as surely as one in a comparison.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ("min", "max"):
            for arg in node.args:
                compared |= _names_in(arg)
        # A numeric table whose values are looked up at all. Following the value to
        # the comparison would need dataflow the AST does not give for free, and the
        # cost of not trying was concrete: `cwv_metrics.THRESHOLDS` holds Google's
        # Core Web Vitals bands, is read as `limits = THRESHOLDS[metric]` and then
        # compared as `value <= limits["good"]`, and a scan that only looked inside
        # `Compare` nodes reported the most authoritative numbers in the tree as
        # absent while they decided six items. Over-including a lookup table that
        # turns out to decide nothing costs one line of explanation; missing those
        # cost the whole point of the tool.
        elif isinstance(node, (ast.Subscript, ast.Attribute)):
            compared |= _names_in(node.value)

    out = []
    for name, lineno in sorted(consts.items(), key=lambda kv: kv[1]):
        if name not in compared:
            continue
        kind, why = _basis_for(lines, lineno)
        out.append({"file": os.path.relpath(path, SKILL), "name": name,
                    "line": lineno, "kind": kind, "why": why})
    return out


def unnamed_thresholds(path: str) -> list[dict]:
    """Comparisons against a bare number, excluding status codes and arithmetic."""
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    lines = src.splitlines()
    out = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Compare):
            continue
        text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
        about_status = bool(STATUS_WORDS.search(text))
        for side in [node.left, *node.comparators]:
            if not isinstance(side, ast.Constant):
                continue
            value = side.value
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            if value in ARITHMETIC:
                continue
            if about_status and value in HTTP_STATUS and float(value).is_integer():
                continue
            out.append({"file": os.path.relpath(path, SKILL), "line": node.lineno,
                        "value": value, "source": text.strip()[:90]})
    return out


def scan() -> tuple[list[dict], list[dict]]:
    named, unnamed = [], []
    for folder in (SCRIPTS, os.path.join(SCRIPTS, "lib")):
        for entry in sorted(os.listdir(folder)):
            if not entry.endswith(".py") or entry == "__init__.py":
                continue
            path = os.path.join(folder, entry)
            named += named_thresholds(path)
            unnamed += unnamed_thresholds(path)
    return named, unnamed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Inventory every number a verdict depends on",
        epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if a named threshold has no basis")
    ap.add_argument("--unnamed", action="store_true",
                    help="list the comparisons against a bare number")
    ap.add_argument("--kind", default="", choices=("", *KINDS),
                    help="list only thresholds of this kind")
    a = ap.parse_args()

    named, unnamed = scan()
    bare = [t for t in named if not t["kind"]]
    by_kind = {k: [t for t in named if t["kind"] == k] for k in KINDS}

    if a.kind:
        for t in by_kind[a.kind]:
            print(f"  {t['file']}:{t['line']}  {t['name']}\n      {t['why']}")
        print(f"\n{len(by_kind[a.kind])} {a.kind} threshold(s)")
        return 0

    if a.unnamed:
        for t in unnamed:
            print(f"  {t['file']}:{t['line']}  {t['value']}   {t['source']}")
        print(f"\n{len(unnamed)} comparison(s) against a bare number")
        return 0

    print(f"{len(named)} named threshold(s) a verdict depends on:")
    for kind in KINDS:
        print(f"  {kind:<11} {len(by_kind[kind]):>3}")
    print(f"  {'no basis':<11} {len(bare):>3}")
    print(f"\n{len(unnamed)} threshold(s) still unnamed — a comparison against a bare "
          f"number cannot carry a basis, so the first step for those is a constant")

    if bare:
        print("\nNamed, and resting on nothing stated:")
        for t in bare:
            print(f"  {t['file']}:{t['line']}  {t['name']}")
        if a.check:
            print("\nAdd a `# basis: standard|measured|convention|inherited — why` "
                  "line above each. `inherited` is allowed and counted: a number that "
                  "arrived with borrowed code and has not been examined is a to-do "
                  "with a name, which is worth more than a number with neither.",
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
