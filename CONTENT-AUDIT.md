# Content quality audit — question bank

Run 2026-07-30 across all 10,116 questions. Everything here is a **content**
problem, invisible to the test suite because the code is correct — the data isn't.

All of it traces to one root cause: the bank was imported from PDFs/OCR where
sub- and superscript formatting was flattened into spaces or dropped entirely.

---

## ✅ Fixed

| Issue | Count | Status |
|---|---|---|
| Malformed LaTeX (bare `\int`, `frac {}{}`, exponents outside `\( \)`, `\\(`) | 41 questions | fixed, verified against KaTeX |
| Options/explanations rendered without `MathText` | 5 components | fixed |
| Letter **O** used where digit **0** meant | 3 questions | fixed |
| Raw HTML tables rendering as literal tags | 14 questions | fixed via `QuestionText` |

Guarded by `tools/fix_question_latex.py --check`, which runs in CI.

### Raw HTML tables — solved with a renderer, not a data migration

`question_text` in 14 questions (Accounting 12, Chemistry 1, Economics 1) contains
literal `<table><tr><th>…` markup — 486 `<td>`, 246 `<tr>`, 120 `<b>` occurrences.
Nothing rendered HTML, so students saw the raw tags.

Fixed by adding `frontend/src/components/ui/QuestionText.tsx`, which parses that
markup into real React elements and passes everything else through `MathText`.
Chosen over converting the data to `\begin{array}` because:

- KaTeX arrays handle accounting tables badly — currency, long labels, alignment.
- It fixes all 14 at once and any future ones, rather than a one-off migration.
- Admins can paste tables from Admin and have them render.

It deliberately avoids `dangerouslySetInnerHTML`: question text is admin-editable, so
injecting it as HTML would be a stored-XSS hole. Parsing to a fixed element set
(`table/tr/th/td/b`) means the worst a malformed question can do is look wrong.

Verified: all 14 parse into well-formed rows and cells (5–6 rows each), with no HTML
tags left outside the parsed tables. Swapped in at all 7 `question_text` call sites,
with `<p>` wrappers changed to `<div>` since a table inside a paragraph is invalid HTML.

---

## ❌ Outstanding, by priority

### 1. Lost sub/superscripts — ~136 fields

Formatting flattened to spaces. Needs per-question transcription; the `explanation`
field usually disambiguates.

| Subject | Count | Example | Should be |
|---|---|---|---|
| Chemistry | 53 | `Na 2 CO 3`, `H 2 SO 4`, `Ca 2+` | Na₂CO₃, H₂SO₄, Ca²⁺ |
| Mathematics | 42 | `y 3 + 4y 2 + ky - 6` | y³ + 4y² + ky − 6 |
| Physics | 21 | `10m/s 2`, `1 kgm -3`, `kg m 2` | m/s², kg m⁻³, kg m² |
| Accounting/Econ | 19 | mostly false positives (`N 9 900`, `a 2% rise`) | — |

Three distinct sub-variants, which is why this can't be regexed:

- **superscript**: `n 2 - 6n - 4` → `n²  − 6n − 4`
- **subscript**: `I 3` → `I₃` (matrix order), `log 10 4` → `log₁₀ 4`
- **glued**: `1101112 + 101002` → `110111₂ + 10100₂` (number bases)

`MTH-0193` has both in one line: `log₁₀ 4^{1/3}`.

**Chemistry is the most mechanical** (`<element> <digit>` → subscript, `<n>+`/`<n>-`
→ charge superscript) and the most visible, so it's the best place to start.

### 2. Flattened tables — 73 questions

Refer to "the table" with no `\begin{array}`, no `<table>`, and no `image_url`. The
data was pasted as prose, so the question is unanswerable.

Example — `ECO-0494`:
```
X 8 10 12 16 18 20 24 F 2 1 4 3 3 1 6 From the table, Calculate the median
```
That's an X row and an F row. Unreadable as written.

By subject: Chemistry 16, Economics 15, Mathematics 15, Accounting 12, Geography 6,
Literature 4, Physics 4, Commerce 1.

### 3. Smaller items

- **ASCII reaction arrows** — 55 Chemistry questions use `----->`; should be `→`.
  Purely mechanical, safe to bulk-replace.
- **Caret outside LaTeX** — 38 questions, e.g. `(4a + 3) ^2`, `^1/_9`, `\(Wm^-1k\)^-1`.
- **ASCII comparisons** — 10 questions use `<=` / `>=` instead of ≤ / ≥.
- **`l` / `I` as digit 1** — 6 questions in Physics/Biology. Needs checking; several
  are probably legitimate Roman numerals in "I only / II only" style options.

---

## Recommended order

1. **Chemistry subscripts (53)** — highest volume, most mechanical, very visible.
2. **Physics units (21)** — mechanical once a convention is picked.
3. **Maths (42)** — most varied, needs the most judgement.
4. **Flattened tables (73)** — largest and hardest. Now that `QuestionText` renders
   tables, the fix is to convert these into the same `<table>` markup rather than
   inventing a new format. Several may be better replaced with an image, or retired
   if the source table can't be recovered.
5. **Mechanical sweeps** — arrows, `<=`/`>=`, carets.

Each batch needs a production sync afterwards (`sync_questions_db.py`) — the CSV is
the source of truth, but only the sync reaches students.

## Preventing recurrence

`tools/fix_question_latex.py --check` catches malformed LaTeX in CI. It does **not**
yet catch lost sub/superscripts, HTML, or flattened tables, because those need
heuristics with false positives (`N 9 900` is currency, not a superscript). Worth
extending it with a warn-only mode once the backlog is cleared, so new imports get
flagged rather than silently shipping.
