# While you slept — 1 August 2026

## Final continuation: archive keying complete and approved set published

The last **15 archive batches / 3,052 questions** went through the same measured
three-way gate: a blind direct solve, a separate elimination pass that could
not see the first answer, and the supplied solved archive as evidence rather
than authority. **2,247 passed all three signals; 805 remain held.** Thirteen of
the accepted rows duplicated normalized question text already in the bank, so
the net addition from these batches was **2,234**.

The earlier **234-question review pile was also adjudicated row by row**. A
question was recovered only when the reviewer could defend one option
independently; missing passages, broken options, and genuine ambiguity stayed
held. The result was **173 approved and 61 still held**. All 25 known
missing-passage English questions remained held.

Together, those steps moved the bank from 13,520 to **15,927 unique rows**.
The approved production set is **3,553 questions**:

- 3,380 accepted by the measured three-way gate (1,146 from the prior
  continuation plus 2,234 new, after duplicate guards);
- 173 recovered by explicit adjudication;
- 866 unresolved rows remain outside the published set (61 from the original
  review pile and 805 from the final batches).

The production importer requires a non-empty topic. The archive supplied none,
so a calibrated topic step was added rather than silently losing every row at
sync time. It uses two different text classifiers and assigns an existing
canonical topic only when both agree with validated margins; uncertain rows
receive the truthful broad label `General Past Questions`. On deterministic
held-out validation, precision among specifically classified rows ranged from
90.0% to 100% by subject. Across the 5,811 archive rows in the bank, 2,686 got
a canonical topic and 3,125 got the broad fallback.

### Admin spot-check and corrections

A deterministic 24-question sample covered all eight archive subjects and
included prior-gate, final-gate, and adjudicated rows. All 24 rendered in the
real Admin question table as drafts. Eight were opened in the edit form for a
deep check of question text, four options, selected answer, explanation,
topic, source, and status; all eight passed. The sample caught four presentation
defects before promotion:

- `ACC-J00372`: converted a flattened balance sheet into supported safe table
  markup and clarified the goodwill explanation;
- `BIO-J00468`: corrected “Hermophroditic” to “Hermaphroditic”;
- `COM-J00367`: corrected “Which oft these” and “Enterpreneuer”;
- `ENG-J01331`: capitalized the name Agbo.

The final LaTeX gate then caught three more archive rows with raw `frac{...}`
markup (`ACC-J00617`, `ECO-J00673`, `ECO-J00706`); their fractions now use the
app's supported `\( ... \)` delimiters.

The local Admin rehearsal also exposed a fresh-database sync bug unrelated to
the content: SQLite received an empty executemany update after successful
inserts, raised for missing bind parameters, and rolled the transaction back.
`sync_questions_db.py` now skips that empty update; a regression test proves a
fresh SQLite database commits its first question import.

### Final verification before production sync

- **15,927 rows / 15,927 unique IDs**
- **13,470 active, 2,457 draft**
- **3,553 approved archive questions active**, with zero invalid keys, blank
  selected options, blank explanations, blank topics, or missing passages
- no active question depends on a missing passage; the 192 legacy orphaned
  comprehension questions remain quarantined as drafts
- `fix_question_latex.py --check`: clean across all 15,927 rows
- full sync dry run: 15,927 prepared, **0 skipped**
- backend: **210 tests passed**
- frontend: `tsc -b` passed with no output
- manifest: **92/275 batches**, 6,982/16,826 questions (41.5%); archive keying
  is now **91/91 complete**

There are 825 older active questions with blank explanations. None belongs to
this 3,553-question approved archive set; that pre-existing debt is recorded
separately rather than hidden inside this continuation's clean result.

## Continuation: 1,146 more questions, gated three ways

The supplied solved archive was useful, but not trustworthy enough to import
directly. It matched all 144 questions in the existing validation set and got
only **121/144 (84.0%)** of their stored keys. It also disagreed with the
earlier hand-keyed archive work on 381 of 2,297 exact matches. I therefore used
it only as one independent signal, never as an answer authority.

I processed **1,385 questions across 17 batches** with three genuinely
different routes:

1. one agent solved each question directly;
2. a different agent eliminated the wrong options, without seeing the first
   answer or the solved archive; and
