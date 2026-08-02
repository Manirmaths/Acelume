"""
Work through the question bank one subject-year at a time.

Doing 17,000 questions in a single run is a bad idea for reasons that have
nothing to do with cost: you cannot inspect the result, a bad prompt or a weak
model poisons everything before you notice, and there is no natural point to
stop and look. Batching by subject and year gives roughly 45 questions per unit
-- small enough to actually read, large enough to be worth a run.

Two kinds of batch, because the bank has two different problems:

    key    archive questions with NO answer key   -> tools/answer_keys.py
    audit  live questions whose key was never checked -> tools/audit_keys.py

Order is newest-first, since recent papers matter most to a student sitting
JAMB next. Undated questions (the decade-spanning aggregate files) come last.

    python tools/batch_queue.py --build          # create the manifest
    python tools/batch_queue.py --status         # what is done, what is next
    python tools/batch_queue.py --next           # show the next batch
    python tools/batch_queue.py --next --run     # ...and run it
    python tools/batch_queue.py --batch audit-2025-Mathematics --run

Each batch writes its own CSV and its own checkpoint. Nothing is merged into
data/questions.csv until you run tools/merge_keyed_questions.py, and nothing
reaches students until you sync and publish.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import subprocess
import sys
from collections import Counter, defaultdict

csv.field_size_limit(10 ** 7)
REPO = pathlib.Path(__file__).resolve().parents[1]
STAGING = REPO / "data" / "staging"
BATCH_DIR = STAGING / "batches"
MANIFEST = STAGING / "batch_manifest.json"

# Canonical order from app/subjects.py, so a year is worked through in the same
# order the app lists subjects.
SUBJECT_ORDER = [
    "Mathematics", "English", "Physics", "Chemistry", "Biology", "Geography",
    "Economics", "Literature", "Government", "Commerce", "Accounting",
]
# A batch bigger than this is split. ~45 is the median; 250 is about the most
# anyone will actually review in one sitting.
MAX_BATCH = 250


def load_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as fh:
        rows = [dict(r) for r in csv.DictReader(fh)]
    for r in rows:
        if "question_id" not in r:
            r["question_id"] = r.get("﻿question_id", "")
    return rows


def sort_key(kind: str, year: str, subject: str):
    """Newest year first; undated last; canonical subject order within a year."""
    undated = 0 if year.isdigit() else 1
    y = -int(year) if year.isdigit() else 0
    s = SUBJECT_ORDER.index(subject) if subject in SUBJECT_ORDER else 99
    return (undated, y, s, kind)


def build() -> int:
    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)

    for r in load_csv(REPO / "data" / "questions.csv"):
        # Drafts are not served to anyone, so auditing them measures nothing.
        # Diagram-backed questions are excluded too: a text-only model cannot
        # see the image, so every one becomes a false disagreement.
        if (r.get("correct_option") in ("A", "B", "C", "D")
                and r.get("status") == "active"
                and not (r.get("image_url") or "").strip()):
            groups[("audit", r.get("year") or "undated", r["subject"])].append(r["question_id"])
    for r in load_csv(STAGING / "jamb_archive_unkeyed.csv"):
        groups[("key", r.get("year") or "undated", r["subject"])].append(r["question_id"])

    batches = []
    for (kind, year, subject), ids in groups.items():
        chunks = [ids[i:i + MAX_BATCH] for i in range(0, len(ids), MAX_BATCH)] or [[]]
        for n, chunk in enumerate(chunks, start=1):
            suffix = f"-{n}" if len(chunks) > 1 else ""
            batches.append({
                "id": f"{kind}-{year}-{subject}{suffix}",
                "kind": kind, "year": year, "subject": subject,
                "count": len(chunk), "question_ids": chunk,
                "status": "pending", "result": None,
            })
    batches.sort(key=lambda b: sort_key(b["kind"], b["year"], b["subject"]))

    # Preserve completed work if a manifest already exists.
    if MANIFEST.exists():
        old = {b["id"]: b for b in json.loads(MANIFEST.read_text(encoding="utf-8"))["batches"]}
        for b in batches:
            if b["id"] in old and old[b["id"]]["status"] != "pending":
                b["status"] = old[b["id"]]["status"]
                b["result"] = old[b["id"]]["result"]

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"batches": batches}, indent=1), encoding="utf-8")
    total = sum(b["count"] for b in batches)
    print(f"built {len(batches)} batches covering {total:,} questions")
    print(f"  key   : {sum(b['count'] for b in batches if b['kind']=='key'):,}")
    print(f"  audit : {sum(b['count'] for b in batches if b['kind']=='audit'):,}")
    print(f"\nfirst 12 in order:")
    for b in batches[:12]:
        print(f"    {b['id']:38s} {b['count']:5d}")
    print(f"\nmanifest -> {MANIFEST}")
    return 0


def read_manifest() -> list[dict]:
    if not MANIFEST.exists():
        raise SystemExit("No manifest. Run: python tools/batch_queue.py --build")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["batches"]


def save_manifest(batches: list[dict]) -> None:
    temp = MANIFEST.with_suffix(".json.tmp")
    temp.write_text(json.dumps({"batches": batches}, indent=1), encoding="utf-8")
    temp.replace(MANIFEST)


def status() -> int:
    batches = read_manifest()
    c = Counter(b["status"] for b in batches)
    done_q = sum(b["count"] for b in batches if b["status"] == "done")
    total_q = sum(b["count"] for b in batches)
    print(f"batches: {dict(c)}")
    print(f"questions: {done_q:,}/{total_q:,}  ({100*done_q/max(1,total_q):.1f}%)")
    nxt = next((b for b in batches if b["status"] == "pending"), None)
    print(f"next: {nxt['id']} ({nxt['count']} questions)" if nxt else "next: nothing pending")
    recent = [b for b in batches if b["status"] == "done"][-8:]
    if recent:
        print("\nrecently completed:")
        for b in recent:
            r = b.get("result") or {}
            print(f"    {b['id']:38s} {r}")
    return 0


def write_batch_csv(batch: dict) -> pathlib.Path:
    src = (REPO / "data" / "questions.csv") if batch["kind"] == "audit" \
        else (STAGING / "jamb_archive_unkeyed.csv")
    rows = load_csv(src)
    wanted = set(batch["question_ids"])
    subset = [r for r in rows if r["question_id"] in wanted]
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    out = BATCH_DIR / f"{batch['id']}.csv"
    with open(out, "w", encoding="utf-8", newline="") as fh:
        # Normalise away the BOM column name so downstream tools see a clean header.
        fields = [f.lstrip("﻿") for f in subset[0].keys()] if subset else ["question_id"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in subset:
            w.writerow({k.lstrip("﻿"): v for k, v in r.items()})
    return out


def run_batch(batch: dict, *, model: str, workers: int, apply: bool) -> int:
    path = write_batch_csv(batch)
    print(f"\n=== {batch['id']}  ({batch['count']} questions) ===")
    print(f"batch CSV: {path}")

    if batch["kind"] == "key":
        cmd = [sys.executable, str(REPO / "tools" / "answer_keys.py"),
               "--in", str(path),
               "--out", str(BATCH_DIR / f"{batch['id']}_keyed.csv"),
               "--review-out", str(BATCH_DIR / f"{batch['id']}_needs_review.csv"),
               "--model", model, "--workers", str(workers)]
    else:
        cmd = [sys.executable, str(REPO / "tools" / "audit_keys.py"),
               "--in", str(path), "--model", model, "--workers", str(workers),
               "--out", str(BATCH_DIR / f"{batch['id']}-disagreements.csv")]
    if apply:
        cmd.append("--apply")
    print("running:", " ".join(cmd), "\n")
    return subprocess.call(cmd)


def run_all(batches, *, kind, model, workers, apply, stop_after, run) -> int:
    """Work through every pending batch in queue order.

    Resumable by construction: a batch is marked done only after its tool exits
    cleanly with --apply, and each tool keeps its own per-question checkpoint.
    Interrupt this at any point -- rerunning picks up exactly where it stopped,
    re-answering nothing.

    It stops at the first failing batch rather than ploughing on. A batch fails
    for a reason, usually a bad API key or a rate limit, and continuing would
    burn through the remaining batches recording the same failure each time.
    """
    pending = [b for b in batches if b["status"] == "pending"
               and (not kind or b["kind"] == kind)]
    if stop_after:
        pending = pending[:stop_after]
    total_q = sum(b["count"] for b in pending)
    print(f"{len(pending)} pending batches, {total_q:,} questions")
    if not run:
        for b in pending[:20]:
            print(f"    {b['id']:34s} {b['count']:5d}")
        if len(pending) > 20:
            print(f"    ... and {len(pending) - 20} more")
        print("\nAdd --run --apply to work through them.")
        return 0

    for n, batch in enumerate(pending, start=1):
        print(f"\n########## {n}/{len(pending)}  {batch['id']} ##########")
        rc = run_batch(batch, model=model, workers=workers, apply=apply)
        if rc != 0:
            print(f"\n{batch['id']} failed (exit {rc}). Stopping so the failure "
                  f"is not repeated across every remaining batch.")
            print("Fix the cause and rerun this same command; finished batches are skipped.")
            return rc
        if apply:
            batch["status"] = "done"
            save_manifest(batches)
    print(f"\nfinished {len(pending)} batches")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--batch", default="")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--stage", action="store_true",
                    help="write the selected batch CSV without calling a model")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--mark-done", default="", help="mark a batch id complete")
    ap.add_argument(
        "--record-result", action="append", default=[], metavar="ID:KEYED:REVIEW:ORPHAN",
        help="atomically mark one or more batches done with reconciled counts",
    )
    ap.add_argument("--all", action="store_true",
                    help="work through every pending batch, not just the next one")
    ap.add_argument("--kind", default="", choices=["", "key", "audit"],
                    help="restrict --all to keying or auditing")
    ap.add_argument("--stop-after", type=int, default=0,
                    help="with --all, stop after this many batches")
    args = ap.parse_args()

    if args.build:
        return build()
    if args.status or not (
        args.next or args.batch or args.mark_done or args.record_result or args.all
    ):
        return status()

    batches = read_manifest()
    if args.record_result:
        by_id = {batch["id"]: batch for batch in batches}
        for spec in args.record_result:
            try:
                batch_id, keyed, review, orphan = spec.rsplit(":", 3)
                result = {
                    "keyed": int(keyed), "review": int(review), "orphan": int(orphan),
                }
            except ValueError as exc:
                raise SystemExit(
                    f"invalid --record-result {spec!r}; expected ID:KEYED:REVIEW:ORPHAN"
                ) from exc
            batch = by_id.get(batch_id)
            if batch is None:
                raise SystemExit(f"no such batch: {batch_id}")
            if any(value < 0 for value in result.values()):
                raise SystemExit(f"{batch_id}: result counts cannot be negative")
            if sum(result.values()) != batch["count"]:
                raise SystemExit(
                    f"{batch_id}: result counts sum to {sum(result.values())}, "
                    f"manifest count is {batch['count']}"
                )
            batch["status"] = "done"
            batch["result"] = result
            print(f"recorded {batch_id}: {result}")
        save_manifest(batches)
        return 0
    if args.mark_done:
        for b in batches:
            if b["id"] == args.mark_done:
                b["status"] = "done"
                save_manifest(batches)
                print(f"marked {b['id']} done")
                return 0
        raise SystemExit(f"no such batch: {args.mark_done}")

    if args.all:
        return run_all(batches, kind=args.kind, model=args.model,
                       workers=args.workers, apply=args.apply,
                       stop_after=args.stop_after, run=args.run)

    if args.batch:
        batch = next((b for b in batches if b["id"] == args.batch), None)
        if batch is None:
            raise SystemExit(f"no such batch: {args.batch}")
    else:
        batch = next((b for b in batches if b["status"] == "pending"), None)
        if batch is None:
            print("nothing pending")
            return 0

    print(f"batch      : {batch['id']}")
    print(f"kind       : {batch['kind']}  ({'needs keys' if batch['kind']=='key' else 'has keys, auditing'})")
    print(f"subject    : {batch['subject']}   year: {batch['year']}")
    print(f"questions  : {batch['count']}")
    if args.stage:
        path = write_batch_csv(batch)
        print(f"\nstaged -> {path}")
        return 0
    if not args.run:
        print("\nAdd --stage to write its CSV, or --run to execute it.")
        return 0

    rc = run_batch(batch, model=args.model, workers=args.workers, apply=args.apply)
    if rc == 0 and args.apply:
        batch["status"] = "done"
        save_manifest(batches)
        print(f"\nmarked {batch['id']} done")
    elif rc == 0:
        print("\nDry run finished. Re-run with --apply to record it as done.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
