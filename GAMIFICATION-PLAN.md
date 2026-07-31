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

### Next step to make Phase 0 live

`record()` is not yet called from anywhere. Wiring it in is deliberately a
separate commit so the schema can land first:

1. `routers/quiz.py::answer_quiz` → `QUESTION_ANSWERED`, plus `MISTAKE_CORRECTED`
   when the question was previously missed (join `QuestionMastery`).
2. `routers/notes.py::mark_read` → `LESSON_COMPLETED`.
3. `routers/mock.py::submit` → `MOCK_COMPLETED`.
4. `routers/smart_review.py` finish → `REVIEW_COMPLETED`.

Suggested keys: `"QUESTION_ANSWERED:attempt={id}:q={qid}"`,
`"LESSON_COMPLETED:{subject}:{topic}"`, `"MOCK_COMPLETED:attempt={id}"`.

---

## Phase 1 — Quest Map and Personal Bests

**Quest Map** needs one thing that does not exist yet: a **syllabus graph**. Topics
currently live only as free-text strings on `Question.topic`. Needs a `SyllabusTopic`
table with `subject`, `topic`, `order`, `prerequisite_topic_id`, `estimated_minutes`,
plus a seed script derived from the existing topic list.

Without prerequisites there is no "locked" state and no Test Out, so this table is
the real Phase 1 blocker — not the UI.

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
