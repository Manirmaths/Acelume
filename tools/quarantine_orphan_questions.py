"""
Find and quarantine questions that reference material the student cannot see.

Discovered by the 2025 English key audit. 192 Reading Comprehension and Cloze
questions are live and ask things like:

    "What was the common ritual at the morning assembly at Stardom on Tuesdays
     and Thursdays?"
    "Who instructed the Chemistry teacher to conclude the assembly after Mr Bepo
     burst into tears?"

There is no Stardom, no Mr Bepo, and no passage. `passage_id` is empty, and
data/passages.csv holds two rows for the whole bank. The comprehension text was
never imported.

This is not a wrong answer key. It is a question **nobody can answer** -- not
the model, and not the student, who sees the same thing the model saw. Every one
of the 192 also has an empty explanation, so a student who guesses wrong is told
nothing. They fail, and learn that they are bad at comprehension.

That is worse than a wrong key, and it has been in production the whole time.

Quarantining sets status=draft, which removes them from practice, quizzes and
mocks without deleting anything. They come back the moment their passages are
imported.

    python tools/quarantine_orphan_questions.py
    python tools/quarantine_orphan_questions.py --apply
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

# Topics that are meaningless without an accompanying text.
PASSAGE_TOPICS = {"Reading Comprehension", "Cloze Test"}


def is_orphan(row: dict, known_passages: set[str]) -> str:
    """Return a reason if this question depends on text that is not available."""
    pid = (row.get("passage_id") or "").strip()
    if row.get("topic") in PASSAGE_TOPICS:
        if not pid:
            return "comprehension question with no passage_id"
        if pid not in known_passages:
            return f"passage_id {pid!r} not found in passages.csv"
    elif pid and pid not in known_passages:
        return f"passage_id {pid!r} not found in passages.csv"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=str(REPO / "data" / "questions.csv"))
    ap.add_argument("--passages", default=str(REPO / "data" / "passages.csv"))
    ap.add_argument("--out", default=str(REPO / "data" / "staging" / "orphan_questions.csv"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    bank_path = pathlib.Path(args.bank)
    with open(bank_path, encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        rows = [dict(r) for r in reader]
    idcol = fields[0]

    known = set()
    ppath = pathlib.Path(args.passages)
    if ppath.exists():
        with open(ppath, encoding="utf-8-sig") as fh:
            known = {(r.get("passage_id") or "").strip()
                     for r in csv.DictReader(fh) if (r.get("passage_id") or "").strip()}

    flagged = []
    for r in rows:
        why = is_orphan(r, known)
        if why:
            flagged.append((r, why))

    active = [(r, w) for r, w in flagged if r.get("status") == "active"]
    print(f"bank                      : {len(rows)} questions")
    print(f"passages available        : {len(known)}")
    print(f"depend on missing text    : {len(flagged)}")
    print(f"  ...and are ACTIVE       : {len(active)}   <-- served to students now")
    if flagged:
        print("\nreasons:", dict(Counter(w for _, w in flagged).most_common()))
        print("by subject:", dict(Counter(r['subject'] for r, _ in flagged).most_common()))
        print("by year   :", dict(Counter(r.get('year', '') for r, _ in flagged).most_common(8)))
        print("\nexamples:")
        for r, _w in flagged[:3]:
            print(f"  [{r[idcol]}] {r['question_text'][:100]}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to set these to draft.")
        return 0
    if not active:
        print("nothing active to quarantine")
        return 0

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields + ["orphan_reason"])
        w.writeheader()
        for r, why in flagged:
            w.writerow({**r, "orphan_reason": why})

    ids = {r[idcol] for r, _ in active}
    for r in rows:
        if r[idcol] in ids:
            r["status"] = "draft"

    backup = bank_path.with_suffix(".csv.bak")
    shutil.copy2(bank_path, backup)
    with open(bank_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"quarantined {len(ids)} questions (status -> draft)")
    print(f"report  -> {out}")
    print(f"backup  -> {backup}")
    print("\nThey are not deleted. Import the passages, set passage_id, flip")
    print("status back to active, and they return.")
    print("Run the sync-questions Action to apply this to production.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
