"""
Merge keyed questions from data/staging/ into data/questions.csv.

Deliberately the last step and deliberately separate: everything upstream is
reversible, and this is the point where content becomes something the app can
serve. It refuses to merge anything without a key, and it never silently
promotes a row to `active`.

Publishing is a second, explicit decision:

    python tools/merge_keyed_questions.py --in data/staging/jamb_archive_keyed.csv
    python tools/merge_keyed_questions.py --in ... --apply
    python tools/merge_keyed_questions.py --in ... --apply --publish   # status=active

Without --publish, rows land as drafts. Students see nothing until you say so,
which is what you want after a bulk automated keying run: seed the database,
look at a few dozen in the admin UI, then publish.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
import shutil
import sys
from collections import Counter

csv.field_size_limit(10 ** 7)
REPO = pathlib.Path(__file__).resolve().parents[1]
BANK = REPO / "data" / "questions.csv"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (s or "").lower())).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--bank", default=str(BANK))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="set status=active (default: keep as draft)")
    args = ap.parse_args()

    bank_path = pathlib.Path(args.bank)
    with open(bank_path, encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        bank = [dict(r) for r in reader]
    idcol = fields[0]                      # may carry a BOM
    have_ids = {r[idcol] for r in bank}
    have_text = {norm(r["question_text"]) for r in bank}

    with open(args.infile, encoding="utf-8-sig") as fh:
        incoming = [dict(r) for r in csv.DictReader(fh)]

    add, skipped = [], Counter()
    for r in incoming:
        qid = r.get("question_id") or r.get(idcol, "")
        if r.get("correct_option") not in ("A", "B", "C", "D"):
            skipped["no answer key"] += 1
            continue
        if not (r.get("explanation") or "").strip():
            skipped["no explanation"] += 1
            continue
        if qid in have_ids:
            skipped["question_id already in bank"] += 1
            continue
        if norm(r.get("question_text", "")) in have_text:
            skipped["duplicate question text"] += 1
            continue
        row = {c: "" for c in fields}
        for c in fields:
            key = c.lstrip("﻿")
            if key in r:
                row[c] = r[key]
        row[idcol] = qid
        row["status"] = "active" if args.publish else "draft"
        add.append(row)
        have_ids.add(qid)
        have_text.add(norm(r.get("question_text", "")))

    print(f"bank            : {len(bank)} questions")
    print(f"incoming        : {len(incoming)}")
    print(f"will add        : {len(add)}  as {'ACTIVE' if args.publish else 'draft'}")
    if skipped:
        print("skipped:")
        for why, n in skipped.most_common():
            print(f"    {why:32s} {n}")
    if add:
        print("\nby subject:")
        for s, n in Counter(r["subject"] for r in add).most_common():
            print(f"    {s:12s} {n}")
        print(f"\nbank after merge: {len(bank) + len(add)}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
        return 0
    if not add:
        print("nothing to do")
        return 0

    backup = bank_path.with_suffix(".csv.bak")
    shutil.copy2(bank_path, backup)
    with open(bank_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(bank + add)
    print(f"backup  -> {backup}")
    print(f"wrote   -> {bank_path}  ({len(bank) + len(add)} rows)")
    print("\nNext: run the sync-questions GitHub Action (dry_run: false) to push")
    print("these to production. Nothing reaches students until then.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
