"""
One-off repair of malformed LaTeX in data/questions.csv.

Context: the frontend renders math through `MathText`, which only treats text
inside \\( ... \\) (or \\[ ... \\]) as LaTeX. Anything outside those delimiters
is printed literally, so a row like `Find \\int cos4 x dx` showed students the
raw source instead of an integral. 41 questions were affected across four
distinct failure modes:

  1. bare_frac      -- `frac {3}{4}` with no backslash and no delimiters
  2. bare_cmd       -- `\\cap`, `\\oplus`, `\\sintheta` sitting outside delimiters
  3. exp_outside    -- `(\\(\\frac{1}{5}\\))^{-1}`, where the exponent is outside
                       the delimiters so it renders as literal text
  4. double_delim   -- `\\\\(int^{2}\\)` (doubled backslash breaks the delimiter)

Fixes are an explicit per-field map, deliberately NOT a blanket regex: this is
exam content where a wrong "correction" silently teaches the wrong thing.
Answers and correct_option are never touched -- only presentation.

IMPORTANT -- never use `\\,` (LaTeX thin space) in this CSV. It contains a
literal comma, and in an unquoted field that splits the row. Use `\\;` instead.
That bug was introduced and caught during this repair; the checker below
guards against it recurring.

Usage:
    python tools/fix_question_latex.py --check    # report only, exit 1 if bad
    python tools/fix_question_latex.py --apply    # rewrite data/questions.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "questions.csv"
FIELDS = ["question_text", "option_a", "option_b", "option_c", "option_d", "explanation"]

# (question_id, field) -> corrected value
FIXES: dict[tuple[str, str], str] = {
    # --- bare `frac {..}{..}` with no backslash ---------------------------------
    ("MTH-0397", "question_text"): r"Find the values of \(x\) for which \(\frac{x+2}{4} - \frac{2x - 3}{3} < 4\)",
    ("MTH-0405", "question_text"): r"The probabilities that John and James pass an examination are \(\frac{3}{4}\) and \(\frac{3}{5}\) respectively. Find the probability of both boys failing the examination.",
    ("MTH-0405", "option_a"): r"\(\frac{1}{10}\)",
    ("MTH-0405", "option_b"): r"\(\frac{2}{10}\)",
    ("MTH-0405", "option_c"): r"\(\frac{9}{20}\)",
    ("MTH-0405", "option_d"): r"\(\frac{11}{20}\)",
    ("MTH-0602", "question_text"): r"Make \(x\) the subject of the formula: \(y = \frac{3x - 9c}{4x + 5d}\)",
    ("MTH-0602", "option_a"): r"\(x = \frac{-(9c - 5dy)}{4y - 3}\)",
    ("MTH-0602", "option_b"): r"\(x = \frac{9c + 5dy}{4y - 3}\)",
    ("MTH-0602", "option_c"): r"\(x = \frac{9c - 5dy}{4y - 3}\)",
    ("MTH-0602", "option_d"): r"\(x = \frac{-(9c + 5dy)}{4y - 3}\)",
    ("MTH-0609", "question_text"): r"Evaluate the following limit: \(\lim_{x\to 2} \frac{x^2 + 4x - 12}{x^2 - 2x}\)",
    ("MTH-0614", "option_a"): r"\(\frac{7}{8}\)",
    ("MTH-0614", "option_b"): r"\(\frac{3}{8}\)",
    ("MTH-0614", "option_d"): r"\(\frac{1}{8}\)",
    ("MTH-0615", "option_b"): r"\(y = \frac{5}{3}x - 2\)",
    ("MTH-0616", "option_a"): r"\(\frac{dy}{dx} = \frac{10x^{5/3}}{3} - \frac{8x^{2/3}}{3}\)",
    ("MTH-0616", "option_b"): r"\(\frac{dy}{dx} = \frac{10x^{2/3}}{3} - \frac{8x^{5/3}}{3}\)",
    ("MTH-0616", "option_c"): r"\(\frac{dy}{dx} = \frac{10x^{5/3}}{3} - \frac{8x^{5/3}}{3}\)",
    ("MTH-0616", "option_d"): r"\(\frac{dy}{dx} = \frac{10x^{2/3}}{3} - \frac{8x^{2/3}}{3}\)",
    ("MTH-0618", "option_b"): r"\(\frac{-10}{3}\)",
    ("MTH-0618", "option_c"): r"\(\frac{44}{3}\)",
    ("MTH-0618", "option_d"): r"\(\frac{64}{3}\)",
    ("MTH-0624", "option_a"): r"\(\frac{1}{3}\)",
    ("MTH-0624", "option_b"): r"\(\frac{2}{9}\)",
    ("MTH-0624", "option_c"): r"\(\frac{2}{3}\)",
    ("MTH-0624", "option_d"): r"\(\frac{8}{33}\)",
    ("MTH-0146", "question_text"): r"Find the derivative of \(\frac{\sin\theta}{\cos\theta}\)",

    # --- bare LaTeX commands outside delimiters ---------------------------------
    ("MTH-0123", "question_text"): r"A binary operation \(\oplus\) on real numbers is defined by \(x \oplus y = xy + x + y\) for two real numbers \(x\) and \(y\). Find the value of \(3 \oplus -\frac{2}{3}\).",
    ("MTH-0154", "question_text"): r"If P is a set of all prime factors of 30 and Q is a set of all factors of 18 less than 10, find \(P \cap Q\)",
    ("MTH-0166", "question_text"): r"The binary operation on the set of real numbers is defined by \(m * n = \frac{mn}{2}\) for all \(m, n \in R\). If the identity element is 2, find the inverse of -5",
    ("MTH-0195", "question_text"): r"If \(P = \{x : x \text{ is odd}, -1 < x \le 20\}\) and \(Q = \{y : y \text{ is prime}, -2 < y \le 25\}\), find \(P \cap Q\)",
    ("MTH-0228", "question_text"): r"Integrate \(\frac{1 + x}{x^{3}} \; \mathrm{d}x\)",
    ("MTH-0237", "question_text"): r"If \(P = \{1,2,3,4,5\}\) and \(P \cup Q = \{1,2,3,4,5,6,7\}\), list the elements in Q",
    ("MTH-0254", "question_text"): r"If \(\sin\theta = \frac{12}{13}\), find the value of \(1 + \cos\theta\)",
    ("MTH-0304", "question_text"): r"Given that S and T are sets of real numbers such that \(S = \{x : 0 \le x \le 5\}\) and \(T = \{x : -2 < x < 3\}\), find \(S \cup T\)",
    ("MTH-0351", "question_text"): r"If Q is a factor of 18 and T is prime numbers between 2 and 18. What is \(Q \cap T\)?",
    ("MTH-0360", "question_text"): r"Evaluate \((\sin 45^\circ + \sin 30^\circ)\) in surd form",
    ("MTH-0439", "question_text"): r"A binary operation \(\otimes\) is defined by \(m \otimes n = mn + m - n\) on the set of real numbers, for all \(m, n \in R\). Find the value of \(3 \otimes (2 \otimes 4)\).",
    ("MTH-0552", "question_text"): r"If the binary operation \(\ast\) is defined by \(m \ast n = mn + m + n\) for any real number m and n, find the identity of the elements under this operation",
    ("MTH-0661", "explanation"): r"\(P \setminus Q = \{2\}\), \(Q \setminus P = \{1,9\}\); union \(= \{1,2,9\}\).",

    # --- exponent / structure outside the delimiters -----------------------------
    ("MTH-0098", "question_text"): r"Evaluate \(\int_{0}^{2}(x^3 + x^2)\;dx\).",
    ("MTH-0138", "question_text"): r"Evaluate \(\int_{0}^{1}(3 - 2x)\;dx\)",
    ("MTH-0462", "question_text"): r"Integrate \(\int_{-1}^{2} (2x^2 + x) \; \mathrm{d}x\)",
    ("MTH-0365", "question_text"): r"Simplify \(3^{n-1} \times \frac{27^{n+1}}{81^n}\)",
    ("MTH-0365", "option_c"): r"\(3n\)",
    ("MTH-0365", "option_d"): r"\(3^{n+1}\)",
    ("MTH-0390", "question_text"): r"Simplify \(\left(\sqrt[3]{64a^3}\right)^{-1}\)",
    ("MTH-0471", "question_text"): r"Evaluate \(\left(\frac{6}{0.32} \div \frac{2}{0.084}\right)^{-1}\) correct to 1 decimal place.",
    ("MTH-0481", "question_text"): r"If \(25^{1-x} \times 5^{x+2} \div \left(\frac{1}{125}\right)^{x} = 625^{-1}\), find the value of \(x\).",
    ("MTH-0496", "question_text"): r"What is the product of \(\frac{27}{5}\), \((3)^{-3}\) and \(\left(\frac{1}{5}\right)^{-1}\)?",
    ("MTH-0559", "question_text"): r"Solve for \(k\) in the equation \(\left(\frac{1}{8}\right)^{k+2} = 1\)",
    ("MTH-0601", "question_text"): r"The area A of a circle is increasing at a constant rate of \(1.5\;\mathrm{cm^2s^{-1}}\). Find, to 3 significant figures, the rate at which the radius r of the circle is increasing when the area is \(2\;\mathrm{cm^2}\)",

    # --- doubled backslash breaking the opening delimiter ------------------------
    ("MTH-0176", "question_text"): r"Evaluate \(\int_{1}^{2}(x^2 - 4x)\;dx\)",
    ("MTH-0452", "question_text"): r"If \(4\sin^2 x - 3 = 0\), find the value of \(x\), when \(0^\circ \le x \le 90^\circ\)",
    ("MTH-0598", "question_text"): r"Evaluate \(\int_{0}^{1} \left(4x - 6\sqrt[3]{x^2}\right)\;dx\)",
}

INLINE = re.compile(r"\\\((.+?)\\\)", re.S)
DISPLAY = re.compile(r"\\\[(.+?)\\\]", re.S)


def problems(value: str) -> list[str]:
    """Return the names of LaTeX problems detected in a single field."""
    found: list[str] = []
    if "\\," in value:
        # A literal comma inside an unquoted CSV field splits the row.
        found.append("thin_space_comma")
    if value.count("\\(") != value.count("\\)"):
        found.append("unbalanced_delimiters")
        return found
    if re.search(r"\\\\\(", value):
        found.append("double_backslash_delimiter")
    outside = DISPLAY.sub(" ", INLINE.sub(" ", value))
    if re.search(r"\\[a-zA-Z]+", outside):
        found.append("bare_latex_outside_delimiters")
    if re.search(r"(?<!\\)\bfrac\s*\{", outside):
        found.append("bare_frac_without_backslash")
    if re.search(r"[\^_]\s*(\{|\\\()", outside):
        found.append("exponent_outside_delimiters")
    return found


def load() -> tuple[list[str], list[dict[str, str]]]:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def scan(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[str]]:
    out: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        for field in FIELDS:
            value = row.get(field) or ""
            if not value:
                continue
            found = problems(value)
            if found:
                out[(row["question_id"], field)] = found
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write the fixes to disk")
    parser.add_argument("--check", action="store_true", help="report problems, exit 1 if any")
    args = parser.parse_args()

    fieldnames, rows = load()

    if args.apply:
        by_id = {row["question_id"]: row for row in rows}
        applied = missing = 0
        for (qid, field), new in FIXES.items():
            row = by_id.get(qid)
            if row is None:
                print(f"  ! unknown question_id in FIXES: {qid}")
                missing += 1
                continue
            if row[field] != new:
                row[field] = new
                applied += 1
        with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"applied {applied} field fixes ({missing} unknown ids)")
        fieldnames, rows = load()

    remaining = scan(rows)
    if remaining:
        print(f"\n{len(remaining)} field(s) still have LaTeX problems:")
        for (qid, field), why in sorted(remaining.items()):
            print(f"  [{qid}] {field}: {', '.join(why)}")
        return 1

    print(f"OK - {len(rows)} questions, no LaTeX problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
