# Acelume gamification — implementation plan

Maps the eight-feature specification onto this codebase. Written 2026-07-30.

**Scope honesty:** the spec describes roughly a quarter's work. The phases below
follow the spec's own recommended order. Phase 0 is built; the rest are specified
against real files so each can be picked up independently.

---

## What already exists (reuse, don't rebuild)

A surprising amount of the foundation is already here:

| Spec concept | Existing implementation |
|---|---|
| Spaced repetition | `QuestionMastery` — per-question Leitner boxes, `next_review_at`, driving `routers/smart_review.py` |
| Achievements | `UserAchievement` + a registry in `app/achievements.py` (9 badges, auto-awarded) |
| Streaks | `User.current_streak` / `longest_streak` / `streak_freezes`, with `record_practice()` already implementing freeze-consumption |
| Daily goal | `User.daily_goal` + the dashboard XP ring |
| The "Learn" stage | `LessonNote` + `NoteProgress` (97 notes) |
| Practice / Master stages | `QuizAttempt` with `mode` (quiz, blitz, mock, diagnostic, marked) |
| Topic analytics | `app/progress.py` `compute_progress()` — per-topic accuracy, weak-topic recommendations |
| Mock exams | `routers/mock.py`, free-navigation with `marked_question_ids` |
| Leaderboard | `routers/leaderboard.py` — overall, per-subject, and (new) Blitz best-score |

**The main gap** the spec exposes is not features — it is that each of those
systems computes progress its own way, with no shared, auditable record of what
a student actually did. That is what Phase 0 fixes.

---

## Phase 0 — Foundation ✅ BUILT

`backend/app/models.py` (four new tables) and `backend/app/gamification/`.

### `LearningEvent` — append-only, idempotent

Every gamification feature reads from one validated event log rather than
recomputing. The critical field is **`event_key`**, a deterministic natural key
(`"QUESTION_ANSWERED:attempt=7:q=42"`) with a **UNIQUE constraint**.

That constraint is the idempotency guarantee, and it is enforced by the database
rather than an application check, because an application check races: two
concurrent requests both SELECT, both find nothing, both INSERT. `record()`
flushes inside a try/except on `IntegrityError` so only one survives.

This is what satisfies the spec's repeated requirement that "replaying or
resubmitting the same event does not duplicate XP" — including offline queues
re-syncing, which is otherwise very hard to get right.

### `XpLedger` — append-only

`User.points` stays as the fast running total, but the ledger is the auditable
record behind it. Without it you cannot answer "was this already rewarded?",
cannot correct a bug retroactively, and cannot investigate a suspicious account.

### `TopicMastery` — per-topic, distinct from `QuestionMastery`

Both are needed and neither replaces the other:

- `QuestionMastery` — "when should this student see **this question** again?"
- `TopicMastery` — "does this student understand **this topic**?"

Holds the seven states, 0–3 stars, `mastery_score`, and the topic-level 3/7/21/45-day
review ladder.

**`mastery_score` can go down; XP cannot.** Keeping them in separate tables is
precisely what stops a student appearing academically strong from accumulated XP —
the spec's stated core requirement.

### `GamificationSetting` — admin-editable thresholds

All ~30 "suggested" values from the spec live in `gamification/config.py` with
documented defaults, overridable per-key from the database. An empty table
behaves exactly like hard-coded constants.

This matters more here than usual: the Android app is a **WebView shell**, so
students may be on an old release for weeks. Tuning a threshold must never
require an app update.

### Wiring ✅ BUILT

`record()` is called from four places, and the legacy `user.points += 10` is gone
from both sites that had it — XP now flows only through the ledger.

| Call site | Events |
|---|---|
| `quiz.py::answer_quiz` | `QUESTION_ANSWERED`, `MISTAKE_CORRECTED` |
| `quiz.py` on attempt finish | `TOPIC_PROFICIENT`, `TOPIC_MASTERED`, `REVIEW_COMPLETED` |
| `mock.py::mock_submit` | `QUESTION_ANSWERED` per question, `MOCK_COMPLETED` once |
| `notes.py::mark_read` | `LESSON_COMPLETED` (first star) |

### The XP-value decision

`xp_correct_answer` is set to **10, not the spec's suggested 2**. The app already
awarded 10 points per correct answer, and `User.daily_goal` (default 50), the
dashboard XP ring and the points leaderboard are all calibrated to it. The spec's
value would silently turn the daily goal from 5 correct answers into 25 for every
existing student. Retuning to the spec's economy is a settings change plus a
`daily_goal` migration — deliberately deferred, not forgotten.

### Rules encoded at the call sites

- **Mixed-topic attempts credit no topic.** A quiz spanning Algebra and Calculus
  is not evidence about either; crediting it would let a student "master" a topic
  they barely touched. Only single-topic attempts fold into `TopicMastery`.
- **Only timed modes can reach three stars.** The spec's Master stage is a timed
  challenge, so Blitz qualifies and ordinary practice does not, however high the
  score. `MASTERY_MODES` / `TIMED_MODES` in `quiz.py` control this.
- **`MISTAKE_CORRECTED` is keyed per question for life** (`MISTAKE_CORRECTED:q={id}`),
  not per attempt — otherwise a student could farm it by deliberately missing.
- **Diagnostic and "marked" modes never grant mastery.** A diagnostic samples every
  subject shallowly; "marked" replays questions the student already flagged.
