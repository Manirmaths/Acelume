"""
Generate answer keys and explanations for unkeyed questions.

Publishes ONLY where two independent passes agree (see tools/keying_core.py for
why that is the whole design). Everything else is written out as a review queue
and left as a draft, because a question with no key teaches nothing, while a
question with a wrong key teaches something false.

Run the validation first. It scores this exact pipeline against questions whose
answers are already known, so you learn your real accuracy before spending
anything on a bulk run:

    python tools/answer_keys.py --validate data/staging/ground_truth.csv

Then a small batch, then the rest:

    python tools/answer_keys.py --in data/staging/jamb_archive_unkeyed.csv --limit 100
    python tools/answer_keys.py --in data/staging/jamb_archive_unkeyed.csv --apply

Runs are resumable: progress is appended to a .progress.jsonl beside the output,
and re-running skips anything already decided. Interrupt it freely.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from keying_core import PROMPT_VERSION, ModelError, api_key_from_env, decide  # noqa: E402

csv.field_size_limit(10 ** 7)
REPO = pathlib.Path(__file__).resolve().parents[1]


def progress_path_for(base: pathlib.Path, model: str) -> pathlib.Path:
    """Checkpoint path, namespaced by model.

    Resuming is keyed on question id, so a checkpoint written by one model would
    be silently reused by another -- you would switch to a stronger model, see
    "6,900 already decided", and ship the weaker model's answers believing they
    came from the new one. Putting the model in the filename makes that
    impossible rather than merely unlikely.
    """
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", model)
    return base.with_name(f"{base.name}.{safe}.{PROMPT_VERSION}.jsonl")


def load_progress(path: pathlib.Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["question_id"]] = rec
    return out


def run(rows, *, model, api_key, workers, progress_path, explain=True, suggest=False):
    done = load_progress(progress_path)
    todo = [r for r in rows if r["question_id"] not in done]
    print(f"{len(done)} already decided, {len(todo)} to do")

    if todo:
        with open(progress_path, "a", encoding="utf-8") as log, \
                ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(decide, r, model=model, api_key=api_key, explain=explain,
                            suggest_on_conflict=suggest): r
                for r in todo
            }
            for i, fut in enumerate(as_completed(futures), start=1):
                r = futures[fut]
                try:
                    v = fut.result()
                    rec = {"question_id": v.question_id, "accepted": v.accepted,
                           "letter": v.letter, "pass_a": v.pass_a, "pass_b": v.pass_b,
                           "reason": v.reason, "explanation": v.explanation,
                           "note": v.note, "suggestion": v.suggestion}
                except ModelError as e:
                    rec = {"question_id": r["question_id"], "accepted": False,
                           "letter": None, "pass_a": None, "pass_b": None,
                           "reason": "", "explanation": "", "note": f"model error: {e}"}
                log.write(json.dumps(rec, ensure_ascii=False) + "\n")
                log.flush()
                done[rec["question_id"]] = rec
                if i % 25 == 0 or i == len(todo):
                    ok = sum(1 for x in done.values() if x["accepted"])
                    print(f"  {i}/{len(todo)}  accepted so far {ok}/{len(done)}"
                          f" ({100*ok/max(1,len(done)):.1f}%)")
    return done


def validate(path, *, model, api_key, workers, limit):
    """Score the gated pipeline against questions with verified answers."""
    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    truth = {r["question_id"]: r["correct_option"] for r in rows}
    if limit:
        rows = rows[:limit]
    prog = progress_path_for(pathlib.Path(str(path) + ".validate"), model)
    done = run(rows, model=model, api_key=api_key, workers=workers,
               progress_path=prog, explain=False)

    dec = [done[r["question_id"]] for r in rows if r["question_id"] in done]
    acc = [d for d in dec if d["accepted"]]
    acc_right = [d for d in acc if d["letter"] == truth[d["question_id"]]]
    # How often pass A alone was right -- i.e. what you would ship with no gate.
    a_right = [d for d in dec if d.get("pass_a") == truth[d["question_id"]]]

    print("\n================ VALIDATION ================")
    print(f"questions scored          : {len(dec)}")
    print(f"ungated (single pass)     : {len(a_right)}/{len(dec)}"
          f"  = {100*len(a_right)/max(1,len(dec)):.1f}% correct")
    print(f"accepted by the gate      : {len(acc)}/{len(dec)}"
          f"  = {100*len(acc)/max(1,len(dec)):.1f}% coverage")
    print(f"  of those, CORRECT       : {len(acc_right)}/{len(acc)}"
          f"  = {100*len(acc_right)/max(1,len(acc)):.1f}%")
    held = len(dec) - len(acc)
    print(f"held for review           : {held}")
    if acc:
        bad = len(acc) - len(acc_right)
        print(f"\nProjected on 6,934 questions: about {round(6934*len(acc)/len(dec)):,} published,"
              f" roughly {round(6934*bad/len(dec)):,} of them wrong.")
    wrong = [d for d in acc if d["letter"] != truth[d["question_id"]]]
    if wrong:
        print("\nAccepted but wrong (these are the ones that would reach students):")
        by = {r["question_id"]: r for r in rows}
        for d in wrong[:15]:
            r = by[d["question_id"]]
            print(f"  [{r['subject']}] {r['question_text'][:88]}")
            print(f"     pipeline {d['letter']}  |  key {truth[d['question_id']]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile")
    ap.add_argument("--validate", help="CSV with known correct_option, to score the pipeline")
    ap.add_argument("--out", default=None)
    ap.add_argument("--review-out", default=None)
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--suggest", action="store_true",
                    help="third pass on disagreements, to seed the review queue "
                         "(never published as a key)")
    args = ap.parse_args()

    api_key = api_key_from_env()

    if args.validate:
        return validate(args.validate, model=args.model, api_key=api_key,
                        workers=args.workers, limit=args.limit)

    if not args.infile:
        ap.error("--in or --validate is required")
    src = pathlib.Path(args.infile)
    with open(src, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if args.limit:
        rows = rows[:args.limit]

    out = pathlib.Path(args.out or str(src).replace("_unkeyed", "_keyed"))
    review = pathlib.Path(args.review_out or str(src).replace("_unkeyed", "_needs_review"))
    done = run(rows, model=args.model, api_key=api_key, workers=args.workers,
               suggest=args.suggest,
               progress_path=progress_path_for(pathlib.Path(str(out) + ".progress"), args.model))

    keyed, held = [], []
    for r in rows:
        d = done.get(r["question_id"])
        if d and d["accepted"]:
            r = dict(r)
            r["correct_option"] = d["letter"]
            r["explanation"] = d["explanation"]
            r["tags"] = r["tags"].replace("needs-key", "auto-keyed")
            # Still a draft. Two passes agreeing is evidence, not proof, and
            # nothing here has been seen by a human who knows the subject.
            r["status"] = "draft"
            keyed.append(r)
        else:
            r = dict(r)
            r["tags"] = r["tags"] + "|review"
            note = (d or {}).get("note", "undecided")
            sug = (d or {}).get("suggestion")
            # Seed the reviewer with a starting point, clearly marked as
            # unverified so it is never mistaken for a decided key.
            r["explanation"] = f"{note}; suggested {sug} (UNVERIFIED)" if sug else note
            held.append(r)

    print(f"\nkeyed (both passes agreed): {len(keyed)}")
    print(f"held for human review     : {len(held)}")
    if held:
        print("  reasons:", dict(Counter((done.get(r['question_id']) or {}).get('note','?')
                                          for r in held).most_common()))
    if not args.apply:
        print("\nDry run. Re-run with --apply to write CSVs.")
        return 0

    for path, data in ((out, keyed), (review, held)):
        if not data:
            continue
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(data)
        print(f"wrote {path} ({len(data)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
