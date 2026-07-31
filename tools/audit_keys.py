"""
Blind audit of answer keys already in the bank.

Nobody has ever measured whether the 10,000+ keys currently served to students
are correct. This finds out, without changing anything.

Two rules make the result meaningful:

  1. BLIND. The model never sees the stored key, and never sees the stored
     explanation -- which usually names the answer outright. Show it either and
     it agrees with whatever is there, and the audit measures nothing.

  2. NEVER AUTO-OVERWRITE. A disagreement means one of the two is wrong, and
     the pipeline is not automatically the better one. Measured against verified
     answers it sits around 91% alone. So this writes a review file for a human
     and stops.

Some disagreements are not errors at all but genuinely contested questions --
whether the Alaafin of Oyo was an absolute or a constitutional monarch is
argued both ways in Nigerian textbooks. Those still deserve attention: an
ambiguous question with a confident explanation is its own problem.

    python tools/audit_keys.py --in data/questions.csv --limit 300
    python tools/audit_keys.py --in data/questions.csv --subject Government --apply
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from answer_keys import progress_path_for, run  # noqa: E402
from keying_core import api_key_from_env  # noqa: E402

csv.field_size_limit(10 ** 7)
REPO = pathlib.Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default=str(REPO / "data" / "questions.csv"))
    ap.add_argument("--out", default=str(REPO / "data" / "staging" / "key_audit_disagreements.csv"))
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="sample size (0 = all)")
    ap.add_argument("--subject", default="")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    api_key = api_key_from_env()

    with open(args.infile, encoding="utf-8-sig") as fh:
        rows = [dict(r) for r in csv.DictReader(fh)]
    for r in rows:
        r.setdefault("question_id", r.get("﻿question_id", ""))
    rows = [r for r in rows if r.get("correct_option") in ("A", "B", "C", "D")]

    # Questions carrying a diagram cannot be judged by a text-only model: it
    # never sees the image, so it answers from the words alone and "disagrees"
    # with a key that is perfectly correct. The 2025 Mathematics batch reported
    # exactly two disagreements and BOTH were this -- a weights table and a
    # triangle, each with a real SVG the model could not see. Auditing them is
    # not merely wasted spend, it manufactures false alarms in the review queue.
    with_image = [r for r in rows if (r.get("image_url") or "").strip()]
    rows = [r for r in rows if not (r.get("image_url") or "").strip()]
    if with_image:
        print(f"skipping {len(with_image)} question(s) with a diagram -- "
              f"a text model cannot see them, so it cannot audit them")
    if args.subject:
        rows = [r for r in rows if r["subject"] == args.subject]
    if args.limit:
        import random
        random.Random(args.seed).shuffle(rows)
        rows = rows[:args.limit]

    truth = {r["question_id"]: r["correct_option"] for r in rows}

    # Strip anything that leaks the answer before the model sees a row. The
    # stored explanation almost always states it outright.
    blind = [{"question_id": r["question_id"], "subject": r["subject"],
              "question_text": r["question_text"],
              "option_a": r["option_a"], "option_b": r["option_b"],
              "option_c": r["option_c"], "option_d": r["option_d"]} for r in rows]

    prog = progress_path_for(pathlib.Path(args.out + ".progress"), args.model)
    done = run(blind, model=args.model, api_key=api_key, workers=args.workers,
               progress_path=prog, explain=False)

    dec = [done[r["question_id"]] for r in blind if r["question_id"] in done]
    agree = [d for d in dec if d["accepted"] and d["letter"] == truth[d["question_id"]]]
    disagree = [d for d in dec if d["accepted"] and d["letter"] != truth[d["question_id"]]]
    unsure = [d for d in dec if not d["accepted"]]

    print("\n================ KEY AUDIT ================")
    print(f"questions checked      : {len(dec)}")
    print(f"agreed with stored key : {len(agree)}  ({100*len(agree)/max(1,len(dec)):.1f}%)")
    print(f"DISAGREED (both passes): {len(disagree)}  ({100*len(disagree)/max(1,len(dec)):.1f}%)")
    print(f"pipeline unsure        : {len(unsure)}")
    print("\nA disagreement is not proof the stored key is wrong. It is a")
    print("question worth a human looking at, and nothing more.")

    by = defaultdict(lambda: [0, 0])
    idx = {r["question_id"]: r for r in rows}
    for d in dec:
        s = idx[d["question_id"]]["subject"]
        by[s][1] += 1
        if d["accepted"] and d["letter"] != truth[d["question_id"]]:
            by[s][0] += 1
    print("\ndisagreement rate by subject:")
    for s, (bad, tot) in sorted(by.items(), key=lambda kv: -kv[1][0] / max(1, kv[1][1])):
        print(f"  {s:12s} {bad:4d}/{tot:4d}  {100*bad/max(1,tot):5.1f}%")

    if disagree:
        print("\nfirst few disagreements:")
        for d in disagree[:8]:
            r = idx[d["question_id"]]
            print(f"\n  [{r['question_id']} {r['subject']}] {r['question_text'][:95]}")
            print(f"     stored   {truth[d['question_id']]}: "
                  f"{r['option_' + truth[d['question_id']].lower()][:58]}")
            print(f"     pipeline {d['letter']}: {r['option_' + d['letter'].lower()][:58]}")
            if d.get("reason"):
                print(f"     because  {d['reason'][:110]}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write the review CSV.")
        return 0

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["question_id", "subject", "topic", "question_text",
                    "option_a", "option_b", "option_c", "option_d",
                    "stored_key", "stored_answer_text", "pipeline_key",
                    "pipeline_answer_text", "pipeline_reason", "stored_explanation",
                    "verdict"])
        for d in disagree:
            r = idx[d["question_id"]]
            w.writerow([
                r["question_id"], r["subject"], r.get("topic", ""), r["question_text"],
                r["option_a"], r["option_b"], r["option_c"], r["option_d"],
                truth[d["question_id"]], r["option_" + truth[d["question_id"]].lower()],
                d["letter"], r["option_" + d["letter"].lower()],
                d.get("reason", ""), r.get("explanation", ""), "",
            ])
    print(f"wrote {out} ({len(disagree)} rows) -- fill in the 'verdict' column.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
