# Acelume — Gamification Roadmap

Status: partly BUILT as of 2026-08-07. Companion document: `PRODUCT-ARCHITECTURE.md`.

| § | Feature | State |
|---|---|---|
| 1 | `answer_seconds` on `UserResponse` | **Built** |
| 2 | Subject Rating (Glicko-2, shown as predicted score) | **Built** — `app/rating.py`, `app/rating_service.py` |
| 3 | Bot opponents | **Built** — `app/bots.py` |
| 4 | Answer-quality labels + accuracy | **Built** — `app/answer_labels.py` |
| 5 | Daily Question | **Built** — `app/routers/daily_question.py` |
| 6 | Rush mode | **Built** — `app/routers/rush.py` |
| 7 | School clubs | **Built** — `app/schools.py` |
| 8 | Arenas | **Deliberately not built** — see below |
| 9 | Insights as sentences | **Built** — `app/insights.py` |
| 10 | Fair play | **Built** — `app/fair_play.py` |

**Arenas (§8) are the one thing deliberately left unbuilt.** They are cheap —
the same points machinery on a different clock — but §8 gates them on roughly
200 concurrent users, and below that an arena leaderboard reads as empty and
does active harm. Building it now would mean shipping a feature designed to
look popular, at a moment when it cannot. Revisit when the concurrency is
there; the note in §8 is the trigger.

The sections below are kept as written, because the reasoning is why each
thing was built the way it was. Where the implementation departs from the
proposal, the code comments say so.

Chess.com is the right thing to learn from. It has kept tens of millions of people
doing a hard, frequently humiliating cognitive task, daily, for years — which is
structurally the same problem as getting a 17-year-old to do Mathematics past questions
every evening for eight months.

But most of what's visible on chess.com is decoration. The load-bearing parts are few,
and Acelume is missing exactly one of them.

---

## 1. What's already built — and the one field that's missing

Verified in the codebase, so nothing below gets re-specced:

| System | State | Where |
|---|---|---|
| XP + levels | Live. Monotonic ledger, configurable curve. | `XpLedger`, `gamification/config.py` |
| Mastery score | Live. 0–100 per topic, **falls** with decay. | `TopicMastery.mastery_score` |
| Mastery Points | Live. Weekly reset, drives leagues. | `MasteryPointLedger` |
| Weekly leagues | Live. 6 tiers, cohorts of 20, top 5 up / bottom demoted, opt-out. | `gamification/leagues.py` |
| Two streaks | Live. Learning streak + Mastery streak, freezes capped at 3, student-local midnight. | `User`, `gamification/events.py` |
| Daily missions | Live. 3/day. | `DailyMission`, `gamification/missions.py` |
| Personal bests | Live. | `PersonalBest`, `gamification/personal_best.py` |
| Achievements | Live. | `UserAchievement`, `routers/achievements.py` |
| Quest map | Live. 7-state topic progression. | `routers/quest.py`, `QuestMap.tsx` |
| Battles | Live. Async + live (30s/question, shared server clock). | `routers/battles.py` |
| Blitz | Live. 180s sprint, ≤60 questions, single subject. | `routers/blitz.py` |
| Spaced review | Live. Leitner per question + per topic. | `QuestionMastery`, `smart_review.py` |

**The three-way separation of XP / mastery / league points is already correct** and is
the thing most exam apps get wrong. Chess.com has the same discipline: rating measures
skill and can fall; everything else is participation.

### One missing column blocks a third of this document

`UserResponse` stores `selected_option`, `is_correct` and `timestamp` — but **not how
long the answer took.** The only per-answer timing anywhere in the schema is
`BattleParticipant.correct_seconds`, which covers battles only.

That single omission blocks: the *Lucky* and *Blunder* labels (§4), the pacing and
speed insights (§9), and the fair-play floor (§10). It is a one-column migration:

