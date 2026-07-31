# Answer keys: how content gets in, and why it is gated

This describes how questions become answered questions in Acelume, and the one
constraint that shapes every part of it.

## The constraint

A wrong answer key is worse than a missing one.

A question with no key teaches nothing. A question with a wrong key teaches
something false, wrapped in a fluent explanation justifying it, to a student who
cannot tell — for them the app *is* the authority. They will memorise it, and
they will carry it into JAMB.

So the pipeline is not built to be right as often as possible. It is built to
**know when it is unsure, and refuse to publish those.**

## The measurement that started this

The 1990–2009 archive arrived with no answer keys at all. Before generating
~7,000 of them, we measured the error rate honestly.

144 of the scraped questions already existed in `data/questions.csv` with
human-entered keys and identical options. 80 were answered blind — the key was
written to a sealed file and only opened after answers were locked.

**Result: 73/80, or 91.2%.** Ungated, that projects to roughly 500–1,100 wrong
keys across the archive.

Of the 7 misses, 4 were self-flagged as uncertain. Three were confident errors —
and at least two of those look like problems in *our existing bank*, not the
model:

| Question | Bank says | Pipeline says |
|---|---|---|
| The Alaafin of Oyo was… | absolute monarch | constitutional monarch |
| Giraffe's long neck illustrates… | natural selection | use and disuse |
| A meeting of the legislature ends with… | adjournment | prorogation |

All three are genuinely arguable. That is the real lesson: **disagreement marks
a question worth a human's attention, not a verdict about who is right.**

## Measured result (gpt-4o, 144 questions)

```
ungated (single pass)  128/144  = 88.9%
accepted by the gate   130/144  = 90.3% coverage
  of those, correct    124/130  = 95.4%
held for review         14
```

**But three of the six "errors" were not errors.** Each was checked by hand:

| | bank says | pipeline says | verdict |
|---|---|---|---|
| *Twelfth Night*, "she bore a mind…" | Olivia | **Viola** | bank is wrong — it is Sebastian describing Viola in 2.1 |
| Partnership profit, expenses include | partners' salaries | **interest on loans** | bank is wrong — salaries are an appropriation, not an expense |
| Asset taken over by a partner | Dr Capital, Cr Realisation | Dr Realisation, Cr Capital | pipeline is wrong |
| Raw materials cost | prime cost | explicit cost | both defensible |
| Argument against multi-party | instability | cost of elections | both defensible |
| Credit union characteristic | ten people, same trade | contribution by ability | both defensible |

So **`ground_truth.csv` is not ground truth.** Its answers came from the same
unaudited bank being checked, and two of 144 are demonstrably wrong — about
1.4%, which projects to **~140 wrong keys among the 10,116 live questions**.
The pipeline's real accuracy is better than 95.4%, because it is being marked
against a flawed answer sheet.

The dominant failure mode is not "model got it wrong" but "question has two
defensible answers". That is a content defect worth fixing on its own.

## The gate

`tools/keying_core.py` answers every question twice:

- **Pass A** — cold, letter only, no reasoning. It cannot talk itself into a position.
- **Pass B** — independent, reasoning required, and the **options shuffled and relabelled**.
- **Publish only if both passes name the same option _text_.**

The shuffle is the load-bearing part. Asking the same model the same question
twice produces correlated errors and tells you almost nothing. Changing which
letter carries which option breaks position bias, so the two passes fail in
different ways and a disagreement becomes real evidence of difficulty.

Mapping the shuffled letter back to the original is the only code here that can
be wrong *systematically* — an off-by-one would produce a whole bank of
confidently wrong keys that each look fine. It is pure, and exhaustively tested
over all 24 permutations in `backend/tests/test_keying_core.py`.

## Running it

```powershell
$env:OPENAI_API_KEY = 'sk-...'

# 1. Clean the archive. Produces questions with NO keys.
python tools/clean_jamb_archive.py --zip jamb_questions_1990_to_2009.zip --apply

# 2. Measure YOUR model before spending anything. Non-negotiable.
python tools/answer_keys.py --validate data/staging/ground_truth.csv --model gpt-4o

# 3. Small batch first, then the rest. Resumable — interrupt freely.
python tools/answer_keys.py --in data/staging/jamb_archive_unkeyed.csv --limit 100
python tools/answer_keys.py --in data/staging/jamb_archive_unkeyed.csv --apply

# 4. Merge. Lands as drafts unless you pass --publish.
python tools/merge_keyed_questions.py --in data/staging/jamb_archive_keyed.csv --apply

# 5. Push to production via the sync-questions GitHub Action (dry_run: false).
```

