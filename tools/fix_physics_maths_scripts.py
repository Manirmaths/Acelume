"""
Restore lost super/subscripts in Physics and Mathematics questions.

Same root cause as the Chemistry pass (tools/fix_chemistry_formulae.py): the
bank was imported from PDFs where sub/superscript formatting collapsed into
spaces, so `n 2 - 6n - 4` reached students instead of n squared, and
`10m/s 2` instead of m/s squared.

Unlike Chemistry, this is an explicit per-field map rather than a rule engine.
Chemistry formulae follow a tight grammar; algebra does not. In this data a
space-separated digit can be any of:

    x 2          superscript       -> x^2
    log 3 x      subscript (base)  -> \\log_3 x
    123.34 6     numeric base      -> 123.34_6
    3 x 3 n-1    x is MULTIPLICATION, not a variable -> 3 \\times 3^{n-1}
    x(x-5) 2(x+2)   the space is a FRACTION BAR -> \\frac{x(x-5)}{2(x+2)}

No regex distinguishes those; only reading the question and its explanation
does. Every entry below was checked against the stated answer.

    python tools/fix_physics_maths_scripts.py            # dry run
    python tools/fix_physics_maths_scripts.py --apply

Never use `\\,` here -- it contains a literal comma and splits unquoted CSV
fields. Use `\\;`.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.csv"

FIXES: dict[tuple[str, str], str] = {
    # ---------------- Physics: units and dimensions ----------------
    ("PHY-0189", "option_a"): r"\(\frac{q^2}{4\pi\varepsilon_o r^2}\)",
    ("PHY-0189", "option_b"): r"\(\frac{q^2}{4\pi\varepsilon_o r}\)",
    ("PHY-0189", "option_c"): r"\(\frac{q}{4\pi\varepsilon_o r^2}\)",
    ("PHY-0189", "option_d"): r"\(\frac{q}{4\pi\varepsilon_o r}\)",

    ("PHY-0207", "question_text"): r"An object of volume \(1\;\mathrm{m^3}\) and mass 2kg is totally immersed in a liquid of density \(1\;\mathrm{kg\;m^{-3}}\). Calculate its apparent weight.",

    ("PHY-0249", "option_a"): r"\(0.8\;\mathrm{m^3}\)",
    ("PHY-0249", "option_b"): r"\(1.4\;\mathrm{m^3}\)",
    ("PHY-0249", "option_c"): r"\(3.6\;\mathrm{m^3}\)",

    ("PHY-0352", "question_text"): r"If a mango fruit dropped at a height of 50 meters. How long does it reach the ground? (take \(g = 10\;\mathrm{m/s^2}\))",

    ("PHY-0367", "question_text"): r"If a projectile has maximum range of 36m, find the speed of projection (Take \(g = 9.8\;\mathrm{m/s^2}\))",
    ("PHY-0367", "option_c"): r"\(4\;\mathrm{m/s^2}\)",
    ("PHY-0367", "option_d"): r"\(7\;\mathrm{m/s^2}\)",

    ("PHY-0368", "option_a"): r"\(\mathrm{kg\;m^{-2}}\)",
    ("PHY-0368", "option_b"): r"\(\mathrm{kg\;m^{2}}\)",
    ("PHY-0368", "option_c"): r"\(\mathrm{kg\;cm^{3}}\)",

    ("PHY-0369", "option_b"): r"\(ML^{3}T^{2}\)",
    ("PHY-0369", "option_c"): r"\(ML^{3}\)",
    ("PHY-0369", "option_d"): r"\(MLT^{-2}\)",

    ("PHY-0412", "question_text"): r"Calculate the temperature of 6 moles of an ideal gas at a pressure of \(7.6 \times 10^{6}\;\mathrm{Nm^{-2}}\) with a volume of \(10^{-3}\;\mathrm{m^3}\). [\(R = 8.3\;\mathrm{J\;mol^{-1}K^{-1}}\)]",
    ("PHY-0412", "option_a"): r"\(201^\circ\mathrm{C}\)",
    ("PHY-0412", "option_b"): r"\(126^\circ\mathrm{C}\)",
    ("PHY-0412", "option_c"): r"\(153^\circ\mathrm{C}\)",
    ("PHY-0412", "option_d"): r"\(185^\circ\mathrm{C}\)",

    ("PHY-0430", "option_a"): r"\(a = v^2 - \frac{u^2}{2}\)",
    ("PHY-0430", "option_b"): r"\(v^2 = u^2 + 2as\)",
    ("PHY-0430", "option_c"): r"\(s = ut + \frac{1}{2}at^2\)",
    ("PHY-0430", "option_d"): r"\(v^2 - u^2 = 2as\)",

    # ---------------- Mathematics ----------------
    # The space between the two bracketed groups is a fraction bar; options
    # A-C are all fractions and the explanation confirms x(x+5)/[2(x+2)].
    ("MTH-0062", "option_a"): r"\(\frac{x(x-5)}{2(x+2)}\)",
    ("MTH-0062", "option_b"): r"\(\frac{x(x-5)}{2(x-2)}\)",
    ("MTH-0062", "option_c"): r"\(\frac{x(x+5)}{2(x+2)}\)",
    ("MTH-0062", "option_d"): r"\(\frac{x^2+5}{2x+4}\)",

    ("MTH-0071", "option_a"): r"\(\cos x + x^2 + K\)",
    ("MTH-0071", "option_c"): r"\(-\cos x + x^2 + K\)",

    ("MTH-0114", "question_text"): r"Find the remainder when \(x^3 - 2x^2 + 3x - 3\) is divided by \(x^2 + 1\)",

    # log base 3 is a SUBSCRIPT; the 2 on x is a superscript. Explanation
    # ("x^2 = 3^-8") confirms both.
    ("MTH-0152", "question_text"): r"If \(\log_3 x^2 = -8\), what is \(x\)?",

    ("MTH-0158", "question_text"): r"Solve for \(x\) and \(y\) in the equations below: \(x^2 - y^2 = 4\), \(x + y = 2\)",
    ("MTH-0163", "question_text"): r"The nth term of a sequence is \(n^2 - 6n - 4\). Find the sum of the 3rd and 4th terms.",

    # I_3 is the 3x3 identity matrix -- subscript, not superscript.
    ("MTH-0168", "question_text"): r"Given that \(I_3\) is a unit matrix of order 3, find \(|I_3|\)",

    ("MTH-0175", "question_text"): r"If \(y = x^2 - \frac{1}{x}\), find \(\frac{\delta y}{\delta x}\)",
    ("MTH-0175", "option_b"): r"\(2x + x^2\)",
    ("MTH-0175", "option_c"): r"\(2x - x^2\)",

    ("MTH-0196", "option_a"): r"\(S^2 - 2\)",
    ("MTH-0196", "option_d"): r"\(S^2 + 2\)",

    ("MTH-0197", "question_text"): r"If \(x - 4\) is a factor of \(x^2 - x - k\), then \(k\) is",
    ("MTH-0198", "question_text"): r"The remainder when \(6p^3 - p^2 - 47p + 30\) is divided by \(p - 3\) is",

    ("MTH-0200", "option_a"): r"\(s\) varies inversely as \(r\) and \(t^2\)",
    ("MTH-0200", "option_b"): r"\(s\) varies inversely as \(r^2\) and \(t\)",
    ("MTH-0200", "option_c"): r"\(s\) varies directly as \(r^2\) and \(t^2\)",

    ("MTH-0240", "question_text"): r"Find the value of \(k\) if \(y - 1\) is a factor of \(y^3 + 4y^2 + ky - 6\)",
    ("MTH-0241", "question_text"): r"\(y\) varies directly as \(w^2\). When \(y = 8\), \(w = 2\). Find \(y\) when \(w = 3\)",
    ("MTH-0257", "question_text"): r"Find the minimum value of \(y = x^2 - 2x - 3\)",
    ("MTH-0270", "question_text"): r"Factorize \(x^2 + 9x + 20\)",
    ("MTH-0297", "question_text"): r"Solve \(x^2 - 2x - 3 = 0\)",

    # Numeric BASES -- subscripts, not powers. "(159.75)10 = (x)6" is
    # base 10 to base 6.
    ("MTH-0299", "question_text"): r"If \((159.75)_{10} = (x)_6\), find \(x\)",
    ("MTH-0299", "option_a"): r"\(x_6 = 123.34_6\)",
    ("MTH-0299", "option_b"): r"\(x_6 = 424.5_6\)",
    ("MTH-0299", "option_c"): r"\(x_6 = 122.43_6\)",
    ("MTH-0299", "option_d"): r"\(x_6 = 124.45_6\)",

    # log base 5 throughout -- subscripts. Explanation confirms the intent.
    ("MTH-0308", "question_text"): r"Evaluate \(\log_5\left(\frac{y^2 x^5}{125 b^{\frac{1}{2}}}\right)\)",
    ("MTH-0308", "option_a"): r"\(2\log_5 y + 5\log_5 y^2 - 3\)",
    ("MTH-0308", "option_b"): r"\(\log_5 y^2 + 5\log_5 x + 3\)",
    ("MTH-0308", "option_c"): r"\(25\log_y 5 + 3\)",
    ("MTH-0308", "option_d"): r"\(2\log_5 y + 5\log_5 x - \frac{1}{2}\log_5 b - 3\)",

    ("MTH-0317", "option_b"): r"\(x^3 + 2x + k\)",
    ("MTH-0317", "option_d"): r"\(x^3 - 2x + k\)",

    ("MTH-0327", "question_text"): r"Factorize \(k^2 - 2kp + p^2\).",
    ("MTH-0327", "option_c"): r"\(k^2 + p^2\)",
    ("MTH-0327", "option_d"): r"\(k^2 - p^2\)",

    # Here `x` is the MULTIPLICATION sign, not a variable: the sequence
    # 3, 9, 27, 81 has nth term 3 x 3^(n-1).
    ("MTH-0344", "option_a"): r"\(3 \times 3^{n-2}\)",
    ("MTH-0344", "option_b"): r"\(3 \times 3^{n-1}\)",
    ("MTH-0344", "option_c"): r"\(3 \times 3^{n+2}\)",
    ("MTH-0344", "option_d"): r"\(3 \times 3^{n+1}\)",

    ("MTH-0384", "question_text"): r"Find \(\int(x^2 + 3x - 5)\;dx\)",

    ("MTH-0387", "option_c"): r"\(s = \frac{nrp}{mr} + m^2\)",
    ("MTH-0387", "option_d"): r"\(s = \frac{nrp}{nr} + m^2\)",

    ("MTH-0548", "option_d"): r"\((x^2 + 4)\)",
    ("MTH-0549", "option_a"): r"\((m^2 + 1)(m - 2)\)",
    ("MTH-0549", "option_d"): r"\((m^2 + 2)(m - 1)\)",
    ("MTH-0551", "option_c"): r"\(n^2 + n\)",
    ("MTH-0551", "option_d"): r"\(n^2 + 3n + 2\)",
}

# Left untouched: the defect is missing content or a duplicate option, not
# just lost formatting, so any "fix" would be a guess at the exam's intent.
SUSPECT = {
    "MTH-0120": "Options A and C are BOTH the bare string 'x 5' -- identical, and missing their "
                "comparison operators. Given the answer (D: x > 3 or x < -5) they were probably "
                "'x > 5' and 'x < 5', but that is a guess. Two identical options is also a bug in "
                "its own right.",
    "MTH-0243": "Option B reads 'x 1' and option D 'x 5' -- both missing a comparison operator.",
    "PHY-0249": "Option D reads '49.m 3' -- a stray period. Could be 4.9 m^3 or 49 m^3; the other "
                "options (0.8, 1.4, 3.6) suggest 4.9. Question text also mixes '4.2m-3' and "
                "'kgm-3' inconsistently.",
    "MTH-0508": "'a x b' uses x as the name of a binary operation, not multiplication or a "
                "variable. Left as prose deliberately -- rendering it as maths would imply "
                "multiplication and change the question.",
    "MTH-0345": "'(1/7 x 3 1/2)' mixes a multiplication sign with the mixed number 3 1/2. "
                "Needs a human to confirm which is which before encoding.",
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
    applied = 0
    unknown: list[str] = []

    for (qid, field), new in FIXES.items():
        row = by_id.get(qid)
        if row is None:
            unknown.append(qid)
            continue
        old = row[field]
        if old == new:
            continue
        print(f"[{qid}] {field}")
        print(f"   -  {old[:140]}")
        print(f"   +  {new[:140]}")
        applied += 1
        if args.apply:
            row[field] = new

    print(f"\n{applied} fields across {len({q for q, _ in FIXES})} questions")
    if unknown:
        print("UNKNOWN question ids:", ", ".join(unknown))

    print("\nNEEDS HUMAN REVIEW (left untouched):")
    for qid, why in SUSPECT.items():
        print(f"  [{qid}] {why}")

    if args.apply:
        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("\nwritten to data/questions.csv")
    else:
        print("\n(dry run -- pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