```python
# UserResponse
answer_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Client sends it; server clamps to a sane range (0–600) so a backgrounded tab doesn't
record a 4-hour answer. Nullable, so existing rows and any flow that doesn't send it
stay valid.

Differencing consecutive `timestamp` values within an attempt is *not* an adequate
substitute — it breaks on pauses, backgrounding, and the mock exam's free navigation.
**Do this first.** It is an hour of work, it is the prerequisite for several items
below, and every day it isn't shipped is a day of timing data you can't recover.

---

## 2. The gap: Acelume has no number that answers "how good am I?"

This is the whole finding. Take the four numbers a student currently sees:

| Number | Problem as a self-assessment |
|---|---|
| **XP** | Only ever goes up. Measures attendance. |
| **Level** | Derived from XP. Same problem. |
| **Mastery %** | Per-topic and absolute. Answers "did I pass this topic," not "am I good at Mathematics." |
| **League tier** | Measures *this week's effort* vs 19 arbitrary strangers. Resets. |

None of them answers the question the student actually has, which is *"if JAMB were
tomorrow, what would I score?"* — and none of them can be compared to anyone else in
a way that means something.

Chess.com's entire engagement loop hangs off one primitive that does both: **rating.**
It goes up and down, it's calibrated against opposition, and it's a single honest
number. Every other feature is plumbed into it — matchmaking, puzzle difficulty,
leaderboards, bots, insights. Acelume has all those features and no rating to plug
them into, which is why several of them work worse than they should.

### The build: Subject Rating

Implement **Glicko-2** (better than Elo for players with irregular activity, which is
every student) per `(user_id, path_id, subject)`.

```python
class SubjectRating(Base):
    __tablename__ = "subject_rating"
    user_id, path_id, subject           # composite unique
    rating: float                       # μ, start 1200
    deviation: float                    # RD, start 350 — uncertainty
    volatility: float                   # σ, start 0.06
    peak_rating: int
    updated_at
```

**Questions are the opponent.** Each question carries its own rating, derived from real
performance data you already collect in `UserResponse` — % of students who get it right,
inverted. A question answered correctly by 30% of students is "rated" higher than one
answered correctly by 90%. Answering it correctly moves the student's rating up more.

Seed unrated questions from the existing `difficulty` field (easy 1000 / medium 1200 /
hard 1450) and let real responses replace the estimate. You already have thousands of
responses to bootstrap from.

### Frame it as predicted score, not as a rating

**This is the critical design decision.** A raw rating labelled "1180" is meaningless
to a JAMB candidate and quietly demoralising to a weak one. But you already compute
`score_estimate` in `progress.py`. Make that the visible surface of the rating:

```
Mathematics          Predicted  62/100   ▲ 4 this week
```

Same mathematics underneath, mapped to the scale the student already cares about. This
gets you all the machinery benefits with none of the "I'm a 900 and my friend is a
1400" damage. Keep the raw rating internal.

### What rating unlocks immediately

| Feature | Today | With rating |
|---|---|---|
| Question selection | `random.sample()` from a difficulty pool | Serve at rating +50 to +150 — the band where learning happens |
| Battle matchmaking | Share a code with a friend | Match strangers of comparable strength |
| League seeding | Tier carried between weeks, effort-based | Seed by rating so cohorts are genuinely comparable |
| "Am I ready?" | Not answerable | Predicted score with a confidence range from RD |
| Bot difficulty | N/A | A calibrated opponent (§3) |

### Guardrails — this is the one mechanic that can hurt students

1. **Rating floor.** Never below 400. A student who cannot fall further stops fearing
   the number.
2. **RD-based framing.** New students see "Getting a read on you — 5 more questions"
   instead of a number that swings wildly. Chess.com's provisional rating, same idea.
3. **Private by default.** Never on a public profile, never in a leaderboard, without
   an explicit opt-in.
4. **Never announce a fall.** Rising: "▲ 4 this week." Falling: show the number, add
   "Algebra is pulling this down — 10 questions will help." A drop must always arrive
   attached to an action.
5. **Practice mode doesn't count.** Chess.com has unrated games for a reason. Students
   need somewhere to fail safely, or they'll avoid hard topics to protect the number —
   the exact opposite of what you want.

---

## 3. Bot opponents — the highest ratio of value to effort here

Battles currently require a second human. `MAX_OPEN_BATTLES = 5`, invites expire after
48 hours, and live mode needs both players present simultaneously. For a student
opening the app at 10pm with no friends on the platform, the feature does not exist.
This is classic multiplayer cold-start, and chess.com solved it with bots.

Their insight isn't "add an AI opponent." It's that **the bots have names, faces,
personalities and honest published ratings**, so playing one feels like playing someone
rather than practising against a machine.

### The design

A bot is not an AI. It's a probability distribution — a few dozen lines of code.

```python
BOTS = [
    # name,      rating, accuracy_curve,     speed,        personality
    ("Tunde",      700,  "guesses on hard",  "fast",   "Rushes. Beat him by being careful."),
    ("Amara",      950,  "solid on easy",    "steady", "Never rushes. Strong on the basics."),
    ("Chidi",     1150,  "strong, careless", "fast",   "Very quick, but slips under pressure."),
    ("Ms Bello",  1400,  "near-perfect",     "slow",   "The one to beat. Takes her time."),
]
```

Per question, given the question's rating and the bot's:

```
P(correct) = glicko_expected_score(bot_rating, question_rating)
answer_time = sample(bot.speed_distribution)
```

That's it. No model call, no latency, no cost. It produces an opponent that feels
human because it makes *plausible* mistakes — wrong on hard questions, occasionally
careless on easy ones — rather than random ones.

### Non-negotiable honesty rules

- Bot badge on the avatar, always. Never inferable-only.
- "Practice opponent" in the result screen, never "Opponent."
- **Bot results never count toward league points or leaderboards.** They may move
  subject rating (a calibrated opponent is a valid measurement) but must not affect
  anything competitive against real students.

Two days of work. It converts battles from a feature that works when your friends are
online into one that works at 10pm on a Tuesday.

---

## 4. Answer review with named mistake types

Chess.com's Game Review is the most-copied feature in the category, and the reason is
not the analysis — it's the **vocabulary**. Naming a move a "blunder" gives players a
shared word for a category of error, which makes the error thinkable and therefore
fixable. Players say "I blundered" the way Acelume students should be able to say "I
slipped on a topic I'd mastered."

Acelume's results screen currently shows correct/incorrect plus an explanation. Add a
label to every answer, derived from `UserResponse`, `TopicMastery` and the question's
rating. Labels marked ⏱ require `answer_seconds` (§1) — the other four ship today:

| Label | Condition | Message |
|---|---|---|
| **Sharp** | Correct on a question rated well above you | "Well above your level." |
| **Solid** | Correct, at level | — |
| **Lucky** ⏱ | Correct, but far slower than your average, or topic mastery is low | "Right answer — check you'd get it again." |
| **Slip** | Wrong, on a topic you're **proficient or mastered** | "You know this one. Read it again." |
| **Gap** | Wrong, on a topic not yet learned | "Not covered yet — here's the lesson." |
| **Blunder** ⏱ | Wrong, very fast, on an easy question | "Too quick. This one was there for you." |

Then one headline number, chess.com's Accuracy score:

```
Mathematics practice · 12 questions

     Accuracy  78%          ▲ your best this week

     Sharp 2   Solid 7   Lucky 1   Slip 1   Blunder 1

     ⚠  1 slip on Quadratic Equations — a topic you've mastered.
        [ 5 questions on it ]