3. the supplied archive contributed its source key.

Only three-way agreements were keyed. A blind run of this exact arrangement on
the 144-question validation set measured:

| method | accepted/scored | correct | accuracy |
|---|---:|---:|---:|
| direct agent pass | 143 | 136 | 95.1% |
| independent elimination pass | 139 | 135 | 97.1% |
| direct + archive agreement | 122 | 118 | 96.7% |
| **all three agree** | **119** | **117** | **98.3%** |

The two recorded three-way “errors” are `GOV-0483` (whether the Alaafin was an
absolute or constitutional monarch) and `ACC-0470` (partnership expenses).
Both are already documented in this repository as likely defects in the old
validation keys, so 98.3% is the conservative measured figure.

The gate accepted **1,151**, held **234** for review, and identified 25 of the
held English questions as unanswerable because their passages are missing.
Five accepted rows duplicated normalized question text already in the bank and
were skipped by the merge guard. The bank therefore grew by **1,146**, from
12,374 to **13,520**. Every added row is still `draft`; nothing was published or
synced to production.

| batch | keyed | review | missing passage/data |
|---|---:|---:|---:|
| key-1992-Government | 39 | 2 | 0 |
| key-1991-Biology | 37 | 2 | 0 |
| key-1991-Geography | 31 | 9 | 0 |
| key-1991-Economics | 37 | 4 | 0 |
| key-1991-Literature | 39 | 11 | 0 |
| key-1991-Government | 38 | 1 | 0 |
| key-1990-English | 78 | 3 | 25 |
| key-1990-Biology | 35 | 4 | 0 |
| key-1990-Geography | 29 | 7 | 0 |
| key-1990-Economics | 40 | 3 | 0 |
| key-1990-Literature | 35 | 14 | 0 |
| key-1990-Government | 53 | 6 | 0 |
| key-undated-Biology-1 | 241 | 9 | 0 |
| key-undated-Biology-2 | 33 | 1 | 0 |
| key-undated-Geography-1 | 168 | 82 | 0 |
| key-undated-Geography-2 | 13 | 6 | 0 |
| key-undated-Economics-1 | 205 | 45 | 0 |
| **total** | **1,151** | **209** | **25** |

The five duplicate-text skips were `BIO-J00070`, `GEO-J00552`, `ECO-J00620`,
`ECO-J00621`, and `ECO-J00651`. Actual additions by subject were Biology 345,
Economics 279, Geography 240, Government 130, Literature 74, and English 78.

### Integrity repairs made before adding more content

The earlier hand-keyed outputs used a reduced 10-column CSV instead of the
bank's 19-column schema. The old merge tool accepted them and silently blanked
`exam_type`, difficulty, tags, source, and other metadata on **1,639 already
merged rows**. Those fields were restored deterministically by question ID from
`jamb_archive_unkeyed.csv`; the hand-written key, explanation, and draft status
were preserved. A dry check now finds zero repairable metadata gaps.

The two causes are closed:

- `merge_keyed_questions.py` now rejects reduced schemas, rejects keys pointing
  at an empty option, and writes a complete temporary CSV before atomically
  replacing the bank;
- `batch_queue.py` now gives `answer_keys.py` explicit per-batch output paths,
  so a batch input cannot overwrite itself, and manifest writes are atomic.

Five active legacy rows had `correct_option=E` even though the bank and UI have
only A–D; their fifth option had been flattened into option D. `GOV-0203`,
`MTH-0275`, `PHY-0138`, `PHY-0174`, and `PHY-0196` are now drafts rather than
impossible live questions. The LaTeX gate also caught and fixed all four
malformed fraction options on `ECO-J00672` before merge.

### Current verified state

- **13,520** rows, 13,520 unique question IDs
- 9,917 active and 3,603 draft
- 1,146 new three-way-gated rows have full metadata, valid A–D keys, non-empty
  selected options, and non-empty explanations
- zero active questions use an invalid key
- zero active questions depend on a missing passage
- `fix_question_latex.py --check`: clean across all 13,520 rows
- metadata repair dry run: zero gaps
- backend: **206 tests passed**
- frontend: `tsc -b` passed with no output
- manifest: **77/275 batches**, 3,930/16,826 questions (23.4%); archive keying
  is 76/91 batches, with 15 batches / 3,052 questions remaining

