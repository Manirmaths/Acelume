"""Validate and stage answer keys from the solved JAMB text archive.

The solved archive is useful evidence, but it is not trusted implicitly.  This
tool first supports measuring it against the hand-keyed batch outputs already
in ``data/staging/batches``.  Staging uses an exact fingerprint of the cleaned
question stem and all four options, then maps the answer by option text.  Rows
that do not match exactly, have conflicting source records, or name an answer
that is not one of the row's options are written to a review CSV instead of
being guessed.

Examples:

    python tools/import_solved_jamb_archive.py --zip solved.zip --validate
    python tools/import_solved_jamb_archive.py --zip solved.zip \
        --batch key-1991-Biology --prepare-sources --apply
    python tools/import_solved_jamb_archive.py --zip solved.zip \
        --batch key-1991-Biology --consensus --apply

This tool only writes per-batch staging files.  It never edits
``data/questions.csv`` or the batch manifest; merging remains a separate,
sequential decision through ``tools/merge_keyed_questions.py``.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import pathlib
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass

from clean_jamb_archive import clean_text, norm_key


REPO = pathlib.Path(__file__).resolve().parents[1]
STAGING = REPO / "data" / "staging"
BATCH_DIR = STAGING / "batches"
MANIFEST = STAGING / "batch_manifest.json"

Q_START = re.compile(r"^(\d+)\.\s*(.*)$")
OPTION = re.compile(r"^([A-E])\.\s*(.*)$")
ANSWER = re.compile(r"^Correct answer:\s*([A-E])\.?(?:\s+(.*))?$", re.I)
PATH_META = re.compile(
    r"/yearly/([^/]+)/jamb_[^/]+_(\d{4})_answers_and_explanations\.txt$",
    re.I,
)

KEYED_FIELDS = [
    "question_id", "exam_type", "subject", "topic", "subtopic", "difficulty",
    "year", "passage_id", "question_text", "image_url", "option_a", "option_b",
    "option_c", "option_d", "correct_option", "explanation", "tags", "source",
    "status",
]
REVIEW_FIELDS = KEYED_FIELDS


@dataclass(frozen=True)
class SolvedQuestion:
    source_path: str
    number: int
    year: str
    stem: str
    options: dict[str, str]
    answer_letter: str
    answer_text: str
    explanation: str


def read_csv(path: pathlib.Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(
    path: pathlib.Path, fields: list[str], rows: list[dict[str, str]], *, apply: bool
) -> None:
    if not apply:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fingerprint(stem: str, options: dict[str, str]) -> str:
    cleaned_stem = clean_text(stem).replace("[Figure required]", "").strip()
    return "##".join(
        [match_key(cleaned_stem)]
        + [match_key(clean_text(options.get(letter, ""))) for letter in "ABCD"]
    )


def match_key(value: str) -> str:
    """Normalize presentation-only differences when matching solved sources."""
    value = norm_key(value)
    value = re.sub(r"\btimes\b", "x", value)
    value = re.sub(r"\bfrac1001\b", "100", value)
    return value


def row_options(row: dict[str, str]) -> dict[str, str]:
    return {letter: row.get(f"option_{letter.lower()}", "") for letter in "ABCD"}


def parse_solved_text(source_path: str, text: str) -> list[SolvedQuestion]:
    """Parse one yearly solved-text file into structured records."""
    meta = PATH_META.search("/" + source_path.replace("\\", "/").lstrip("/"))
    year = meta.group(2) if meta else ""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    records: list[SolvedQuestion] = []

    number = 0
    stem_lines: list[str] = []
    options: dict[str, str] = {}
    active_option = ""
    answer_letter = ""
    answer_text = ""
    explanation_lines: list[str] = []
    state = "preamble"

    def finish() -> None:
        nonlocal number, stem_lines, options, active_option
        nonlocal answer_letter, answer_text, explanation_lines, state
        if number and stem_lines and answer_letter:
            records.append(SolvedQuestion(
                source_path=source_path,
                number=number,
                year=year,
                stem=clean_text(" ".join(stem_lines)),
                options={key: clean_text(value) for key, value in options.items()},
                answer_letter=answer_letter.upper(),
                answer_text=clean_text(answer_text),
                explanation=clean_explanation(" ".join(explanation_lines)),
            ))
        number = 0
        stem_lines = []
        options = {}
        active_option = ""
        answer_letter = ""
        answer_text = ""
        explanation_lines = []
        state = "preamble"

    for raw in lines:
        line = raw.strip()
        question = Q_START.match(line)
        option = OPTION.match(line)
        answer = ANSWER.match(line)

        if question and not option:
            finish()
            number = int(question.group(1))
            stem_lines = [question.group(2)] if question.group(2) else []
            state = "stem"
            continue
        if not number:
            continue
        if option and not answer:
            active_option = option.group(1).upper()
            options[active_option] = option.group(2)
            state = "options"
            continue
        if answer:
            answer_letter = answer.group(1).upper()
            answer_text = answer.group(2) or ""
            active_option = ""
            state = "answer"
            continue
        if line == "Explanation:":
            state = "explanation"
            continue
        if not line:
            continue
        if state == "stem":
            stem_lines.append(line)
        elif state == "options" and active_option:
            options[active_option] = (options[active_option] + " " + line).strip()
        elif state == "explanation":
            explanation_lines.append(line)

    finish()
    return records


def clean_explanation(value: str) -> str:
    # Unlike the raw question scrape, solved explanations contain deliberate
    # LaTeX commands.  Do not use clean_jamb_archive.clean_text here because it
    # removes backslashes by design.
    value = html.unescape(value)
    value = value.replace("''", "'").replace("â€™", "'")
    value = value.replace("ï¿½", "")
    value = re.sub(r"\bN\s?(?=\d)", "â‚¦", value)
    value = re.sub(r"\s+", " ", value).strip()
    # MathText intentionally does not treat dollar signs as delimiters because
    # real question content uses dollars as currency.  The solved archive uses
    # paired dollars only for formulas, so convert those pairs at import time.
    value = re.sub(r"\$([^$\n]+)\$", r"\\(\1\\)", value)
    value = value.replace(r"\,", r"\;")
    return value


def load_archive(path: pathlib.Path) -> list[SolvedQuestion]:
    records: list[SolvedQuestion] = []
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.lower().endswith("_answers_and_explanations.txt"):
                continue
            text = archive.read(name).decode("utf-8", errors="replace")
            if "SOURCE DATA ERROR" in text:
                continue
            records.extend(parse_solved_text(name, text))
    return records


def archive_index(
    records: list[SolvedQuestion],
) -> tuple[dict[str, SolvedQuestion], set[str]]:
    grouped: dict[str, list[SolvedQuestion]] = defaultdict(list)
    for record in records:
        if all(record.options.get(letter) for letter in "ABCD"):
            grouped[fingerprint(record.stem, record.options)].append(record)

    unique: dict[str, SolvedQuestion] = {}
    conflicts: set[str] = set()
    for key, matches in grouped.items():
        answers = {
            (match.answer_letter, match_key(match.answer_text)) for match in matches
        }
        if len(answers) == 1:
            unique[key] = matches[0]
        else:
            conflicts.add(key)
    return unique, conflicts


def resolve_answer(row: dict[str, str], solved: SolvedQuestion) -> tuple[str, str]:
    options = row_options(row)
    target = match_key(solved.answer_text)
    by_text = [letter for letter, value in options.items() if match_key(value) == target]
    if target and len(by_text) == 1:
        return by_text[0], ""

    letter = solved.answer_letter
    if letter in options and all(
        match_key(options[key]) == match_key(solved.options.get(key, "")) for key in "ABCD"
    ):
        return letter, ""
    if not target:
        return "", "solved record has no answer text and option order did not match"
    if len(by_text) > 1:
        return "", "solved answer text matches more than one option"
    return "", "solved answer text does not match any option"


def stage_rows(
    rows: list[dict[str, str]], index: dict[str, SolvedQuestion], conflicts: set[str]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    keyed: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    for row in rows:
        key = fingerprint(row.get("question_text", ""), row_options(row))
        reason = ""
        solved = index.get(key)
        if key in conflicts:
            reason = "conflicting answers in solved archive"
        elif solved is None:
            reason = "no exact stem-and-options match in solved archive"
        else:
            letter, reason = resolve_answer(row, solved)
            if not reason and not solved.explanation:
                reason = "solved record has no explanation"
            if not reason:
                keyed_row = {field: row.get(field, "") for field in KEYED_FIELDS}
                keyed_row["correct_option"] = letter
                keyed_row["explanation"] = solved.explanation
                keyed.append(keyed_row)
        if reason:
            review_row = {field: row.get(field, "") for field in REVIEW_FIELDS}
            review_row["correct_option"] = ""
            review_row["explanation"] = reason
            review_row["tags"] = (review_row["tags"] + "|review").strip("|")
            review.append(review_row)
    return keyed, review


def consensus_rows(
    rows: list[dict[str, str]],
    agent_rows: list[dict[str, str]],
    index: dict[str, SolvedQuestion],
    conflicts: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Accept only exact agreement between an independent solve and archive."""
    agent_by_id: dict[str, dict[str, str]] = {}
    for agent in agent_rows:
        qid = agent.get("question_id", "")
        if not qid or qid in agent_by_id:
            raise SystemExit(f"agent file has a missing or duplicate question_id: {qid!r}")
        letter = agent.get("correct_option", "").upper()
        if letter not in ("", "A", "B", "C", "D"):
            raise SystemExit(f"{qid}: invalid agent correct_option {letter!r}")
        if not (agent.get("explanation") or "").strip():
            raise SystemExit(f"{qid}: agent explanation is blank")
        agent["correct_option"] = letter
        agent_by_id[qid] = agent

    source_ids = [row.get("question_id", "") for row in rows]
    if set(agent_by_id) != set(source_ids):
        missing = sorted(set(source_ids) - set(agent_by_id))
        extra = sorted(set(agent_by_id) - set(source_ids))
        raise SystemExit(
            f"agent/source ID mismatch: missing={missing[:8]} extra={extra[:8]}"
        )

    keyed: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    for row in rows:
        qid = row["question_id"]
        agent = agent_by_id[qid]
        agent_letter = agent["correct_option"]
        key = fingerprint(row.get("question_text", ""), row_options(row))
        solved = index.get(key)
        archive_letter = ""
        reason = ""
        if key in conflicts:
            reason = "conflicting answers in solved archive"
        elif solved is None:
            reason = "no exact stem-and-options match in solved archive"
        else:
            archive_letter, reason = resolve_answer(row, solved)

        if not agent_letter:
            reason = "independent pass held for review: " + agent["explanation"].strip()
        elif not reason and agent_letter != archive_letter:
            reason = (
                f"independent pass chose {agent_letter}; solved archive chose "
                f"{archive_letter}; independent reasoning: {agent['explanation'].strip()}"
            )

        out = {field: row.get(field, "") for field in KEYED_FIELDS}
        out["status"] = "draft"
        if not reason:
            out["correct_option"] = agent_letter
            out["explanation"] = agent["explanation"].strip()
            out["tags"] = out["tags"].replace("needs-key", "consensus-keyed")
            keyed.append(out)
        else:
            out["correct_option"] = ""
            out["explanation"] = reason
            out["tags"] = (out["tags"] + "|review").strip("|")
            review.append(out)
    return keyed, review