```

That last line is the product. "You got 9/12" is a grade. "You slipped on a topic you'd
already mastered, here's five questions" is a next action, and it routes straight into
the mistake notebook and the existing spaced-review scheduler.

Distinguishing **Slip** from **Gap** is the highest-value piece: they feel identical to
a student and require completely opposite responses — one needs attention, the other
needs teaching.

---

## 5. Daily Question — the cheapest retention mechanic that exists

Chess.com's Daily Puzzle: one puzzle, same for everyone, every day. No matchmaking, no
opponent, no scheduling. It has run for over a decade because it works.

```
Today's Question · Mathematics
────────────────────────────────
[question]

  You: 14s ✓        Average: 41s        68% got this right
  You're in the fastest 12% today.        [ Share ]
```

Why it outperforms daily missions (which Acelume already has): missions are
*personalised*, so nobody else has yours. A shared question is a shared experience —
students compare it, which is free distribution in a market where WhatsApp study groups
are how everything spreads.

Build: one table (`daily_question(date, question_id, subject)`), one endpoint, one card
on Home. Rotate subjects across the week. Curate the pick — this is your most-seen
question of the day and a bad one is a public bad one.

Add a **daily-question streak**, separate from the learning streak: one tap to maintain,
which makes it the lowest-friction reason to open the app on a day the student wasn't
planning to study. Streaks are strongest when the minimum action is nearly free.

---

## 6. Rush mode — upgrade Blitz rather than add a mode

Blitz today: 180 seconds, up to 60 questions, one subject, random sample. It's a timed
quiz. Puzzle Rush is a different thing, and the differences are the whole design:

| | Blitz today | Puzzle Rush | Recommended |
|---|---|---|---|
| Ends on | Timer | **3 mistakes** | 3 mistakes **or** timer |
| Difficulty | Flat random | **Ramps** | Ramps from rating −200 upward |
| Score | Correct count | Correct before 3 strikes | Same |
| Feel | Test | Game | Game |

Three strikes changes the psychology completely. A timer makes a student rush. A strike
count makes them *careful*, then greedy, then careful again — and the run ends at a
moment of tension rather than a beep. It's also the mechanic that makes a personal best
mean something, because two runs are directly comparable in a way two timed quizzes
aren't.

Escalating difficulty gives every student a natural ceiling and a visible one. A 1400
student and a 700 student both fail out, both a few questions past where they're
comfortable, which is exactly where practice should sit.

Keep the existing timed Blitz as a second variant if you like — chess.com runs Rush
(3-strike) and Storm (timed) side by side. Just don't ship the timed one as the
flagship.

---

## 7. Clubs = schools

Chess.com Clubs and team matches are its strongest organic-growth engine: one member
recruits their whole team, and matches create obligation ("the team needs your game").

The Nigerian analogue is stronger than the chess one, because the unit already exists
and already competes. Inter-school academic competition is a live cultural tradition.

```
Federal Government College, Sokoto              412 members
────────────────────────────────────────────────────────────
This week vs. Queen's College, Lagos      2,140 – 1,890
Your contribution                                 84 MP

