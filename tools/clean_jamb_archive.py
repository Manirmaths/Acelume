"""
Turn the myschool.ng JAMB 1990-2009 scrape into rows in the bank's CSV schema.

This stage deliberately produces questions with NO answer key. Keying is a
separate, measurable step (tools/answer_keys.py) because it is the part that
can be wrong in a way a student cannot detect. Cleaning is mechanical and
reviewable; keying is not.

What this does:
  - parses the per-year and aggregate .txt files
  - drops the 22 "SOURCE DATA ERROR" stubs myschool returned for missing years
  - de-duplicates (the `_to_` aggregate files repeat the per-year files almost
    entirely -- 12,849 records collapse to ~7,945)
  - drops questions already present in data/questions.csv
  - repairs scrape artifacts (doubled apostrophes, stray backslashes,
    replacement characters, collapsed whitespace)
  - normalises naira to the ₦ sign
  - routes figure-dependent questions to a separate file rather than the main
    output, since nobody can answer them without the diagram

Usage:
    python tools/clean_jamb_archive.py --zip jamb_questions_1990_to_2009.zip --out data/staging/
    python tools/clean_jamb_archive.py --zip ... --out ... --apply
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import pathlib
import re
import sys
import tempfile
import zipfile
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[1]
BANK = REPO / "data" / "questions.csv"

# myschool's subject slugs -> the app's canonical subject names (app/subjects.py)
SUBJECT_MAP = {
    "english_language": "English",
    "literature_in_english": "Literature",
    "accounts": "Accounting",
    "biology": "Biology",
    "geography": "Geography",
    "economics": "Economics",
    "government": "Government",
    "commerce": "Commerce",
}
ID_PREFIX = {
    "English": "ENG", "Literature": "LIT", "Accounting": "ACC", "Biology": "BIO",
    "Geography": "GEO", "Economics": "ECO", "Government": "GOV", "Commerce": "COM",
}

Q_START = re.compile(r"^(\d+)\.\s*(.*)$")
OPT = re.compile(r"^([A-E])\.\s*(.+)$")
HEADER = re.compile(r"JAMB (.+?) (\d{4})(?: TO (\d{4}))? — OBJECTIVE", re.I)

COLUMNS = [
    "question_id", "exam_type", "subject", "topic", "subtopic", "difficulty",
    "year", "passage_id", "question_text", "image_url", "option_a", "option_b",
    "option_c", "option_d", "correct_option", "explanation", "tags", "source", "status",
]


def clean_text(s: str) -> str:
    """Repair scrape artifacts. Mechanical only -- never changes meaning."""
    if not s:
        return ""
    # The scrape came through a SQL-ish layer that doubled every apostrophe.
    s = s.replace("''", "'").replace("’", "'")
    s = s.replace("�", "")            # replacement chars from bad decoding
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&#0?39;", "'", s)
    s = re.sub(r"&quot;", '"', s)
    s = re.sub(r"&nbsp;", " ", s)
    s = s.replace("\\", "")                # stray escapes, no LaTeX in this corpus
    # Naira: the corpus writes "N10,500" and "N 7,200". The bank is itself split
    # between ₦ and N, but ₦ is unambiguous -- "N" reads as algebra next to a
    # number. Only convert where a digit follows, so words like "N.C.E." survive.
    s = re.sub(r"\bN\s?(?=\d)", "₦", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (s or "").lower())).strip()


def parse_file(path: pathlib.Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    if "SOURCE DATA ERROR" in text:
        return []
    lines = text.split("\n")
    m = HEADER.match(lines[0].strip())
    # Aggregate files ("1990 TO 2000") cannot attribute a year per question, so
    # they are left blank rather than guessed. The per-year files carry it.
    year = m.group(2) if (m and not m.group(3)) else ""
    slug = re.match(r"jamb_(.+?)_\d{4}", path.name)
    subject = SUBJECT_MAP.get(slug.group(1), "") if slug else ""

    out, cur = [], None
    for raw in lines[2:]:
        line = raw.strip()
        qm, om = Q_START.match(line), OPT.match(line)
        if qm and not om:
            if cur:
                out.append(cur)
            cur = {"stem": qm.group(2).strip(), "options": {},
                   "year": year, "subject": subject}
        elif om and cur is not None:
            cur["options"][om.group(1)] = om.group(2).strip()
        elif line and cur is not None and not cur["options"]:
            cur["stem"] = (cur["stem"] + " " + line).strip()
    if cur:
        out.append(cur)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--out", default=str(REPO / "data" / "staging"))
    ap.add_argument("--apply", action="store_true", help="write files (otherwise dry run)")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(args.zip) as z:
            z.extractall(tmp)
        files = sorted(pathlib.Path(tmp).rglob("*.txt"))
        records = []
        for p in files:
            records.extend(parse_file(p))

        # De-duplicate on cleaned stem + option set.
        seen, uniq = set(), []
        for r in records:
            r["stem"] = clean_text(r["stem"])
            r["options"] = {k: clean_text(v) for k, v in r["options"].items()}
            h = hashlib.md5(
                (norm_key(r["stem"]) + "##" +
                 "|".join(norm_key(r["options"].get(k, "")) for k in "ABCDE")).encode()
            ).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            uniq.append(r)

        # Drop anything the bank already has.
        with open(BANK, encoding="utf-8-sig") as fh:
            bank = {norm_key(r["question_text"]) for r in csv.DictReader(fh)}
        fresh = [r for r in uniq if norm_key(r["stem"]) not in bank]

        keep, figures, rejected = [], [], []
        for r in fresh:
            opts = {k: r["options"].get(k, "") for k in "ABCD"}
            if not r["subject"]:
                rejected.append((r, "unknown subject")); continue
            if any(not v for v in opts.values()):
                rejected.append((r, "fewer than four options")); continue
            if len(r["stem"]) < 25:
                rejected.append((r, "stem too short to be a question")); continue
            if len({v.lower() for v in opts.values()}) < 4:
                rejected.append((r, "duplicate options")); continue
            (figures if "Figure required" in r["stem"] else keep).append(r)

        counters = Counter()

        def rows_for(items, status, tag):
            out = []
            for r in items:
                counters[r["subject"]] += 1
                n = counters[r["subject"]]
                stem = r["stem"].replace("[Figure required]", "").strip()
                out.append({
                    "question_id": f"{ID_PREFIX[r['subject']]}-J{n:05d}",
                    "exam_type": "JAMB", "subject": r["subject"],
                    "topic": "", "subtopic": "", "difficulty": "medium",
                    "year": r["year"], "passage_id": "",
                    "question_text": stem, "image_url": "",
                    "option_a": r["options"]["A"], "option_b": r["options"]["B"],
                    "option_c": r["options"]["C"], "option_d": r["options"]["D"],
                    # Deliberately empty. Keying happens in answer_keys.py so it
                    # can be measured; a blank key cannot teach anything false.
                    "correct_option": "", "explanation": "",
                    "tags": tag, "source": "past-question", "status": status,
                })
            return out

        main_rows = rows_for(keep, "draft", "jamb-archive|needs-key")
        fig_rows = rows_for(figures, "draft", "jamb-archive|needs-key|needs-figure")

        print(f"files                     : {len(files)}")
        print(f"raw records               : {len(records)}")
        print(f"unique                    : {len(uniq)}")
        print(f"not already in the bank   : {len(fresh)}")
        print(f"rejected                  : {len(rejected)}")
        for why, n in Counter(w for _, w in rejected).most_common():
            print(f"    {why:34s} {n}")
        print(f"figure-dependent (separate): {len(fig_rows)}")
        print(f"READY FOR KEYING          : {len(main_rows)}")
        print("\nby subject:")
        for s, n in Counter(r["subject"] for r in main_rows).most_common():
            print(f"    {s:12s} {n}")

        if not args.apply:
            print("\nDry run. Re-run with --apply to write.")
            return 0

        outdir = pathlib.Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        for name, rows in (("jamb_archive_unkeyed.csv", main_rows),
                           ("jamb_archive_needs_figure.csv", fig_rows)):
            with open(outdir / name, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=COLUMNS)
                w.writeheader()
                w.writerows(rows)
            print(f"wrote {outdir / name}  ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
