"""Restore metadata erased by reduced-schema hand-keyed CSV merges.

Some hand-keyed staging files contained only question text, options, key, and
explanation.  ``merge_keyed_questions.py`` used to accept those files and fill
every omitted bank column with an empty string, silently dropping provenance
and difficulty metadata.  The original rows remain in
``data/staging/jamb_archive_unkeyed.csv``, so the repair is deterministic by
question ID while preserving the hand-entered answer, explanation, and draft
status.

The write is backup-then-atomic-replace rather than a direct rewrite of the
live bank; an interrupted process therefore cannot leave a truncated CSV.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import shutil
import sys
from collections import Counter


csv.field_size_limit(10 ** 7)
REPO = pathlib.Path(__file__).resolve().parents[1]
BANK = REPO / "data" / "questions.csv"
SOURCE = REPO / "data" / "staging" / "jamb_archive_unkeyed.csv"

RESTORE_FIELDS = [
    "exam_type", "topic", "subtopic", "difficulty", "year", "passage_id",
    "image_url", "tags", "source",
]


def load(path: pathlib.Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def needs_repair(row: dict[str, str], source_ids: set[str]) -> bool:
    return (
        row.get("question_id", "") in source_ids
        and not row.get("exam_type", "")
        and not row.get("difficulty", "")
        and not row.get("source", "")
    )


def repair_rows(
    bank: list[dict[str, str]], source: dict[str, dict[str, str]]
) -> list[dict[str, str]]:
    repaired: list[dict[str, str]] = []
    source_ids = set(source)
    for row in bank:
        if not needs_repair(row, source_ids):
            continue
        original = source[row["question_id"]]
        for field in RESTORE_FIELDS:
            row[field] = original.get(field, "")
        row["tags"] = row["tags"].replace("needs-key", "hand-keyed")
        repaired.append(row)
    return repaired


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    fields, bank = load(BANK)
    _, source_rows = load(SOURCE)
    source = {row["question_id"]: row for row in source_rows}
    repaired = repair_rows(bank, source)

    print(f"bank rows                 : {len(bank):,}")
    print(f"archive source rows       : {len(source):,}")
    print(f"rows needing restoration : {len(repaired):,}")
    for subject, count in Counter(row["subject"] for row in repaired).most_common():
        print(f"  {subject:12s} {count:5d}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to restore metadata.")
        return 0
    if not repaired:
        print("nothing to do")
        return 0

    temp = BANK.with_suffix(".csv.metadata-repair.tmp")
    backup = BANK.with_suffix(".csv.metadata-repair.bak")
    with temp.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(bank)
    shutil.copy2(BANK, backup)
    temp.replace(BANK)
    print(f"backup -> {backup}")
    print(f"wrote  -> {BANK}")

    _, verify = load(BANK)
    remaining = [row for row in verify if needs_repair(row, set(source))]
    if remaining:
        print(f"ERROR: {len(remaining)} rows still need repair")
        return 1
    print(f"verified {len(verify):,} rows; no repairable metadata gaps remain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
