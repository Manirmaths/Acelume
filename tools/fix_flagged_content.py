"""
Resolve the content errors escalated by the earlier formatting passes.

These are questions where the *chemistry or maths itself* was wrong, not just
the formatting, so the formatting tools deliberately skipped them rather than
faithfully encoding an error. Each fix below is justified by the question's own
explanation or by the surrounding options -- none is a guess.

    python tools/fix_flagged_content.py            # dry run
    python tools/fix_flagged_content.py --apply

Anything still genuinely ambiguous stays in STILL_OPEN at the bottom and is
reported, not edited.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.csv"

FIXES: dict[tuple[str, str], str] = {
    # Glucose. The explanation says "ferments glucose into ethanol", and the
    # products (2 ethanol + 2 CO2) only balance from C6H12O6. The O was
    # dropped on import. "25 o" is also OCR for 25 degrees.
    ("CHM-0192", "question_text"): r"At \(25^\circ\mathrm{C}\) and zymase as catalyst, \(\mathrm{C_{6}H_{12}O_{6}} \to \mathrm{2C_{2}H_{5}OH} + \mathrm{2CO_{2}}\) + energy. The reaction represented by the equation above is useful in the production of",

    # The explanation spells the balanced equation out: the product side is
    # 5Fe(3+), not 5Fe(2+). Iron is oxidised; permanganate is reduced.
    ("CHM-0179", "question_text"): r"\(\mathrm{MnO_{4}^{-}\;(aq)} + Y + \mathrm{5Fe^{2+}\;(aq)} \to \mathrm{Mn^{2+}\;(aq)} + \mathrm{5Fe^{3+}\;(aq)} + \mathrm{4H_{2}O\;(l)}\). In the equation above, Y is",
    ("CHM-0179", "option_a"): r"\(\mathrm{5H^{+}\;(aq)}\)",
    ("CHM-0179", "option_b"): r"\(\mathrm{4H^{+}\;(aq)}\)",
    ("CHM-0179", "option_c"): r"\(\mathrm{10H^{+}\;(aq)}\)",
    ("CHM-0179", "option_d"): r"\(\mathrm{8H^{+}\;(aq)}\)",

    # Electron configurations, not formulae. Subshells are lowercase; "ls"/"Is"
    # are OCR for "1s". The explanation confirms Mg(2+) is 1s2 2s2 2p6.
    ("CHM-0206", "option_a"): r"\(1s^2\;2s^2\;2p^6\;3s^2\;3p^2\)",
    ("CHM-0206", "option_b"): r"\(1s^2\;2s^2\;2p^6\)",
    ("CHM-0206", "option_c"): r"\(1s^2\;2s^2\;2p^6\;3s^2\)",
    ("CHM-0206", "option_d"): r"\(1s^2\;2s^2\;2p^4\)",

    # Percentage composition -- needs the missing comma so "H 53.3%" cannot be
    # misread as a subscript.
    ("CHM-0238", "question_text"): r"A compound contains 40.0% C, 6.7% H, 53.3% O. If the molecular mass of the compound is 180, its molecular formula is [C = 12, H = 1, O = 16]",
    ("CHM-0238", "option_a"): r"\(\mathrm{CH_{2}O}\)",
    ("CHM-0238", "option_b"): r"\(\mathrm{C_{3}H_{6}O_{3}}\)",
    ("CHM-0238", "option_c"): r"\(\mathrm{C_{6}H_{6}O_{3}}\)",
    ("CHM-0238", "option_d"): r"\(\mathrm{C_{6}H_{12}O_{6}}\)",

    # "CI 2" is chlorine (Cl), not carbon-iodine. The option list is a set of
    # gases: N2, N2O, Cl2, NH3.
    ("CHM-0227", "option_a"): r"\(\mathrm{N_{2}}\)",
    ("CHM-0227", "option_b"): r"\(\mathrm{N_{2}O}\)",
    ("CHM-0227", "option_c"): r"\(\mathrm{Cl_{2}}\)",
    ("CHM-0227", "option_d"): r"\(\mathrm{NH_{3}}\)",

    # Option D is "PH3 and CO", so option A is the same list plus CO2 -- the
    # comma was lost. There is no compound "PH3CO".
    ("CHM-0412", "option_a"): r"\(\mathrm{PH_{3}}\), \(\mathrm{CO}\) and \(\mathrm{CO_{2}}\)",
    ("CHM-0412", "option_b"): r"\(\mathrm{CO}\) and \(\mathrm{C}\)",
    ("CHM-0412", "option_c"): r"\(\mathrm{N_{2}}\), \(\mathrm{CO}\) and \(\mathrm{CO_{2}}\)",
    ("CHM-0412", "option_d"): r"\(\mathrm{PH_{3}}\) and \(\mathrm{CO}\)",

    # Hydrated iron oxides. The stray 2 in "2H2 2 O" is an import artifact.
    ("CHM-0453", "option_a"): r"\(\mathrm{Fe^{3+}(H_{2}O)_{6}}\)",
    ("CHM-0453", "option_b"): r"\(\mathrm{FeO\cdot H_{2}O}\)",
    ("CHM-0453", "option_c"): r"\(\mathrm{Fe_{2}O_{3}\cdot xH_{2}O}\)",
    ("CHM-0453", "option_d"): r"\(\mathrm{Fe_{3}O_{4}\cdot 2H_{2}O}\)",

    # The bank/UI has four option columns. These five legacy rows were imported
    # with a fifth option flattened into option D and correct_option="E", so an
    # active student could never select the stored answer. Keep the content for
    # repair, but do not serve an impossible question.
    ("GOV-0203", "status"): "draft",
    ("MTH-0275", "status"): "draft",
    ("PHY-0138", "status"): "draft",
    ("PHY-0174", "status"): "draft",
    ("PHY-0196", "status"): "draft",
}

STILL_OPEN = {
    "CHM-0421": "Corrupted DUPLICATE of CHM-0177. Both ask the same question about methane "
                "chlorination, but CHM-0421 spells chlorine with a capital i ('CI 2', 'HCI') "
                "AND has the wrong product (CH2Cl instead of CH3Cl). CHM-0177 is correct. "
                "Recommend retiring CHM-0421 (set status=draft) rather than repairing it.",
    "CHM-0431": "Option B reads 'concentrated NaCO 4', which is not a real compound. Possibly "
                "Na2CO3. It is a distractor (answer is A, anhydrous CaCl2), so nothing hinges "
                "on it, but it should not ship as written.",
    "CHM-0437": "Option D reads 'CNH 2'. Likely CONH2 (amide) with the O dropped, but the "
                "option list mixes functional groups inconsistently. A chemist should confirm.",
    "MTH-0120": "Options A and C are the IDENTICAL string 'x 5', both missing a comparison "
                "operator. Two identical options is a bug regardless of formatting. From the "
                "answer (D: x > 3 or x < -5) they were probably 'x > 5' and 'x < 5'.",
    "MTH-0243": "Option B reads 'x 1' and option D 'x 5' -- both missing comparison operators.",
    "PHY-0249": "Option D reads '49.m 3'. Given the other options (0.8, 1.4, 3.6) it is "
                "probably 4.9, but the stray period makes 49 possible too.",
    "MTH-0345": "'(1/7 x 3 1/2)' mixes a multiplication sign with the mixed number 3 1/2.",
    "MTH-0508": "'a x b' names a binary operation 'x'. Correct as prose -- listed here only so "
                "nobody 'fixes' it into multiplication later.",
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
        if row is None:
            print(f"  ! unknown question_id {qid}")
            continue
        if row[field] == new:
            continue
        print(f"[{qid}] {field}")
        print(f"   -  {row[field][:130]}")
        print(f"   +  {new[:130]}")
        changed += 1
        if args.apply:
            row[field] = new

    print(f"\n{changed} fields across {len({q for q, _ in FIXES})} questions")
    print("\nSTILL OPEN (needs a human decision):")
    for qid, why in STILL_OPEN.items():
        print(f"  [{qid}] {why}")

    if args.apply:
        temp = CSV_PATH.with_suffix(".csv.flagged-content.tmp")
        backup = CSV_PATH.with_suffix(".csv.flagged-content.bak")
        with temp.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        shutil.copy2(CSV_PATH, backup)
        temp.replace(CSV_PATH)
        print(f"\nbackup -> {backup}")
        print("written to data/questions.csv")
    else:
        print("\n(dry run -- pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
