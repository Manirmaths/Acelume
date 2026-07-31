"""
Replace figure-dependent questions with diagram-free ones on the same concept.

574 questions in the archive say "[Figure required]" and the figure was never
scraped. They are unanswerable by anyone, so they cannot be keyed -- but the
CONCEPT each one tests is usually recoverable from the stem and the options
("The part labelled 3 is the / A. leaf scar B. lenticel..." is plainly about
stem external features).

So rather than discard them, write a fresh question testing the same idea in
words. The replacement is original content, not a past question, and is tagged
and sourced as such -- passing off a generated question as a real JAMB paper
question would be a lie to the student about what they are practising.

The safeguard is the interesting part. A generator that invents both question
and answer is unfalsifiable: it cannot notice that its question is ambiguous,
has two defensible answers, or that the "correct" option is wrong. So every
generated question is then handed to the SAME independent two-pass solver used
for real questions (tools/keying_core.py), which has never seen the intended
answer. If the solver cannot recover it, the question is discarded.

That inverts the usual failure mode: instead of hoping the generator is right,
we keep only questions that a fresh solver independently agrees on.

    python tools/replace_figure_questions.py --limit 20
    python tools/replace_figure_questions.py --subject Biology --apply
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
from answer_keys import load_progress, progress_path_for  # noqa: E402
from keying_core import ModelError, api_key_from_env, call_model, decide  # noqa: E402

csv.field_size_limit(10 ** 7)
REPO = pathlib.Path(__file__).resolve().parents[1]
STAGING = REPO / "data" / "staging"

GENERATE = """This is a Nigerian JAMB {subject} past question that referred to a diagram
which has been lost, so the question can no longer be answered:

  {stem}
  A. {A}
  B. {B}
  C. {C}
  D. {D}

Write ONE new multiple-choice question that tests the same underlying knowledge
WITHOUT needing any diagram, image, table or figure.

Requirements:
- Self-contained. A student must be able to answer from the text alone.
- Same subject and topic, same difficulty, JAMB style.
- Exactly four options, exactly one unambiguously correct.
- The three wrong options must be plausible, not obviously silly.
- Do not mention a diagram, figure, label, or "the part labelled".
- Do not reference "the passage above" or any external material.

