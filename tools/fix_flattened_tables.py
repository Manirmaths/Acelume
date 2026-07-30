"""
Convert flattened two-row tables in question_text into real table markup.

Some imported questions had their table pasted in as a run of prose:

    Marks 2 3 4 5 6 7 8 No. of students 3 1 5 2 4 2 3 from the table above...

which is unreadable, and in several cases makes the question unanswerable.
This rewrites them into the <table> markup that
`frontend/src/components/ui/QuestionText.tsx` renders as a real HTML table.

    python tools/fix_flattened_tables.py            # dry run
    python tools/fix_flattened_tables.py --apply

Scope is deliberately narrow: exactly two parallel rows (a label followed by
N values, twice, with N matching). Questions mentioning a "table" that are
NOT tables are left alone -- "Hallowell's The Dining Table" is a poem, and
"sit round a circular table" is a permutations question. Wider tables and
those with no recoverable data need a human or an image.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.csv"

NUM = r"-?\d{1,3}(?:,\d{3})+|-?\d+(?:\.\d+)?"
PAIR = re.compile(
    rf"(?P<l1>(?:[A-Za-z][A-Za-z.']*\s+){{0,3}}[A-Za-z][A-Za-z.']*)\s+"
    rf"(?P<r1>(?:(?:{NUM})\s+){{2,}}(?:{NUM}))\s+"
    rf"(?P<l2>(?:[A-Za-z][A-Za-z.']*\s+){{0,3}}[A-Za-z][A-Za-z.']*)\s+"
    rf"(?P<r2>(?:(?:{NUM})\s+){{2,}}(?:{NUM}))"
)

# The label regex greedily takes up to four preceding words, which sometimes
# swallows the end of the sentence before the table. These say where the real
# label starts.
LABEL_FIX: dict[str, str] = {
    "MTH-0411": "Mark",
    "MTH-0412": "Mark",
    "MTH-0430": "x",
    "MTH-0490": "No of goals",
}

# Matches the two-row pattern but isn't a two-row table. Converting these would
# capture the first two rows and strand the rest as prose -- worse than leaving
# them alone.
SKIP: dict[str, str] = {
    "ACC-0483": "Three columns (Total, P, Q) and at least four rows (Stock, Sales, "
                "Purchase, ...). Needs a full multi-row table, by hand or from the "
                "original paper.",
}


def build_table(l1: str, r1: list[str], l2: str, r2: list[str]) -> str:
    head = "".join(f"<th>{html.escape(v)}</th>" for v in r1)
    body = "".join(f"<td>{html.escape(v)}</td>" for v in r2)
    return (
        "<table>"
        f"<tr><th>{html.escape(l1)}</th>{head}</tr>"
        f"<tr><td>{html.escape(l2)}</td>{body}</tr>"
        "</table>"
    )


def convert(qid: str, text: str) -> str | None:
    m = PAIR.search(text)
    if not m:
        return None
    r1 = re.findall(NUM, m.group("r1"))
    r2 = re.findall(NUM, m.group("r2"))
    if len(r1) != len(r2) or len(r1) < 3:
        return None

    l1_raw = m.group("l1").strip()
    start = m.start("l1")
    wanted = LABEL_FIX.get(qid)
    if wanted:
        idx = l1_raw.rfind(wanted)
        if idx == -1:
            return None
        start += idx
        l1 = wanted
    else:
        l1 = l1_raw

    prefix = text[:start].rstrip()
    suffix = text[m.end():].lstrip()
    table = build_table(l1, r1, m.group("l2").strip(), r2)
    return " ".join(p for p in (prefix, table, suffix) if p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)

    changed = 0
    for row in rows:
        q = row["question_text"] or ""
        if not q or "<table" in q or "\\begin{array}" in q or row["image_url"]:
            continue
        if row["question_id"] in SKIP:
            continue
        new = convert(row["question_id"], q)
        if not new or new == q:
            continue
        changed += 1
        print(f"[{row['question_id']}|{row['subject']}]")
        print(f"   -  {q[:150]}")
        print(f"   +  {new[:150]}")
        if args.apply:
            row["question_text"] = new

    print(f"\n{changed} questions converted")
    if SKIP:
        print("\nNEEDS HUMAN REVIEW (matches the pattern but isn't a two-row table):")
        for qid, why in SKIP.items():
            print(f"  [{qid}] {why}")

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
