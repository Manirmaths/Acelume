"""
Replace ASCII stand-ins with the real typographic symbols in the question bank.

Imported questions use keyboard approximations that read poorly to students:
reaction arrows as `----->`, equilibrium as `<=>`, inequalities as `<=`.

    python tools/fix_ascii_symbols.py            # dry run
    python tools/fix_ascii_symbols.py --apply

Deliberately NOT replaced:

  `!=`  -- every occurrence in this bank is a FACTORIAL followed by an equals
           sign ("8!/3!=6720", "P(5,3)=5!/2!=60"), not "not equal to".
           Rewriting those to the not-equal glyph would turn correct
           permutation working into nonsense.

Order matters below: `<=>` must be handled before `<=`, and `----->` before
`->`, or the shorter pattern eats part of the longer one.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.csv"
FIELDS = ["question_text", "option_a", "option_b", "option_c", "option_d", "explanation"]

REPLACEMENTS: list[tuple[str, str, str]] = [
    (r"<=+>", "⇌", "equilibrium arrow"),      # ⇌  -- before <=
    (r"-{2,}>", "→", "long reaction arrow"),  # →  -- before ->
    (r"(?<![-<!])->", "→", "reaction arrow"),  # →
    (r"<=(?!>)", "≤", "less than or equal"),  # ≤
    (r">=", "≥", "greater than or equal"),    # ≥
]


def apply_all(value: str) -> tuple[str, list[str]]:
    """Rewrite a single field. Math inside \\( ... \\) is left alone -- KaTeX
    has its own commands there and a raw glyph could break rendering."""
    parts = re.split(r"(\\\(.+?\\\))", value, flags=re.S)
    used: list[str] = []
    for i, part in enumerate(parts):
        if part.startswith("\\("):
            continue
        for pattern, glyph, label in REPLACEMENTS:
            new, n = re.subn(pattern, glyph, part)
            if n:
                part = new
                used.append(label)
        parts[i] = part
    return "".join(parts), used


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)

    changed = 0
    questions: set[str] = set()
    shown = 0
    for row in rows:
        for f in FIELDS:
            old = row.get(f) or ""
            if not old:
                continue
            new, used = apply_all(old)
            if new == old:
                continue
            changed += 1
            questions.add(row["question_id"])
            if shown < 12:
                shown += 1
                print(f"[{row['question_id']}] {f}  ({', '.join(sorted(set(used)))})")
                print(f"   -  {old[:120]}")
                print(f"   +  {new[:120]}")
            if args.apply:
                row[f] = new

    print(f"\n{changed} fields across {len(questions)} questions")

    if args.apply:
        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("written to data/questions.csv")
    else:
        print("(dry run -- pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