Across the whole day, the bank moved **10,116 → 13,520**, a net gain of 3,404
draft questions with answers and explanations.

## Earlier rounds before this continuation

Hand-keyed sixty subject-year batches from the 1990–2009 archive. **2,258 new
questions are now in `data/questions.csv`**, every one with an answer and a
written explanation. The bank went from 10,116 to 12,374.

This round asked for 24 batches in parallel (1995's remaining four subjects,
then all of 1994, 1993, 1992, and three 1991 subjects). 20 ran; the last 4
(1992-Government, 1991-Biology/Geography/Economics) hit two different
platform limits in sequence — first the 20-concurrent-subagent cap, then,
on retry, the session's own API rate limit, which resets 7:10am UK time.
Those 4 are still queued and pending — nothing lost, just not done yet.

The 20 that did run were merged one at a time with a row-count check after
every single merge, the discipline adopted after the earlier truncation
incident. It held: no corruption this time. One row was caught and silently
skipped by the merge tool's own duplicate-question-text guard somewhere in
the 20 — the bank grew by 775 rather than the 776 the batches reported
producing. That's the guard working as intended (the same question text
apparently appears in two different year archives), not a bug, but it means
the by-subject subtotals below are approximate to within one question.

The LaTeX checker caught two more malformed-fraction questions this round
(ECO-J00128 and, from the previous round, ECO-J00252) — same
missing-backslash pattern as before, both fixed by hand before merging
further. Worth checking whether whatever wrote these Economics
formula-options across multiple agents has a systematic habit of forgetting
the backslash.

**A second round of 11 parallel batches ran into a real data-integrity
incident, caught and fixed before anything was lost.** Merging 11 batches
sequentially in one shell command overran the command's timeout partway
through the 8th merge, which killed the write mid-file and left
`data/questions.csv` truncated — an invalid CSV missing thousands of rows,
including the ~2,000 pre-existing questions past whatever point the writer
had reached. Caught immediately by re-checking the row count after the batch
(9,070 lines where ~11,600 were expected) rather than assuming the loop
finished cleanly. `merge_keyed_questions.py` writes a `.bak` of the prior
state before every overwrite, so the fix was to restore from that backup
(which held the correct state after the first 7 of the 11 merges) and redo
the remaining 4 merges one at a time instead of in a batch, verifying the row
count after each one. Final count matches the expected sum exactly. Nothing
was lost, but it's a reminder that merges into the live bank should run one
at a time with a verified count after each — not chained in a loop where one
slow write can silently corrupt everything after it.

The last 14 batches ran as parallel subagents rather than one at a time: three
in one round (Government, Commerce, Literature), then eleven more in a second
round (2000-Literature, 2000/1999/1998-Accounting, 1998-Biology/Geography/
Economics/Literature/Government/Commerce, 1997-Biology). Each agent worked
from the same written methodology and only produced its three output CSVs —
merging into `data/questions.csv` and updating the manifest was deliberately
kept as a separate, sequential step done by me afterward, specifically so 11
agents writing at once couldn't clobber each other's changes to the same two
shared files.

**That separation caught a real bug before it reached the bank.** All 8
agents in the second round wrote `correct_option` as lowercase (`a`/`b`/`c`/`d`)
instead of the uppercase `A`/`B`/`C`/`D` the merge script requires — so the
first merge attempt silently skipped 351 fully-answered questions as "no
answer key" rather than adding them wrong. Caught by checking the merge
script's own output counts against what each agent reported, not by trusting
either side. Fixed by uppercasing the column and re-running; nothing reached
`data/questions.csv` with a bad key.