Step 2 is the one people skip. The 91% figure is not a property of the pipeline,
it is a property of *the model you point at it* — a small/cheap model scores far
below it, and no gate rescues a model that is confidently wrong. `--validate`
reports both the ungated accuracy and the accuracy of what the gate would
actually publish, on questions whose answers are already known.

Checkpoints are namespaced by model (`.progress.gpt-4o.jsonl`). Without that,
switching models mid-run would resume from the old model's answers and report
them as the new one's.

## Working through it, one subject-year at a time

17,045 questions in one run is a bad idea for reasons unrelated to cost: you
cannot inspect the result, a weak model poisons everything before you notice,
and there is no natural place to stop and look. `tools/batch_queue.py` splits
the work into **276 batches** of median ~45 questions, newest year first.

```powershell
python tools/batch_queue.py --build      # 276 batches, 17,045 questions
python tools/batch_queue.py --status     # progress
python tools/batch_queue.py --next       # what is up next
python tools/batch_queue.py --next --run --apply
python tools/batch_queue.py --batch key-2001-Biology --run
```

Two kinds of batch, because the bank has two different problems:

| kind | what it is | tool |
|---|---|---|
| `audit` | 10,111 live questions whose keys were never checked | `audit_keys.py` |
| `key` | 6,934 archive questions with no key at all | `answer_keys.py` |

The queue starts at `audit-2025-Mathematics`, then works through 2025's other
subjects in the app's canonical order, then 2024, and so on back to 2010 —
then the archive, 2001 back to 1990. Undated batches come last.

Each batch writes its own CSV and its own checkpoint. A batch is only marked
done when it completes with `--apply`.

### Note on ordering

There is no **Mathematics 2009**. The archive contains no Mathematics, Physics
or Chemistry at all — it is the eight humanities and commercial subjects — and
the live bank starts at 2010. The two datasets do not overlap in year, so the
queue runs 2025→2010 (audit) and then 2001→1990 (key). 3,855 archive questions
came from decade-spanning aggregate files and carry no year; those are grouped
into undated batches rather than guessed at.

## Figure-dependent questions

574 questions reference a diagram that was never scraped. Rather than discard
them, `tools/replace_figure_questions.py` writes a fresh question testing the
same concept in words.

The safeguard matters more than the generator. A model that invents both a
question and its answer cannot mark its own homework — it has no way to notice
that its question is ambiguous or that its "correct" option is wrong. So every
generated question is handed to the **same independent two-pass solver**, which
never sees the intended answer. If the solver cannot recover it, the question is
discarded. Only questions a fresh reader independently agrees on survive.

Replacements are written with `source: original` and tagged
`figure-replacement|generated|solver-verified`. They are **not** past questions,
and a student is entitled to know the difference.

## Auditing keys already live

```powershell
python tools/audit_keys.py --limit 300              # sample
python tools/audit_keys.py --subject Government --apply
```

Two rules make the result mean anything:

1. **Blind.** The model never sees the stored key *or the stored explanation* —
   which usually states the answer outright. Show it either and it will agree
   with whatever is there, and the audit measures nothing.
2. **Never auto-overwrite.** It writes a review CSV with a blank `verdict`
   column and stops. Our key is not automatically better than theirs.

## Current state

| | |
|---|---|
| Cleaned, unkeyed, ready | **6,934** (`data/staging/jamb_archive_unkeyed.csv`) |
| Held back — need diagrams | 574 (`jamb_archive_needs_figure.csv`) |
| Ground-truth validation set | 144 (`ground_truth.csv`) |
| Already in the bank | 10,116, keys never audited |

The archive covers English, Literature, Government, Economics, Biology,
Geography, Commerce and Accounting for 1990–2009 — years the bank currently has
**zero** coverage of. It contains no Mathematics, Physics or Chemistry, which is
where the bank is thinnest.

## What is still a human's job

- The 574 figure-dependent questions. Nobody can answer these without the diagram.
- Every disagreement in `jamb_archive_needs_review.csv`.
- Every row in `key_audit_disagreements.csv`.
- Deciding when a draft becomes `active`. Nothing here does that for you.