def second_gate(
    keyed: list[dict[str, str]],
    second_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Require a separate elimination pass to agree with first-pass consensus."""
    by_id: dict[str, str] = {}
    for row in second_rows:
        qid = row.get("question_id", "")
        if not qid or qid in by_id:
            raise SystemExit(f"second-pass file has a missing or duplicate ID: {qid!r}")
        letter = row.get("correct_option", "").upper()
        if letter not in ("", "A", "B", "C", "D"):
            raise SystemExit(f"{qid}: invalid second-pass correct_option {letter!r}")
        by_id[qid] = letter

    expected = {row["question_id"] for row in keyed}
    if set(by_id) != expected:
        missing = sorted(expected - set(by_id))
        extra = sorted(set(by_id) - expected)
        raise SystemExit(
            f"second-pass/source ID mismatch: missing={missing[:8]} extra={extra[:8]}"
        )

    accepted: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    for row in keyed:
        first = row["correct_option"]
        second = by_id[row["question_id"]]
        if second == first:
            accepted.append(row)
            continue
        held = dict(row)
        held["correct_option"] = ""
        held["explanation"] = (
            f"direct solve and solved archive chose {first}; independent "
            f"elimination pass chose {second or 'no answer'}"
        )
        held["tags"] = held["tags"].replace("consensus-keyed", "needs-key")
        held["tags"] = (held["tags"] + "|review").strip("|")
        review.append(held)
    return accepted, review


def validate_existing(
    index: dict[str, SolvedQuestion], conflicts: set[str]
) -> int:
    totals = Counter()
    by_subject: dict[str, Counter] = defaultdict(Counter)
    mismatches: list[tuple[str, str, str, str]] = []
    for path in sorted(BATCH_DIR.glob("key-*_keyed.csv")):
        _, rows = read_csv(path)
        for row in rows:
            totals["hand_keyed"] += 1
            subject = row.get("subject", "")
            key = fingerprint(row.get("question_text", ""), row_options(row))
            if key in conflicts:
                totals["archive_conflict"] += 1
                by_subject[subject]["archive_conflict"] += 1
                continue
            solved = index.get(key)
            if solved is None:
                totals["unmatched"] += 1
                by_subject[subject]["unmatched"] += 1
                continue
            letter, reason = resolve_answer(row, solved)
            if reason:
                totals["unresolved"] += 1
                by_subject[subject]["unresolved"] += 1
                continue
            totals["matched"] += 1
            by_subject[subject]["matched"] += 1
            if letter == row.get("correct_option", "").upper():
                totals["agreed"] += 1
                by_subject[subject]["agreed"] += 1
            else:
                totals["disagreed"] += 1
                by_subject[subject]["disagreed"] += 1
                mismatches.append((
                    row.get("question_id", ""), row.get("correct_option", ""),
                    letter, row.get("question_text", ""),
                ))

    print("validation against existing hand-keyed outputs")
    print(f"  hand-keyed rows : {totals['hand_keyed']:,}")
    print(f"  archive matched : {totals['matched']:,}")
    print(f"  archive unmatched: {totals['unmatched']:,}")
    print(f"  source conflicts: {totals['archive_conflict']:,}")
    print(f"  answer agreed   : {totals['agreed']:,}")
    print(f"  answer disagreed: {totals['disagreed']:,}")
    if totals["matched"]:
        print(f"  agreement rate  : {100 * totals['agreed'] / totals['matched']:.2f}%")
    print("\nby subject (agreed/matched):")
    for subject in sorted(by_subject):
        counts = by_subject[subject]
        rate = 100 * counts["agreed"] / max(1, counts["matched"])
        print(f"  {subject:12s} {counts['agreed']:4d}/{counts['matched']:4d}  {rate:6.2f}%"
              f"  unmatched={counts['unmatched']}")
    if mismatches:
        print("\nfirst 30 disagreements:")
        for qid, manual, solved, stem in mismatches[:30]:
            print(f"  {qid}: hand={manual} archive={solved}  {stem[:100]}")
    return 1 if totals["disagreed"] else 0


def validate_truth(
    truth_path: pathlib.Path,
    index: dict[str, SolvedQuestion],
    conflicts: set[str],
) -> int:
    _, rows = read_csv(truth_path)
    counts = Counter()
    disagreements: list[tuple[str, str, str, str]] = []
    for row in rows:
        key = fingerprint(row.get("question_text", ""), row_options(row))
        if key in conflicts:
            counts["conflict"] += 1
            continue
        solved = index.get(key)
        if solved is None:
            counts["unmatched"] += 1
            continue
        letter, reason = resolve_answer(row, solved)
        if reason:
            counts["unresolved"] += 1
            continue
        counts["matched"] += 1
        if letter == row.get("correct_option", "").upper():
            counts["agreed"] += 1
        else:
            counts["disagreed"] += 1
            disagreements.append((
                row.get("question_id", ""), row.get("correct_option", ""),
                letter, row.get("question_text", ""),
            ))

    print(f"validation against trusted keys: {truth_path}")
    print(f"  truth rows      : {len(rows):,}")
    print(f"  archive matched : {counts['matched']:,}")
    print(f"  archive unmatched: {counts['unmatched']:,}")
    print(f"  answer agreed   : {counts['agreed']:,}")
    print(f"  answer disagreed: {counts['disagreed']:,}")
    if counts["matched"]:
        print(f"  accuracy        : {100 * counts['agreed'] / counts['matched']:.2f}%")
    if disagreements:
        print("\ndisagreements:")
        for qid, truth, solved, stem in disagreements:
            print(f"  {qid}: truth={truth} archive={solved}  {stem[:100]}")
    return 1 if counts["disagreed"] else 0


def selected_batches(*, batch_id: str, pending: bool, limit: int) -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["batches"]
    if batch_id:
        wanted = [value.strip() for value in batch_id.split(",") if value.strip()]
        by_id = {item["id"]: item for item in manifest}
        missing = [value for value in wanted if value not in by_id]
        if missing:
            raise SystemExit(f"no such batch: {', '.join(missing)}")
        matches = [by_id[value] for value in wanted]
        return matches
    if not pending:
        return []
    matches = [
        item for item in manifest
        if item["kind"] == "key" and item["status"] == "pending"
    ]
    if not limit:
        return matches
    selected: list[dict] = []
    questions = 0
    for item in matches:
        if selected and questions >= limit:
            break
        selected.append(item)
        questions += item["count"]
    return selected


def prepare_sources(batches: list[dict], *, apply: bool) -> None:
    fields, archive_rows = read_csv(STAGING / "jamb_archive_unkeyed.csv")
    by_id = {row["question_id"]: row for row in archive_rows}
    for batch in batches:
        path = BATCH_DIR / f"{batch['id']}.csv"
        rows = [by_id[qid] for qid in batch["question_ids"] if qid in by_id]
        if len(rows) != batch["count"]:
            raise SystemExit(
                f"{batch['id']}: manifest has {batch['count']} ids but only "
                f"{len(rows)} exist in jamb_archive_unkeyed.csv"
            )
        if path.exists():
            _, existing = read_csv(path)
            if [row["question_id"] for row in existing] != batch["question_ids"]:
                raise SystemExit(f"{path} exists but does not match the manifest")
            print(f"exists {path} ({len(existing)} rows)")
            continue
        write_csv(path, fields, rows, apply=apply)
        print(f"{'wrote' if apply else 'would write'} {path} ({len(rows)} rows)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=pathlib.Path)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--truth", type=pathlib.Path,
                        help="score exact archive matches against a trusted keyed CSV")
    parser.add_argument("--batch", default="")
    parser.add_argument("--pending", action="store_true")
    parser.add_argument("--prepare-sources", action="store_true",
                        help="materialize selected manifest batches without keying them")
    parser.add_argument("--consensus", action="store_true",
                        help="gate <batch>_agent.csv answers against the solved archive")
    parser.add_argument("--prepare-second-pass", action="store_true",
                        help="write blank-key candidates that passed --consensus")
    parser.add_argument("--second-consensus", action="store_true",
                        help="also require <batch>_second_agent.csv to agree")
    parser.add_argument("--limit", type=int, default=0,
                        help="with --pending, stage at least this many source rows")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    records = load_archive(args.zip)
    index, conflicts = archive_index(records)
    print(f"solved records : {len(records):,}")
    print(f"unique exact matches: {len(index):,}")
    print(f"conflicting fingerprints: {len(conflicts):,}\n")

    if args.validate:
        return validate_existing(index, conflicts)
    if args.truth:
        return validate_truth(args.truth, index, conflicts)

    batches = selected_batches(batch_id=args.batch, pending=args.pending, limit=args.limit)
    if not batches:
        raise SystemExit("select --validate, --truth CSV, --batch ID, or --pending")
    if args.prepare_sources:
        prepare_sources(batches, apply=args.apply)
        return 0
    if not args.consensus:
        raise SystemExit(
            "refusing archive-only keying: the solved archive scored 84.0% on "
            "trusted keys. Supply independent <batch>_agent.csv answers and "
            "use --consensus."
        )

    total_keyed = total_review = 0
    for batch in batches:
        source = BATCH_DIR / f"{batch['id']}.csv"
        if not source.exists():
            raise SystemExit(
                f"missing {source}; stage it first with tools/batch_queue.py --batch {batch['id']} --run"
            )
        _, rows = read_csv(source)
        agent_path = BATCH_DIR / f"{batch['id']}_agent.csv"
        if not agent_path.exists():
            raise SystemExit(f"missing independent answer file: {agent_path}")
        _, agent_rows = read_csv(agent_path)
        keyed, review = consensus_rows(rows, agent_rows, index, conflicts)
        if args.prepare_second_pass:
            candidate_ids = {row["question_id"] for row in keyed}
            candidates = [row for row in rows if row["question_id"] in candidate_ids]
            second_path = BATCH_DIR / f"{batch['id']}_second.csv"
            write_csv(second_path, KEYED_FIELDS, candidates, apply=args.apply)
        if args.second_consensus:
            second_path = BATCH_DIR / f"{batch['id']}_second_agent.csv"
            if not second_path.exists():
                raise SystemExit(f"missing second-pass answer file: {second_path}")
            _, second_rows = read_csv(second_path)
            keyed, second_review = second_gate(keyed, second_rows)
            review.extend(second_review)
        keyed_path = BATCH_DIR / f"{batch['id']}_keyed.csv"
        review_path = BATCH_DIR / f"{batch['id']}_needs_review.csv"
        write_csv(keyed_path, KEYED_FIELDS, keyed, apply=args.apply)
        write_csv(review_path, REVIEW_FIELDS, review, apply=args.apply)
        total_keyed += len(keyed)
        total_review += len(review)
        print(f"{batch['id']:34s} keyed={len(keyed):4d} review={len(review):3d}"
              f" source={len(rows):4d}")

    verb = "wrote" if args.apply else "would write"
    print(f"\n{verb} {total_keyed:,} keyed rows and {total_review:,} review rows")
    if not args.apply:
        print("Dry run. Re-run with --apply to write staging CSVs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
