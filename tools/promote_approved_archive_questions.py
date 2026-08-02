"""Promote only fully gated JAMB archive drafts to active status.

Eligible rows carry ``consensus-keyed`` (the measured three-way gate) or
``adjudicated-keyed`` (an explicit review decision).  Hand-keyed and unresolved
archive rows are intentionally out of scope.  The tool rechecks keys, selected
options, explanations, topics, and passage references before changing status.
It is a dry run unless ``--apply`` is supplied.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
import shutil
import sys
from collections import Counter


csv.field_size_limit(10**7)
REPO = pathlib.Path(__file__).resolve().parents[1]
BANK = REPO / "data" / "questions.csv"
PASSAGES = REPO / "data" / "passages.csv"
ELIGIBLE_TAGS = {"consensus-keyed", "adjudicated-keyed"}
PASSAGE_TOPICS = {"Reading Comprehension", "Cloze Test"}
PASSAGE_LANGUAGE = re.compile(
    r"\b(?:according to|from|in) (?:the|this) passage\b|"
    r"\bthe (?:passage|writer|author) (?:states|says|implies|suggests|argues|"
    r"believes|emphasizes|describes|refers|means|concludes)\b|"
    r"\b(?:best|suitable) title for (?:the|this) passage\b",
    re.IGNORECASE,
)


def load(path: pathlib.Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def known_passages(path: pathlib.Path) -> set[str]:
    if not path.exists():
        return set()
    _, rows = load(path)
    return {
        row.get("passage_id", "").strip()
        for row in rows
        if row.get("passage_id", "").strip()
    }


def eligible(row: dict[str, str]) -> bool:
    tags = {tag.strip() for tag in row.get("tags", "").split("|") if tag.strip()}
    return (
        row.get("status", "").strip() == "draft"
        and row.get("source", "").strip() == "past-question"
        and bool(tags & ELIGIBLE_TAGS)
    )


def blocked_reason(row: dict[str, str], passages: set[str]) -> str:
    letter = row.get("correct_option", "").strip().upper()
    if letter not in {"A", "B", "C", "D"}:
        return "invalid or missing answer key"
    if not row.get(f"option_{letter.lower()}", "").strip():
        return "selected option is blank"
    if not row.get("explanation", "").strip():
        return "explanation is blank"
    if not row.get("topic", "").strip():
        return "topic is blank"

    passage_id = row.get("passage_id", "").strip()
    if passage_id and passage_id not in passages:
        return f"unknown passage_id {passage_id}"
    if row.get("topic", "").strip() in PASSAGE_TOPICS and not passage_id:
        return "passage-dependent topic has no passage_id"
    if (
        row.get("subject", "").strip() == "English"
        and not passage_id
        and PASSAGE_LANGUAGE.search(row.get("question_text", ""))
    ):
        return "question wording references a missing passage"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--bank", type=pathlib.Path, default=BANK)
    parser.add_argument("--passages", type=pathlib.Path, default=PASSAGES)
    parser.add_argument(
        "--exclude-id", action="append", default=[],
        help="keep this otherwise eligible question as draft; may be repeated",
    )
    args = parser.parse_args()

    fields, rows = load(args.bank)
    passage_ids = known_passages(args.passages)
    excluded = set(args.exclude_id)
    candidates = [row for row in rows if eligible(row)]
    promote: list[dict[str, str]] = []
    blocked: list[tuple[dict[str, str], str]] = []
    for row in candidates:
        qid = row.get("question_id", "")
        reason = "explicitly excluded after spot-check" if qid in excluded else blocked_reason(row, passage_ids)
        if reason:
            blocked.append((row, reason))
        else:
            promote.append(row)

    print(f"eligible drafts : {len(candidates):,}")
    print(f"will promote    : {len(promote):,}")
    print(f"will keep draft : {len(blocked):,}")
    if blocked:
        print("blocked reasons:")
        for reason, count in Counter(reason for _, reason in blocked).most_common():
            print(f"  {count:5d}  {reason}")
        print("blocked IDs:")
        for row, reason in blocked[:30]:
            print(f"  {row.get('question_id', '')}: {reason}")
    if not args.apply:
        print("\nDry run. Re-run with --apply to promote approved rows.")
        return 0
    if not promote:
        print("nothing to do")
        return 0

    promote_ids = {row["question_id"] for row in promote}
    for row in rows:
        if row.get("question_id", "") in promote_ids:
            row["status"] = "active"

    temp = args.bank.with_suffix(".csv.promote.tmp")
    backup = args.bank.with_suffix(".csv.promote.bak")
    with temp.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    shutil.copy2(args.bank, backup)
    temp.replace(args.bank)
    print(f"backup -> {backup}")
    print(f"wrote  -> {args.bank}")
    print(f"promoted {len(promote):,} approved archive questions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