| batch | keyed | held for review | unanswerable |
|---|---|---|---|
| key-2001-English | 59 | 8 | 24 |
| key-2001-Biology | 36 | 3 | — |
| key-2001-Geography | 26 | 3 | — |
| key-2001-Economics | 43 | 2 | — |
| key-2001-Government | 35 | 3 | — |
| key-2001-Commerce | 31 | 7 | 4 |
| key-2000-Biology | 37 | 1 | — |
| key-2000-Geography | 36 | 3 | — |
| key-2000-Economics | 35 | 2 | — |
| key-2000-Government | 32 | 3 | — |
| key-2000-Commerce | 25 | 10 | 1 |
| key-1999-Biology | 35 | 2 | 2 |
| key-1999-Geography | 26 | 4 | — |
| key-1999-Economics | 33 | 8 | — |
| key-1999-Government | 45 | 1 | 1 |
| key-1999-Commerce | 43 | 2 | 1 |
| key-1999-Literature | 42 | 2 | — |
| key-2000-Literature | 37 | 8 | 2 |
| key-2000-Accounting | 43 | 1 | 4 |
| key-1999-Accounting | 40 | 3 | 1 |
| key-1998-Biology | 41 | 0 | 0 |
| key-1998-Geography | 40 | 2 | 0 |
| key-1998-Economics | 36 | 1 | 1 |
| key-1998-Literature | 29 | 12 | 0 |
| key-1998-Government | 43 | 0 | 1 |
| key-1998-Commerce | 39 | 3 | 1 |
| key-1998-Accounting | 47 | 1 | 0 |
| key-1997-Biology | 36 | 0 | 0 |
| key-2001-Literature | 42 | 6 | 0 |
| key-2001-Accounting | 39 | 1 | 3 |
| key-1997-Geography | 36 | 1 | 0 |
| key-1997-Economics | 38 | 3 | 0 |
| key-1997-Literature | 37 | 13 | 0 |
| key-1997-Government | 39 | 0 | 0 |
| key-1997-Commerce | 45 | 1 | 0 |
| key-1997-Accounting | 40 | 2 | 0 |
| key-1995-Biology | 40 | 1 | 0 |
| key-1995-Geography | 36 | 0 | 0 |
| key-1995-Economics | 41 | 0 | 1 |
| key-1995-Literature | 32 | 18 | 0 |
| key-1995-Government | 44 | 2 | 0 |
| key-1995-Commerce | 37 | 7 | 0 |
| key-1995-Accounting | 37 | 2 | 1 |
| key-1994-Biology | 36 | 2 | 0 |
| key-1994-Geography | 38 | 0 | 0 |
| key-1994-Economics | 39 | 1 | 2 |
| key-1994-Literature | 39 | 8 | 1 |
| key-1994-Government | 47 | 3 | 0 |
| key-1994-Commerce | 39 | 2 | 0 |
| key-1994-Accounting | 30 | 0 | 0 |
| key-1993-Biology | 35 | 0 | 0 |
| key-1993-Geography | 34 | 1 | 0 |
| key-1993-Economics | 38 | 2 | 0 |
| key-1993-Literature | 43 | 4 | 3 |
| key-1993-Government | 42 | 1 | 0 |
| key-1992-Biology | 37 | 2 | 0 |
| key-1992-Geography | 40 | 2 | 0 |
| key-1992-Economics | 42 | 2 | 0 |
| key-1992-Literature | 47 | 1 | 0 |
| **total** | **2,258** | **211** | **58** |

By subject (approximate to within one question — see the duplicate-guard note
above): Literature 348, Government 327, Economics 345, Biology 333,
Geography 312, Accounting 276, Commerce 259, English 59.

**Still pending from this round** (queued, not lost — hit the session's rate
limit, not a content problem): `key-1992-Government` (41), `key-1991-Biology`
(39), `key-1991-Geography` (40), `key-1991-Economics` (41). Run these four
next, the same way as everything else.

### The review rate is a quality signal

Most batches send 2–4 questions to review. Three did far worse, and the reason
is the questions rather than the answering:

- **2000 Commerce: 10 of 36.** Near-duplicate options ("inadequate
  transportation network" against "lack of good transportation network"), and a
  fire-insurance question asking you to apply the average clause with no loss
  figure given.
- **1999 Economics: 8 of 41.** Several stems truncated mid-sentence, and one
  question on national income at factor cost whose four options are all about
  price bases, which is a different concept entirely.
- **2001 Commerce: 7 of 38.** Same pattern.

Treat old Commerce and Accounting years as suspect. The pipeline will key many
of these confidently, because both its passes will settle on the same
plausible-looking option — agreement does not detect a broken question.

**A different kind of high review rate showed up in Literature, and it's not
a content defect.** 2000-Literature held back 8 of 45, and 1998-Literature held
back 12 of 41 — both because a real fraction of questions name a set text
(Stillborn, She Stoops to Conquer, the poetry anthology) without quoting the
specific line needed, and the answering agent was honest about not being able
to verify the detail rather than guessing. 1999-Literature, by contrast, was
fully self-contained (every quote needed was inline) and held back only 2 of
44. So "self-contained vs. set-text-dependent" varies by year even within the
same subject — worth checking case by case rather than assuming.

**One more LaTeX bug, this time in a generated explanation:** ECO-J00252
(1995 Economics, a profit-formula question) had two options written as
malformed math — `(frac{text{(TFC + TVC)}}{Q})` instead of proper
`\(\frac{\text{TFC} + \text{TVC}}{Q}\)` — which would have rendered as raw
source to a student instead of a formatted fraction. Caught by the same
`fix_question_latex.py --check` that gates CI, not by reading every option by
eye. Fixed by hand before merging further.

**One corrupted question found:** 1999 Biology Q36 asks what epiphytes compete
for and offers "cabinet minister" as an option. The correct answer is still
determinable, so it was keyed, but that option is nonsense and should be fixed.

**A second corruption, this time genuinely unanswerable:** 1999 Government
asks which states the UPN won in the 1979 election, but all four option lists
are internally inconsistent with each other and with the historical record
(one substitutes Imo for Ondo, another adds Kwara, which UPN never won). Left
unkeyed rather than guessed. The same batch also held back a "rates are
collected by..." question where the scraped option text itself looks
OCR-corrupted ("the department councils") — answered by elimination, but
flagged for a sanity check against the original paper.

I answered these myself rather than running the gpt-4o pipeline. That is not
obviously more accurate — I scored 91.2% on the blind test against the
pipeline's 95.4% on what it published — but it lets me say "this question is
ambiguous" instead of confidently picking one of two defensible answers, which
was the failure mode in three of the pipeline's six errors. The 59 held back
are exactly those cases.

**Everything is `status: draft`.** No student sees any of it until you publish.

## What is waiting for you

**1. Nothing has been committed.** I cannot run git safely from here — your
working tree currently shows ~186 files as modified, almost all of it a
line-ending artefact of editing across Windows and this Linux sandbox, and
there's an active `.git/index.lock`, which means something else (your own
git client or editor) may have a git operation open right now. Committing
blind on top of that risks mixing in changes neither of us intended. Check
`git status` yourself, resolve the lock, and commit when you're back at the
keyboard:

```powershell
git add -A
git commit -m "Hand-key 2,258 archive questions for 1991-2001 across eight subjects"
git push origin main
```

**2. The Aug 4 gate is in three days** and has not moved. Production access
application, then the Android rebuild against acelume.ng, then confirm testers
received it. This is the only item with an external deadline.

**3. The sync-questions Action still has not run.** The 194 quarantined
questions are quarantined only on your laptop. A student practising English on
acelume.ng right now is still being asked about Mr Bepo.

## What I deferred, and why

**Accounting 2001 (43 questions).** Roughly a third are multi-part questions
whose figures are cut off mid-sentence — `Given: Fixed assets ₦85,600 Sales
₦197,000 ... Share ` and then nothing. Accounting is also the subject I scored
worst on in the blind test (77.8% even after gating). Guessing at truncated
balance-sheet questions in the subject I am weakest at is how wrong keys get
made, so I stopped rather than pushed through.

**Literature 2001 (48 questions).** Depends on specific set texts. Worth
checking whether each question quotes enough of the text to stand alone before
anyone answers them.

## Things worth knowing

**The archive has the same orphan disease as your live bank.** 31 of the
questions I looked at refer to material that is not in the record — "deduced
from the passage" with no passage, "the trade discount receivable by Mr Bacus"
with no figures, "which of these companies" with no list. They are written to
`*_needs_data.csv` and `*_needs_passage.csv` rather than merged. Expect this
throughout the remaining 76 key batches.