Reply with strict JSON and nothing else:
{{"question": "...", "A": "...", "B": "...", "C": "...", "D": "...",
  "correct": "A", "topic": "...", "explanation": "..."}}"""


def parse_generated(raw: str) -> dict | None:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not all(k in d for k in ("question", "A", "B", "C", "D", "correct")):
        return None
    if d["correct"] not in ("A", "B", "C", "D"):
        return None
    opts = [str(d[k]).strip() for k in "ABCD"]
    if any(not o for o in opts) or len({o.lower() for o in opts}) < 4:
        return None
    q = str(d["question"]).strip()
    if len(q) < 20:
        return None
    # A replacement that still leans on a picture defeats the entire point.
    if re.search(r"\b(diagram|figure|the part labell?ed|shown above|illustrat|"
                 r"the graph above|the table above|image)\b", q, re.I):
        return None
    return d


def make_one(row: dict, *, model: str, api_key: str) -> dict:
    """Generate a replacement, then verify it with an independent solver."""
    base = {"subject": row["subject"], "stem": row["question_text"],
            "A": row["option_a"], "B": row["option_b"],
            "C": row["option_c"], "D": row["option_d"]}
    raw = call_model(GENERATE.format(**base), model=model, api_key=api_key,
                     temperature=0.7, max_tokens=500)
    gen = parse_generated(raw)
    if gen is None:
        return {"question_id": row["question_id"], "ok": False, "note": "unusable generation"}

    # Independent check. The solver is given only the question, never the
    # intended answer, and uses the same shuffled two-pass gate as real
    # questions. Disagreement means the question is ambiguous or wrong -- either
    # way it is not fit to put in front of a student.
    probe = {"question_id": row["question_id"] + "-gen", "subject": row["subject"],
             "question_text": gen["question"], "option_a": gen["A"],
             "option_b": gen["B"], "option_c": gen["C"], "option_d": gen["D"]}
    v = decide(probe, model=model, api_key=api_key, explain=False)
    if not v.accepted:
        return {"question_id": row["question_id"], "ok": False,
                "note": f"solver undecided ({v.note})"}
    if v.letter != gen["correct"]:
        return {"question_id": row["question_id"], "ok": False,
                "note": f"solver said {v.letter}, generator meant {gen['correct']}"}

    return {"question_id": row["question_id"], "ok": True, "note": "",
            "question": gen["question"], "A": gen["A"], "B": gen["B"],
            "C": gen["C"], "D": gen["D"], "correct": gen["correct"],
            "topic": str(gen.get("topic", "")).strip()[:80],
            "explanation": re.sub(r"\s+", " ", str(gen.get("explanation", ""))).strip()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile",
                    default=str(STAGING / "jamb_archive_needs_figure.csv"))
    ap.add_argument("--out", default=str(STAGING / "jamb_figure_replacements.csv"))
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--subject", default="")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    api_key = api_key_from_env()

    with open(args.infile, encoding="utf-8-sig") as fh:
        rows = [dict(r) for r in csv.DictReader(fh)]
    if args.subject:
        rows = [r for r in rows if r["subject"] == args.subject]
    if args.limit:
        rows = rows[:args.limit]

    prog = progress_path_for(pathlib.Path(args.out + ".progress"), args.model)
    done = load_progress(prog)
    todo = [r for r in rows if r["question_id"] not in done]
    print(f"{len(done)} already attempted, {len(todo)} to do")

    if todo:
        with open(prog, "a", encoding="utf-8") as log, \
                ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(make_one, r, model=args.model, api_key=api_key): r
                       for r in todo}
            for i, fut in enumerate(as_completed(futures), start=1):
                r = futures[fut]
                try:
                    rec = fut.result()
                except ModelError as e:
                    rec = {"question_id": r["question_id"], "ok": False,
                           "note": f"model error: {e}"}
                log.write(json.dumps(rec, ensure_ascii=False) + "\n")
                log.flush()
                done[rec["question_id"]] = rec
                if i % 20 == 0 or i == len(todo):
                    ok = sum(1 for x in done.values() if x.get("ok"))
                    print(f"  {i}/{len(todo)}  kept {ok}/{len(done)}"
                          f" ({100*ok/max(1,len(done)):.1f}%)")

    kept = [d for d in done.values() if d.get("ok")]
    dropped = [d for d in done.values() if not d.get("ok")]
    print(f"\nkept    : {len(kept)}")
    print(f"discarded: {len(dropped)}")
    if dropped:
        print("  why:", dict(Counter(
            re.sub(r"\(.*\)|said [A-D].*", "", d.get("note", "?")).strip()
            for d in dropped).most_common()))

    idx = {r["question_id"]: r for r in rows}
    if kept:
        print("\nsample replacement:")
        s = kept[0]
        o = idx[s["question_id"]]
        print(f"  was: {o['question_text'][:90]}")
        print(f"  now: {s['question'][:90]}")
        print(f"       A. {s['A'][:44]}   B. {s['B'][:44]}")
        print(f"       correct {s['correct']}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write the CSV.")
        return 0
    if not kept:
        print("nothing to write")
        return 0

    fields = list(rows[0].keys())
    out = pathlib.Path(args.out)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for d in kept:
            src = idx[d["question_id"]]
            row = dict(src)
            row["question_id"] = src["question_id"].replace("-J", "-R", 1)
            row["question_text"] = d["question"]
            row["option_a"], row["option_b"] = d["A"], d["B"]
            row["option_c"], row["option_d"] = d["C"], d["D"]
            row["correct_option"] = d["correct"]
            row["explanation"] = d["explanation"]
            row["topic"] = d.get("topic", "") or src.get("topic", "")
            # NOT a past question. It is inspired by one whose figure was lost,
            # and a student is entitled to know the difference.
            row["source"] = "original"
            row["year"] = ""
            row["tags"] = "figure-replacement|generated|solver-verified"
            row["status"] = "draft"
            w.writerow(row)
    print(f"wrote {out} ({len(kept)} rows)")
    print("These are ORIGINAL questions, not past questions. They are tagged and")
    print("sourced as such, and left as drafts for review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