School rank (Sokoto)          #2 of 31
School rank (national)        #47 of 1,204
```

Mechanics — reuse `MasteryPointLedger` wholesale:

- A student joins one school. Changing schools has a 30-day cooldown (stops farming).
- School weekly total = sum of members' mastery points, **normalised per active member**
  so a 2,000-student school doesn't automatically beat a 200-student one.
- Weekly school-vs-school fixtures, matched on size and average rating.
- Termly national leaderboard by state and nationally.

Growth mechanics — this is where the value is:

- A joining student sees their school's rank immediately, or *"Be the first from your
  school"* — which is a genuinely strong hook for a 16-year-old.
- Weekly result is a shareable image sized for WhatsApp status. That is the single
  highest-leverage distribution surface in this market.
- Teachers can claim a school (routes directly into Acelume for Educators — this is the
  cheapest possible top of funnel for the paid product).

**Safety, non-negotiable:** school membership is a claim, not verification. Never expose
individual student names on public school leaderboards — aggregate only, with
individual contribution visible to the student alone. Same reasoning as the existing
league opt-out.

---

## 8. Arenas — scheduled events

Chess.com arenas create appointment usage: a fixed time when everyone plays at once,
which turns a solitary activity into an occasion.

```
JAMB Mathematics Arena · Saturday 4pm · 45 minutes
1,204 registered
Answer as many as you can. Streaks multiply your points.
```

Rules worth stealing: a correct-answer streak multiplier (2 in a row = ×1.5, 4 = ×2),
resetting on a wrong answer. It produces a real tension between speed and care that a
flat scoring system doesn't.

Build after leagues have proven engagement — it's the same points machinery on a
different clock, so it's cheap, but it's only worth it once there are enough
simultaneous users to make a live leaderboard feel populated. **Below ~200 concurrent,
an arena feels empty and does active harm.** Gate it on that number.

---

## 9. Insights — say the thing, don't draw the chart

Chess.com's Insights works because it makes flat statements: *"You lose most of your
games in the endgame."* Not a chart — a sentence you can act on.

Acelume has rich data — topic mastery, review history, question-level response
history — and currently renders it as percentages. Convert to statements:

```
What's actually costing you marks
─────────────────────────────────────────────────────────
📉  Your accuracy drops 22% after question 30.
    Stamina, not knowledge — try two 25-question sets
    instead of one 50.

🎯  You get 81% of algebra right — but only 54% when the
    question is a word problem.

🔁  You've re-learned "Simultaneous Equations" three times.
    It isn't sticking. [ Try the lesson a different way ]

⏱️  You spend 2.4× longer on geometry than anything else,
    for the same accuracy. That's ~8 minutes in a real paper.
    ← needs answer_seconds (§1)
