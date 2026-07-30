"""
Restore lost subscripts/charges in Chemistry formulae in data/questions.csv.

The bank was imported from PDFs where sub/superscript formatting was flattened
into spaces, so `Na 2 CO 3` reached students instead of Na(2)CO(3) and `Ca 2+`
instead of Ca(2+). Roughly 61 Chemistry questions / 117 fields are affected.

Formulae are rewritten as LaTeX inside \\( ... \\) using \\mathrm, matching how
the rest of the bank encodes maths and rendering through the existing KaTeX
path. Unicode subscripts (H(2)O) were considered and rejected: glyph coverage
for U+2080-2089 is inconsistent across the app's font stack, whereas KaTeX
output is guaranteed.

    python tools/fix_chemistry_formulae.py            # dry run, prints diffs
    python tools/fix_chemistry_formulae.py --apply    # writes the CSV

IMPORTANT: this only fixes *formatting*. Where a formula is chemically wrong
(a dropped element, an unbalanced equation) the script leaves it alone and
lists it under "NEEDS HUMAN REVIEW" -- silently "correcting" chemistry would
risk teaching the wrong thing, which is worse than a formatting bug.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.csv"
FIELDS = ["question_text", "option_a", "option_b", "option_c", "option_d", "explanation"]

# Two-letter symbols must precede single-letter ones in this alternation, or
# "Cl" would match as "C" followed by a stray "l".
ELEMENTS = (
    "He|Li|Be|Ne|Na|Mg|Al|Si|Cl|Ar|Ca|Fe|Cu|Zn|Br|Ag|Ba|Pb|Mn|Cr|Ni|Sn|Hg|Au|Pt|"
    "H|B|C|N|O|F|P|S|K|I"
)

STATE = r"\(\s*(?:g|l|s|aq)\s*\)"

# A formula run: optional coefficient, one or more element+subscript groups,
# optional charge, optional state symbol, optional hydrate tail.
# Adjacency decides charge vs subscript, and it matters in both directions:
#   `Ca 2+`            -> 2 is the charge magnitude, Ca(2+)      [sign attached]
#   `CH 3 COOC 2 H 5 + H 2 O` -> 5 is a subscript and + is the equation's
#                          plus operator, NOT a charge            [sign spaced]
# So a digit is only disqualified as a subscript when the sign touches it.
# Also excluded: a digit that continues into a decimal or a percentage.
# `A compound contains 40.0% C, 6.7% H 53.3% O` is composition data, not a
# formula -- without this guard "H 53.3%" becomes H(53).
SUBSCRIPT = r"(?:\d+(?![+-.%\d]))?"

# Parenthesised groups: Ca(HCO3)2, Mg(OH)2. The inner content must be element
# symbols, which is what keeps this from matching a state symbol -- `(g)`,
# `(l)`, `(s)`, `(aq)` are lowercase and ELEMENTS is case-sensitive.
# Requires a digit or two element symbols inside, AND excludes anything that is
# purely Roman numerals. Both guards are needed: "(I)." is a single symbol, but
# "(II)" and "(III)" are two and three, and I is iodine -- so numbered equation
# lists like "(II). 2NH3(g) + ..." were being swallowed into the formula.
ROMAN = r"(?![IVX]+\s*\))"
GROUP = (
    rf"\({ROMAN}\s*(?:(?:{ELEMENTS})\s*\d*\s*){{2,}}\)\s*\d*"
    rf"|\({ROMAN}\s*(?:{ELEMENTS})\s*\d+\s*\)\s*\d*"
)

# All-caps English words made entirely of element symbols. Without this,
# "CaCO 3 SALTS" consumes the S of SALTS as sulfur. A general "stop at long
# uppercase runs" rule can't work here -- COOH and SALTS look identical to it.
# Deliberately excludes NO and IN: NO is nitric oxide and In is indium, so
# listing them here broke real formulae ("Na NO 3" stopped after Na).
STOPWORDS = {"SALT", "SALTS", "AND", "THE", "ALL", "NONE", "ONLY", "GAS", "ACID", "BASE", "ONE"}

# Likewise a charge is only a charge when the sign is attached to the digit,
# or when the sign is immediately followed by a state symbol (`OH - (aq)`).
CHARGE = r"(?:\s*(?:\d[+-]|[+-](?=\s*\((?:g|l|s|aq)\)))(?![\w+-]))?"

RUN = re.compile(
    rf"""
    (?<![A-Za-z_])
    (?P<body>
        \d*                                          # coefficient, e.g. 2NO2
        (?:(?:(?:{ELEMENTS})\s*{SUBSCRIPT}|{GROUP})\s*)+   # element/group + subscript
        # Hydrate tail (.10H2O). No whitespace allowed after the dot -- with it,
        # a sentence break like "(I). 3CuO" reads as a hydrate separator.
        (?:\.\d*\s*(?:(?:{ELEMENTS})\s*{SUBSCRIPT}\s*)+)?
    )
    (?P<charge>{CHARGE})                             # charge: 2+, 3+, -
    (?P<state>\s*{STATE})?
    """,
    re.VERBOSE,
)

# Only rewrite runs that actually show the defect: an element immediately
# followed by whitespace and a digit. Without this, ordinary prose containing
# a capital letter ("In the reaction", "Y is") would be swallowed.
DEFECT = re.compile(rf"(?:{ELEMENTS})\s+\d")

# Runs whose *chemistry* looks wrong -- reported, never auto-edited.
SUSPECT = {
    "CHM-0192": "C 6 H 12 6 - glucose is C6H12O6; the O appears to have been dropped on import.",
    "CHM-0179": "5Fe 2+ appears on both sides of the redox equation; product side should be Fe 3+. "
                "Also 'MnO - 4(aq)' has the charge before the subscript; should be MnO4-.",
    "CHM-0227": "Option C reads 'CI 2' with a capital i. Chlorine is Cl (lowercase L) -- classic "
                "OCR I/l confusion. Encoding it as written would render iodine.",
    "CHM-0421": "'CI 2(g)', 'CH 2 CI (s)' and 'HCI g' all use capital i for chlorine's l. Note this "
                "question also appears to duplicate CHM-0177, which has the same text spelled "
                "correctly -- consider retiring one of them.",
    "CHM-0206": "Option A is an ELECTRON CONFIGURATION ('ls 2 2s 2 2P 6 3s 2 3P 2'), not a formula. "
                "The subshells should be lowercase (1s2 2s2 2p6 3s2 3p2) and the leading 'ls' is an "
                "OCR error for '1s'. Treating '2P 6' as a formula would render phosphorus.",
    "CHM-0238": "'40.0% C, 6.7% H 53.3% O' is percentage composition, not a formula -- 'H 53.3%' "
                "must not become a subscript. Needs a comma after 6.7% H.",
    "CHM-0431": "Option B reads 'NaCO 4', which is not a real compound. Likely NaClO4 (perchlorate) "
                "or NaNO3; needs a chemist's eye before encoding.",
    "CHM-0437": "Option D reads 'CNH 2'. Probably CONH2 (amide) with the O dropped on import.",
    "CHM-0412": "Option A reads 'PH 3 CO and CO 2'. There is no compound PH3CO; this is almost "
                "certainly the list 'PH3, CO and CO2' with the comma lost. Needs confirming.",
    "CHM-0453": "Option D reads 'Fe 3 O 4 .2H2 2 O' -- the hydrate tail is malformed (a stray 2). "
                "Should probably be Fe3O4.2H2O.",
}

# Hand-written results for runs no general rule handles correctly.
OVERRIDES: dict[tuple[str, str], str] = {
    # The run legitimately ends in S (sulfur) and the word SALTS follows with no
    # separator, so nothing distinguishes it from a valid tail like COOH.
    # Options a, c and d in this same question already use lowercase "salts".
    ("CHM-0290", "option_b"): r"\(\mathrm{Ca(HCO_{3})_{2}}\) and \(\mathrm{CaCO_{3}}\) salts",
}


def _render_symbols(text: str) -> str:
    """Render a plain element/subscript run (used for parenthesised groups)."""
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        m = re.match(rf"(?:{ELEMENTS})", text[i:])
        if not m:
            i += 1
            continue
        out.append(m.group(0))
        i += m.end()
        d = re.match(r"\s*(\d+)", text[i:])
        if d:
            out.append(f"_{{{d.group(1)}}}")
            i += d.end()
    return "".join(out)


def to_latex(body: str, charge: str | None, state: str | None) -> tuple[str, str]:
    """Turn one spaced-out formula run into \\(\\mathrm{...}\\).

    Returns (latex, tail). `tail` is any text the scan stopped short of -- it
    happens when a STOPWORD is hit ("CaCO3 SALTS") and must be re-appended
    outside the math, or the word would silently disappear.
    """
    out: list[str] = []
    i = 0
    stopped_at: int | None = None
    text = body
    # Leading coefficient stays full-size (2NO2, not 2 as a subscript).
    m = re.match(r"\s*(\d+)", text)
    if m:
        out.append(m.group(1))
        i = m.end()

    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "." and i + 1 < len(text) and not text[i + 1].isspace():
            out.append(r"\cdot ")  # hydrate separator, e.g. Na2CO3.10H2O
            i += 1
            m = re.match(r"(\d+)", text[i:])
            if m:
                out.append(m.group(1))
                i += m.end()
            continue
        if ch == "(":  # parenthesised group: Ca(HCO3)2
            close = text.find(")", i)
            if close == -1:
                i += 1
                continue
            inner = text[i + 1 : close]
            out.append("(" + _render_symbols(inner) + ")")
            i = close + 1
            m = re.match(r"\s*(\d+)", text[i:])
            if m:
                out.append(f"_{{{m.group(1)}}}")
                i += m.end()
            continue
        word = re.match(r"[A-Z]{2,}\b", text[i:])
        if word and word.group(0) in STOPWORDS:
            stopped_at = i  # e.g. "CaCO3 SALTS" -- stop before the English word
            break
        m = re.match(rf"(?:{ELEMENTS})", text[i:])
        if not m:
            i += 1
            continue
        symbol = m.group(0)
        i += m.end()
        out.append(symbol)
        # Same adjacency rule as SUBSCRIPT above.
        m = re.match(r"\s*(\d+)(?![+-])", text[i:])
        if m:
            out.append(f"_{{{m.group(1)}}}")
            i += m.end()

    tail = text[stopped_at:] if stopped_at is not None else ""

    if charge:
        c = charge.replace(" ", "")
        out.append(f"^{{{c}}}")
    if state:
        # \; not \, -- the LaTeX thin space contains a literal comma, which
        # splits unquoted CSV fields. See tools/fix_question_latex.py.
        out.append(r"\;" + state.strip())

    return r"\(\mathrm{" + "".join(out) + r"}\)", tail


def fix_text(value: str) -> str:
    # Never touch text already inside math delimiters.
    parts = re.split(r"(\\\(.+?\\\))", value, flags=re.S)
    for idx, part in enumerate(parts):
        if part.startswith("\\("):
            continue

        def repl(m: re.Match[str]) -> str:
            whole = m.group(0)
            if not DEFECT.search(whole):
                # Consistency pass: a formula in the same field that happens to
                # be spaced correctly (HCl (g), OH - (aq)) still needs wrapping,
                # or one equation renders half in math font and half in prose.
                #
                # Guarded hard, because English words are made of element
                # symbols: "In" is indium, "He" is helium, "Sn" tin. Requiring a
                # charge or a state symbol means only real formulae qualify --
                # "In the reaction above" has neither and is left alone.
                if not (m.group("charge") or m.group("state")):
                    return whole
            # to_latex may stop early at a STOPWORD; re-append what it left.
            latex, tail = to_latex(m.group("body"), m.group("charge"), m.group("state"))
            latex += tail
            # The run greedily eats trailing whitespace; put it back so
            # "C3H7OH → C4H10" doesn't become "C3H7OH→ C4H10".
            trailing = len(whole) - len(whole.rstrip())
            return latex + whole[len(whole) - trailing:] if trailing else latex

        parts[idx] = RUN.sub(repl, part)
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)

    changed = 0
    touched_qs: set[str] = set()
    for row in rows:
        if row["subject"] != "Chemistry":
            continue
        if row["question_id"] in SUSPECT:
            continue
        for f in FIELDS:
            old = row.get(f) or ""
            if not old or not DEFECT.search(old):
                continue
            new = OVERRIDES.get((row["question_id"], f)) or fix_text(old)
            if new != old:
                changed += 1
                touched_qs.add(row["question_id"])
                print(f"[{row['question_id']}] {f}")
                print(f"   -  {old[:150]}")
                print(f"   +  {new[:150]}")
                if args.apply:
                    row[f] = new

    print(f"\n{changed} fields across {len(touched_qs)} questions")

    if SUSPECT:
        print("\nNEEDS HUMAN REVIEW (left untouched -- chemistry looks wrong, not just formatting):")
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
