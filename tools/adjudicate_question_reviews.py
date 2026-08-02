"""Apply a human/agent adjudication file to full-schema review questions.

Decisions are deliberately separate from the review rows.  The tool requires an
explicit decision for every input ID, keeps held questions unkeyed, and refuses
to approve questions that the earlier review identified as missing their
passage.  Approved rows remain drafts until a later bulk-promotion step.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys


csv.field_size_limit(10**7)
DECISION_FIELDS = {"question_id", "decision", "correct_option", "explanation"}
MISSING_CONTEXT = re.compile(
    r"passage.{0,45}(?:missing|absent|omitted|not included|not present|not supplied|"
    r"unavailable)|(?:missing|absent|omitted).{0,30}passage|"
    r"depends on (?:an? )?(?:omitted )?passage|no surrounding passage",
    re.IGNORECASE,
)


def read_csv(path: pathlib.Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def missing_context(row: dict[str, str]) -> bool:
    return bool(MISSING_CONTEXT.search(row.get("explanation", "")))


def clean_tags(value: str, *, approved: bool) -> str:
    tags = [tag.strip() for tag in value.split("|") if tag.strip()]
    remove = {"review"}
    if approved:
        remove |= {"needs-key", "consensus-keyed"}
    tags = [tag for tag in tags if tag not in remove]
    wanted = "adjudicated-keyed" if approved else "reviewed-hold"
    if wanted not in tags:
        tags.append(wanted)
    return "|".join(tags)


def apply_decisions(
    reviews: list[dict[str, str]], decisions: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    review_ids = [row.get("question_id", "") for row in reviews]
    if not all(review_ids) or len(set(review_ids)) != len(review_ids):
        raise SystemExit("review inputs contain a missing or duplicate question_id")

    by_id: dict[str, dict[str, str]] = {}
    for decision in decisions:
        qid = decision.get("question_id", "").strip()
        if not qid or qid in by_id:
            raise SystemExit(f"decision file has a missing or duplicate question_id: {qid!r}")
        action = decision.get("decision", "").strip().lower()
        letter = decision.get("correct_option", "").strip().upper()
        explanation = decision.get("explanation", "").strip()
        if action not in {"approve", "hold"}:
            raise SystemExit(f"{qid}: decision must be approve or hold")
        if action == "approve" and letter not in {"A", "B", "C", "D"}:
            raise SystemExit(f"{qid}: approved decision needs an A-D key")
        if action == "hold" and letter:
            raise SystemExit(f"{qid}: held decision must have a blank key")
        if not explanation:
            raise SystemExit(f"{qid}: adjudication explanation is blank")
        decision["decision"] = action
        decision["correct_option"] = letter
        decision["explanation"] = explanation
        by_id[qid] = decision

    if set(by_id) != set(review_ids):
        missing = sorted(set(review_ids) - set(by_id))
        extra = sorted(set(by_id) - set(review_ids))
        raise SystemExit(f"decision/review ID mismatch: missing={missing[:8]} extra={extra[:8]}")

    approved: list[dict[str, str]] = []
    held: list[dict[str, str]] = []
    for source in reviews:
        row = dict(source)
        decision = by_id[row["question_id"]]
        if decision["decision"] == "approve":
            if missing_context(source):
                raise SystemExit(
                    f"{row['question_id']}: cannot approve a question whose source passage is missing"
                )
            answer_field = f"option_{decision['correct_option'].lower()}"
            if not row.get(answer_field, "").strip():
                raise SystemExit(
                    f"{row['question_id']}: selected option {decision['correct_option']} is blank"
                )
            row["correct_option"] = decision["correct_option"]
            row["explanation"] = decision["explanation"]
            row["tags"] = clean_tags(row.get("tags", ""), approved=True)
            row["status"] = "draft"
            approved.append(row)
        else:
            row["correct_option"] = ""
            row["explanation"] = (
                f"{source.get('explanation', '').strip()} | adjudication hold: "
                f"{decision['explanation']}"
            ).strip(" |")
            row["tags"] = clean_tags(row.get("tags", ""), approved=False)
            row["status"] = "draft"
            held.append(row)
    return approved, held


def write_csv(
    path: pathlib.Path, fields: list[str], rows: list[dict[str, str]], *, apply: bool
) -> None:
    if not apply:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", action="append", required=True, type=pathlib.Path)
    parser.add_argument("--decisions", required=True, type=pathlib.Path)
    parser.add_argument("--keyed-out", required=True, type=pathlib.Path)
    parser.add_argument("--held-out", required=True, type=pathlib.Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    fields: list[str] = []
    reviews: list[dict[str, str]] = []
    for path in args.review:
        current_fields, current_rows = read_csv(path)
        if not fields:
            fields = current_fields
        elif current_fields != fields:
            raise SystemExit(f"review schema mismatch: {path}")
        reviews.extend(current_rows)
    decision_fields, decisions = read_csv(args.decisions)
    if not DECISION_FIELDS.issubset(decision_fields):
        missing = sorted(DECISION_FIELDS - set(decision_fields))
        raise SystemExit("decision file is missing columns: " + ", ".join(missing))

    approved, held = apply_decisions(reviews, decisions)
    print(f"reviewed : {len(reviews):,}")
    print(f"approved : {len(approved):,}")
    print(f"held     : {len(held):,}")
    write_csv(args.keyed_out, fields, approved, apply=args.apply)
    write_csv(args.held_out, fields, held, apply=args.apply)
    if args.apply:
        print(f"wrote -> {args.keyed_out}")
        print(f"wrote -> {args.held_out}")
    else:
        print("Dry run. Re-run with --apply to write outputs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