```

The first three are computable from `UserResponse`, `QuizAttempt` and `TopicMastery`
today, with no new data collection — the work is entirely in the phrasing. Anything
about pace or time management needs `answer_seconds` first, and pacing is the insight
students find most surprising, so it's worth the hour.

### Question archetypes = chess openings

Chess.com tells you which openings you're weak in. Acelume can tell a student which
*question shapes* beat them — often more actionable than topic weakness, because it's a
technique fix rather than a knowledge fix:

```
negation      "Which of the following is NOT..."
diagram       requires reading a figure
word_problem  wrapped in a scenario
multi_step    two or more operations chained
data_read     table or graph interpretation
```

Tag questions with archetypes (a one-off classification pass over the bank, which is
tractable given the archive work already done), then: *"You get 88% of straight
questions right and 52% of 'which is NOT' questions. The maths isn't the problem —
you're missing the negation."*

That's a fifteen-minute fix worth several marks, and no competitor in this market is
telling students anything like it.

---

## 10. Fair play — required the moment ratings exist

Chess.com's fair-play system is invisible infrastructure that the entire rating economy
depends on. Once Acelume has ratings, matchmaking and school competitions, there is a
reason to cheat.

Minimum viable:

- **Time-per-answer floor.** Correct answers under ~1.2s on unseen questions are not
  reading time. Flag, don't punish.
- **Repeat-set detection.** Same question set attempted repeatedly before a rated run.
- **Rating-jump detection.** Statistically implausible gains relative to RD.
- **Shadow handling.** Flagged accounts keep full learning access and are quietly
  excluded from leaderboards, school totals and matchmaking. Never accuse a student of
  cheating on a study app — the false-positive cost far outweighs the benefit, and
  you're dealing with minors.

---

## 11. What not to borrow from chess.com

| Their mechanic | Why it doesn't transfer |
|---|---|
| Paywalled game analysis | Explanations are the core value of an exam app. Paywalling them makes the product worse at the thing it's for. Paywall breadth (mock exams, unlimited practice), never understanding. |
| Daily puzzle limits on free tier | Creates resentment in a market where the alternative is a free PDF of past questions. |
| Multiple currencies | Acelume already runs XP + Mastery Points + streaks + achievements. That is at the limit. Adding coins/gems makes every number mean less. |
| Public rating on profiles | Chess is a hobby; exam performance is identity, and these are minors. Private by default. |
| Aggressive loss framing | Chess players accept losing as the game. Students experience it as evidence they're not clever. Every fall must come with an action. |
| Titled-player prestige tiers | No credible equivalent, and inventing one creates a caste system among teenagers. |

---

## 12. Build order

Ordered by value ÷ effort. Rating is first because five other things plug into it.

| # | Feature | Effort | Impact | Depends on |
|---|---|---|---|---|
| 0 | **`answer_seconds` on `UserResponse`** | **XS** | Unblocks 4, 5, 9 — and the data is unrecoverable if delayed | — |
| 1 | **Subject Rating** (internal, shown as predicted score) | M | **Very high** — unlocks 3, 4, 6, and adaptive difficulty | `LearningPath` (`PRODUCT-ARCHITECTURE.md` §2) |
| 2 | **Daily Question** | **S** | High — retention + organic sharing | — |
| 3 | **Bot opponents** | S | High — makes battles work at all hours | 1 |
| 4 | **Answer-quality labels + accuracy** | S | High — turns results into next actions | 0, 1 |
| 5 | **Insights as sentences** | S | Medium-high — mostly phrasing | 0 (partial) |
| 6 | **Rush mode** (Blitz → 3 strikes + ramp) | S | Medium — better session shape, real personal bests | 1 |
| 7 | **Question archetypes** | M | Medium-high — genuinely differentiating | classification pass |
| 8 | **School clubs** | L | **Very high on growth**, low on learning | 1, moderation |
| 9 | **Fair play** | M | Required, invisible | 0, 1, 8 |
| 10 | **Arenas** | M | Medium — gate on ~200 concurrent | 1, 8 |

Item 0 is an hour and should go out with the next deploy regardless of everything else.
Items 2, 4 and 5 need no new architecture and could ship inside two weeks. Item 1 is
the one that changes what the product can do.

---

## The one-line version

> Acelume has more gamification than chess.com and less honesty. Add the one number
> that can go down, name the mistakes, give students an opponent at 10pm, and let their
> school compete. Everything else already exists.