**Some questions are broken in ways no tool will catch.** Commerce Q39 offers
"staff performing the same functions are grouped" and "staff performing similar
functions are grouped" as separate options. Commerce Q29 offers "capital gain"
and "capital appreciation". Those are the same answer written twice, and no
student can choose correctly. Both are in the review pile.

**The review files are where a Nigerian teacher would beat me.** `in ... to his
age` — regard or consideration? Is the Alaafin absolute or constitutional? Does
"fall back on" or "resort to" fit the generator better? These are judgement
calls about what JAMB's examiners intended, and local knowledge decides them.

## Verification

- 48 keying, pipeline and orphan-detection tests pass
- `tools/fix_question_latex.py --check` clean across all 12,374 questions
  (after fixing two malformed-LaTeX Economics questions the check caught,
  one this round and one the round before)
- every draft row has a key naming a real, non-empty option — checked, 0 failures
- every draft row has an explanation, except the 192 pre-existing quarantined
  comprehension questions, which are supposed to be empty until someone
  supplies the missing passage
- no active question depends on a missing passage
- every merge this round was checked one at a time — row count read back and
  compared to the expected running total after each individual merge, not
  just after the whole batch — following the discipline adopted after the
  earlier truncation incident; it held with zero surprises
- the lowercase-`correct_option` bug from the first parallel round did not
  recur once the instruction was made explicit in every prompt

## Where the queue stood before this continuation

60 of 275 batches done, 2,545 of 16,826 questions. Next in order is
`audit-2025-English` (65), then the rest of the 2025 audits. 32 archive keying
batches remain (4,437 questions): the 4 still-pending 1991 batches from this
round, then 1991-Literature/Government, then 1990 (including a large 106-
question English batch), then the undated aggregate files, which are the
biggest remaining chunk (several 250-question English/Biology/Geography/
Economics/Literature/Government/Commerce/Accounting batches). 1996 has no
archive coverage at all (confirmed by checking the manifest, not assumed).
Run the next ones directly by name if you want more new content first:

```powershell
python tools/batch_queue.py --batch key-2000-Commerce --run --apply
```

Nothing is deliberately skipped anymore. `key-2001-Literature` and
`key-2001-Accounting` — the last two batches held back on the strength of an
original concern rather than an actual attempt — got done this round like
everything else: 2001-Literature turned out mostly self-contained (6 of 48
held back for genuine set-text uncertainty), 2001-Accounting held back 4 of
43 for missing/truncated figures, same pattern as every other Accounting year.
Every English batch after 2001 is still simply not yet reached in queue order
(not deferred, just not up yet).

## Earlier estimate for the then-remaining 4,437

This session ran as many as 24 batches in parallel in a single turn — each
subagent hand-keys its own batch and writes its own output CSVs, merging into
the shared bank happens afterward, one batch at a time, specifically so
parallel writers can't collide on the same file. In practice the platform
capped concurrency at 20 subagents at once, and the account's own API rate
limit is a second ceiling on top of that — both were hit this round. That's
roughly the limit of how fast hand-keying can go without changing how
carefully any one question gets read. Even so, the remaining 32 batches would
take at least another session or two, which is not a sensible way to spend
them. The pipeline exists for exactly this, and you have already measured it:
**95.4% correct on what it publishes**, with the rest held for review.

```powershell
$env:OPENAI_API_KEY = 'sk-...'
python tools/batch_queue.py --all --kind key --run --apply
```

That works through all 76 remaining keying batches in one command, resumable,
stopping at the first failure rather than repeating it 76 times. Cost is on the
order of twenty dollars. Then merge and review:

```powershell
Get-ChildItem data/staging/batches/*_keyed.csv | ForEach-Object {
    python tools/merge_keyed_questions.py --in $_.FullName --apply
}
```

Worth reserving hand-keying for where it actually beats the pipeline: subjects
with contested answers, and the review piles the pipeline hands back.

## A note on how this actually works

I answer within a turn, not continuously over hours. Fifteen batches is what fit
across these sessions, not a rate per hour. To keep going, just say continue — each turn
picks up from the manifest, so nothing is repeated or lost.
