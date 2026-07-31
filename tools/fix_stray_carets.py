"""
Repair question text where LaTeX delimiters were opened mid-number.

A large group of Physics explanations reached the bank like this:

    Work function=hf=6.\\(6x10^-34x1.3x10\\)^15=8.\\(58x10^-19\\) J.

The `\\(` opens after "6." and closes before "^15", so the leading digit and
the exponent render as prose either side of a fragment of maths. The student
sees something that is not an equation at all.

    python tools/fix_stray_carets.py            # dry run
    python tools/fix_stray_carets.py --apply

NOT touched: explanations using plain-text caret notation consistently, e.g.
"(81/16)^(-1/4) = 2/3" or "3^(x+4) = 3^(2x)". Those are a normal ASCII
convention, read fine as-is, and rewriting ~20 of them is cosmetic risk for
no gain. Also untouched: MTH-0597, where '^' is the NAME of a binary
operation ("Let '*' and '^' be two binary operations") -- rendering that as
maths would change the question.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.csv"
FIELDS = ["question_text", "option_a", "option_b", "option_c", "option_d", "explanation"]

# Generic: the "^1/_9" mixed-fraction notation used in a couple of questions.
FRACTION_RE = re.compile(r"\^(\d+)/_(\d+)")

FIXES: dict[tuple[str, str], str] = {
    ("PHY-0187", "explanation"): r"Work function \(= hf = 6.6 \times 10^{-34} \times 1.3 \times 10^{15} = 8.58 \times 10^{-19}\) J.",
    ("PHY-0230", "explanation"): r"\(B = \frac{F}{qv} = \frac{1.8 \times 10^{-8}}{1.0 \times 10^{-8} \times 3.0 \times 10^{-2}} = 60 = 6.0 \times 10\) T.",
    ("PHY-0267", "explanation"): r"\(F = qE = 1.5 \times 10^{-19} \times 10^{5} = 1.5 \times 10^{-14}\) N.",
    ("PHY-0280", "explanation"): r"\(E = \frac{hc}{\lambda} = \frac{6.63 \times 10^{-34} \times 3 \times 10^{8}}{10^{-10}} = 2.0 \times 10^{-15}\) J.",
    ("PHY-0336", "explanation"): r"\(F = \frac{Gm_1m_2}{r^2} = \frac{6.67 \times 10^{-11} \times 10^{24} \times 10^{27}}{10^{40}} = 6.67\) N.",
    ("PHY-0369", "explanation"): r"From \(F = \frac{Gm_1m_2}{r^2}\), G has dimension \(M^{-1}L^{3}T^{-2}\).",
    ("PHY-0412", "explanation"): r"\(T = \frac{PV}{nR} = \frac{7.6 \times 10^{6} \times 10^{-3}}{6 \times 8.3} \approx 153\) (in the units given).",
    ("PHY-0536", "explanation"): r"Pressure = Force/Area has dimension \(ML^{-1}T^{-2}\).",
    ("PHY-0581", "explanation"): r"\(g = \frac{GM}{R^2} = \frac{6.7 \times 10^{-11} \times 6 \times 10^{24}}{(6.4 \times 10^{6})^2} \approx 9.8\) N/kg.",
    ("PHY-0687", "explanation"): r"\(V = \frac{hf}{e} = \frac{6.63 \times 10^{-34} \times 1.6 \times 10^{16}}{1.6 \times 10^{-19}} = 66.3\) V.",
    ("PHY-0788", "explanation"): r"\(F = qE = 4.6 \times 10^{-5} \times 3.2 \times 10^{4} \approx 1.5\) N.",
    ("PHY-0827", "explanation"): r"Young's modulus has the dimension of pressure: \(ML^{-1}T^{-2}\).",
    ("PHY-0834", "explanation"): r"\(E = hf = 6.63 \times 10^{-34} \times 2.0 \times 10^{15} = 1.33 \times 10^{-18}\) J.",
    ("PHY-0867", "explanation"): r"\(E = \frac{hc}{\lambda} = \frac{6.63 \times 10^{-34} \times 3 \times 10^{8}}{5.68 \times 10^{-6}} \approx 3.49 \times 10^{-20}\) J.",
    ("PHY-0886", "explanation"): r"\(F = qvB\sin 60^\circ = 1.6 \times 10^{-19} \times 3 \times 10^{7} \times 10 \times 0.866 \approx 4.16 \times 10^{-11}\) N.",
    ("PHY-0922", "explanation"): r"Power = Work/time has dimension \(ML^{2}T^{-3}\).",

    # Unit symbol also corrected: lowercase k is "kilo", uppercase K is kelvin.
    # Thermal conductivity is W m^-1 K^-1.
    ("PHY-0830", "option_a"): r"\(4.9 \times 10^{-2}\;\mathrm{Wm^{-1}K^{-1}}\)",
    ("PHY-0830", "option_b"): r"\(5.0 \times 10^{-2}\;\mathrm{Wm^{-1}K^{-1}}\)",
    ("PHY-0830", "option_c"): r"\(5.2 \times 10^{-2}\;\mathrm{Wm^{-1}K^{-1}}\)",
    ("PHY-0830", "option_d"): r"\(5.1 \times 10^{-2}\;\mathrm{Wm^{-1}K^{-1}}\)",
    ("PHY-0830", "explanation"): r"\(k = \frac{\text{Power}}{A \times \text{gradient}} = \frac{288000/7200}{9 \times 90} \approx 4.9 \times 10^{-2}\;\mathrm{Wm^{-1}K^{-1}}\).",

    # Genotypes: the superscript allele must sit inside the delimiters.
    ("BIO-0236", "explanation"): r"Cross \(X^cY\) (colour-blind father) × \(X^CX^c\) (carrier mother) gives offspring \(X^CX^c\), \(X^cX^c\), \(X^CY\), \(X^cY\) — half (50%) are colour-blind (the \(X^cX^c\) daughter and the \(X^cY\) son).",

    ("MTH-0435", "question_text"): r"Evaluate \(\int_{1}^{2} \frac{5}{x}\;dx\)",
    ("MTH-0483", "question_text"): r"Factorise \((4a + 3)^2 - (3a - 2)^2\)",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)

    by_id = {r["question_id"]: r for r in rows}
    changed = 0

    for (qid, field), new in FIXES.items():
        row = by_id.get(qid)
        if row is None or row[field] == new:
            continue
        print(f"[{qid}] {field}")
        print(f"   -  {row[field][:130]}")
        print(f"   +  {new[:130]}")
        changed += 1
        if args.apply:
            row[field] = new

    # Generic mixed-fraction notation, e.g. "^1/_9" -> a rendered fraction.
    for row in rows:
        for f in FIELDS:
            old = row.get(f) or ""
            if not FRACTION_RE.search(old):
                continue
            new = FRACTION_RE.sub(lambda m: rf"\(\frac{{{m.group(1)}}}{{{m.group(2)}}}\)", old)
            print(f"[{row['question_id']}] {f}  (mixed-fraction notation)")
            print(f"   -  {old[:130]}")
            print(f"   +  {new[:130]}")
            changed += 1
            if args.apply:
                row[f] = new

    print(f"\n{changed} fields")

    if args.apply:
        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("written to data/questions.csv")
    else:
        print("(dry run -- pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