- **A Smart Review only counts as passed at `practice_pass_pct`.** Clicking through
  a review while getting most of it wrong is not retention.
- **`mastery_score` follows the LATEST attempt, not the best one** — it measures
  current understanding and is allowed to fall. `best_practice_pct` keeps the high
  water mark separately.

---

## Phase 1a — Quest Map backend ✅ BUILT

`SyllabusTopic` (model), `backend/seed_syllabus.py`, `backend/app/routers/quest.py`,
`GET /api/quest/{subject}`.

97 topics across 11 subjects, with a clean 1:1 against the existing lesson notes.

### The sequencing decision

`prerequisite_id` is seeded **sparsely, on purpose**. Chains exist only for
Mathematics, Physics, Chemistry and Biology — subjects with an uncontroversial
teaching order. English, Geography, Economics, Literature, Government, Commerce
and Accounting are seeded flat, with every topic immediately available.

That is deliberate. Inventing a teaching order for a subject that doesn't obviously
have one is worse than admitting it, because **a wrong prerequisite actively blocks
students from content they are ready for**. A topic with no prerequisite is simply
available, so an unsequenced subject degrades to a flat map rather than an
unreachable one. Sequence them from the admin UI once a specialist has ordered them.

### Two rules encoded in the endpoint

- **A started topic is never re-locked.** If a prerequisite becomes unmet — say an
  admin reorders the syllabus — a topic the student has already engaged with stays
  reachable. Removing access to work already begun would be punitive.
- **Every locked topic offers Test Out**, so an experienced student is never
  permanently blocked.

Recommendation order is `review_due` → `practising` → `learning` → `proficient` →
`available`: overdue retention first, because that is what decays.

### Still to build for Phase 1

- Wire the three learning stages so states actually advance (currently states are
  read from `TopicMastery`, but nothing writes proficiency/mastery yet — that comes
  with the `events.record()` call sites).
- The Test Out diagnostic endpoint.
- The Quest Map UI.
- Personal Bests (below).

**Personal Bests** needs a `PersonalBest` table keyed on the spec's comparability
tuple (user, programme, subject, topic, mode, question-count band, difficulty band,
time-limit config). The comparability rule is the whole point: without it, an easier
session overwrites a harder record and the feature actively misleads.

Note the spec's wording requirement — "**+12 percentage points**", not "12%".

## Phase 2 — XP, levels, missions, streaks

Levels: `config.level_for_xp()` and `title_for_level()` are already written.

Streaks: the spec wants **two** (Learning and Mastery). The existing single streak
maps to Learning. Mastery streak needs a new pair of columns on `User` — and those
DO need `_PENDING_COLUMNS` entries in `database.py`, since `User` is already
deployed with real data.

Missions need a `DailyMission` table and generation respecting the spec's rules
(never assign locked topics, avoid three from one subject, 15–30 minutes total).

**Timezone**: `User` has no timezone column today. Streaks and mission resets both
need it, and the spec explicitly requires repeated timezone changes not to mint
extra streak days.

## Phase 3 — Achievements

Extend `app/achievements.py` rather than replacing it. Current badges are
activity-based (`first_quiz`, `century`); the spec wants learning-based
(`Weakness to Strength`, `Comeback Scholar`). Evaluate against `LearningEvent`
rather than ad-hoc queries, and move definitions into a table so admins can add
achievements without a deploy.

## Phase 4 — Weekly leagues

Needs `League`, `LeagueMembership`, `MasteryPointLedger` (weekly-resetting,
separate from XP), and a scheduled weekly close. The `daily-reminders.yml` GitHub
Action is a working pattern for that cron.

Privacy requirements are non-trivial and non-optional: nicknames not real names,
opt-out that does not disable learning features, no schools or locations, no
direct messaging.

## Phase 5–6 — Quiz battles

Asynchronous first. Needs `Battle` / `BattleParticipant`, server-selected question
sets, and answers withheld from the client until submission — which the current
guest-practice endpoint deliberately does *not* do (it ships `correct_option` with
the payload). Battles cannot reuse that pattern.

---

## Cross-cutting requirements worth not forgetting

- **Idempotency** — handled centrally by `event_key`. Do not add reward logic that
  bypasses `events.record()`.
- **Server authority** — the client must never award stars, XP or mastery. All
  thresholds are evaluated server-side.
- **Offline** — queued events replay through the same idempotent path; the SERVER
  timestamp governs streaks and league weeks so a wrong device clock cannot cheat.
- **Accessibility** — every Quest Map state needs an icon or label, not colour
  alone; reduced-motion alternatives for all celebrations.
- **No dark patterns** — the spec rules out purchasable keys, real-money rewards
  and gambling-style randomness. Chest contents must be disclosed or rule-based.
- **Never gate learning** — lessons, explanations and academic content must stay
  unlocked regardless of XP or cosmetics.
- **Feature flags** — leagues and battles ship behind flags.

## Testing

The existing suite is 52 tests. Priorities for this system:

1. Replaying the same `event_key` awards XP exactly once (concurrently, too).
2. XP never decreases on a wrong answer.
3. The daily answer cap bounds farmable XP but not lesson/mastery/mock XP.
4. `mastery_score` can fall while XP holds.
5. A mastered topic becoming review-due does **not** remove stars.
6. `level_for_xp()` agrees with `xp_for_level()` at every boundary.
