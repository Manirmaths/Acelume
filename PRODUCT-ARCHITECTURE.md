# Acelume — Product Architecture

Status: proposal, not yet built. Written 2026-08-07.
Companion document: `GAMIFICATION.md`.

This refines the "Acelume Prep / Campus / Tutor" architecture proposal. It agrees with
that document's core diagnosis and disagrees with roughly half of its conclusions. Where
it disagrees, the reason is almost always the same: **the proposal was written as if
Acelume were greenfield.** It isn't. There are 15,900+ questions live, a mastery engine,
a league engine, a battle engine, an AI tutor and a guardian dashboard already shipped.
Several things the proposal recommends building already exist; several things it defers
to "Future" shipped months ago.

---

## 0. The first correction: this is four documents, not one

The source proposal puts brand strategy, navigation, database schema and roadmap into a
single tree. They have different owners, different audiences and — critically —
different rates of change. Merging them means a routine schema change forces an edit to
the brand document, and nobody can tell which parts are decided versus sketched.

| Layer | Question it answers | Changes | Where it lives |
|---|---|---|---|
| **1. Brand** | What do we call things in public? | Yearly | This doc, §1 |
| **2. Information architecture** | Where does a student click? | Per research round | This doc, §5–7 |
| **3. Domain model** | What tables and relationships? | Per feature | This doc, §3–4 + Alembic |
| **4. Roadmap** | What order? | Monthly | This doc, §9 — expected to go stale |

Rule: a change to layer 3 must not require editing layer 1. In the source proposal,
"Acelume Platform Services" sits inside the brand tree next to "Acelume Prep". Internal
services are never a brand tier. That's the symptom.

---

## 1. Naming — apply a test, not a taste

The source proposal correctly identifies a category error: Prep is a *purpose*, Campus is
an *environment*, Tutor is a *feature*. Three unlike things presented as peers. Correct.

But its fix keeps two of the three as sub-brands, which reintroduces the problem in a
milder form. Use a test instead.

> **A thing earns a name when it has its own buyer, its own price, or its own login.**
> Anything else is a feature and gets a lowercase description.

Applying it:

| Candidate | Own buyer? | Own price? | Own login? | Verdict |
|---|---|---|---|---|
| **Acelume** | — | — | — | The brand. Keep. |
| **Acelume for Educators** | Yes (schools, lecturers) | Yes | Yes (educator role) | **Earns a name.** Ship it. |
| Acelume Prep | No — same student | No — same subscription | No | Fails. It's a *path type*. |
| Acelume Campus | No — same student | No | No | Fails **today**. See trigger below. |
| Acelume Tutor | No | No | No | Fails hard. It's a feature. |

### What this means concretely

- **Do not ship "Acelume Campus" as a brand.** Ship **"University courses."** It is
  self-explanatory, needs no descriptor line under it, creates no expectation of
  timetables, accommodation or campus events, and costs nothing to rename later.
- **Do not ship "Acelume Prep" as a brand.** Ship **"Exam prep."** Note that `/prep` in
  a URL is fine — a URL segment is not a brand.
- **Do not use "Tutor" for three different things.** Use `Ask Acelume` (AI) and
  `Find a tutor` (human marketplace, when it exists). The source proposal reaches this
  same conclusion and then contradicts it by putting "Tutor" in the primary nav twice.
- **Ship "Acelume for Educators."** It is the one sub-brand that passes on all three
  criteria, and it's also the one the proposal treats as an afterthought.

### The promotion trigger

Campus earns its name the day a *university* — not a student — signs a contract for it.
At that moment it has a distinct buyer, a distinct price and a distinct login, and
"Acelume Campus" becomes correct. Write the trigger down now so the decision isn't
re-litigated every quarter:

> Promote a pathway to a named sub-brand when it has ≥1 signed institutional customer
> paying for that pathway specifically.

This is the difference between an endorsed architecture and premature brand
proliferation. You get the option without paying for it early.

---

## 2. The single entity that unblocks everything: `LearningPath`

Everything in the source proposal — the context switcher, Campus, separated mastery,
multiple exams, per-path leagues — reduces to one missing concept. Today the app has
no notion of *what a student is working towards*. `TopicMastery` is keyed on
`(user_id, subject, topic)`. A student preparing for JAMB Mathematics and taking
university MTH 101 would silently share one mastery record. That is the blocking bug
for the entire proposal, and it is one table plus one column.

```python
class LearningPath(Base):
    """What a student is working towards. Everything academic scopes to this."""
    __tablename__ = "learning_path"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)

    # "exam" | "course" | "subject" | "personal"
    kind: Mapped[str] = mapped_column(String(20))

    label: Mapped[str] = mapped_column(String(120))        # "JAMB 2027"
    exam_type: Mapped[str | None] = mapped_column(String(20))     # JAMB | WAEC | NECO | NABTEB
    exam_year: Mapped[int | None] = mapped_column(Integer)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("course.id"))
    subjects: Mapped[list[str]] = mapped_column(JSON)      # chosen subjects

    target_date: Mapped[date | None]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_opened_at: Mapped[datetime | None]
```

Then add `path_id` to `TopicMastery`, `QuestionMastery`, `LearningEvent`,
`MasteryPointLedger`, `LeagueMembership`, `PersonalBest`, `StudyPlan`.

**Do not add `path_id` to `XpLedger`, `User.points`, `User.current_streak` or
`UserAchievement`.** That asymmetry is the whole design:

| Scope | What it measures | Examples |
|---|---|---|
| **Global (identity)** | Who you are on Acelume | XP, level, learning streak, achievements, subscription |
| **Per-path (academic)** | What you actually know | Mastery, review schedule, predicted score, league points, personal bests |

A student must not be able to farm league position on an easy path, and JAMB
Mathematics mastery must never blend into university calculus mastery. But their
streak should survive switching paths — a streak measures a habit, not a syllabus.

### Migration for existing users — silent, no re-onboarding

The proposal has no migration section. This is the most important thing in the whole
build, because every existing user has progress that must not appear to vanish.

```
1. Create one LearningPath per existing user:
   kind="exam", exam_type="JAMB", label="JAMB <next year>",
   subjects = distinct subjects in their TopicMastery rows.
2. Backfill path_id on every existing academic row to that path.
3. Ship the path switcher in a state where it shows exactly one path.
   No modal, no announcement, no "set up your new learning path" screen.
```

A returning student should see their dashboard exactly as they left it, plus a
new small control in the header they can ignore forever. Onboarding a *new* concept to
*existing* users is where products like this lose their most valuable cohort.

---

## 3. Domain model — model the course, not the hierarchy

The source proposal specifies a 13-level academic tree:

```
Country → Institution → Campus → Faculty → Department → Programme →
Programme version → Academic level → Semester → Course → Course version →
Course unit → Topic
```

This should not be built. Three reasons, in order of severity:

**1. It is wrong, not just expensive.** The tree assumes every country's higher
education uses the same shape. Nigeria has Faculty → Department → 100 Level → First
Semester. Ireland has Faculty → School → Module with no "level" in the Nigerian sense.
The UK has School → Course → Year. Modelling one country's org chart as a universal
schema means the second country you add either breaks the tree or gets stuffed into
fields that don't mean what they say. Structural mismatches like this are extremely
expensive to unwind once there's data in them.

**2. Every level is a cost multiplier.** 13 levels = 13 tables, 13 admin CRUD screens,
13 joins on the hot path, and up to 13 pickers in onboarding.

**3. Students don't traverse it.** A student looking for MTH 101 types "MTH 101". They
do not navigate Country → Institution → Faculty → Department. The hierarchy is how a
*registrar* thinks, not how a student searches.

### The replacement

**A course is the atomic unit.** Everything above it is metadata on the course, not a
tree to walk. Two tables:

```python
class Institution(Base):
    __tablename__ = "institution"
    id, slug, name, short_name       # "usmanu-danfodiyo", "Usmanu Danfodiyo University", "UDUSOK"
    country_code                     # ISO 3166-1 alpha-2: "NG", "IE"
    kind                             # university | polytechnic | college
    status                           # verified | community | pending_review
    aliases: JSON                    # ["UDU", "UDUS", "Sokoto"] — search hits, not rows

class Course(Base):
    __tablename__ = "course"
    id, slug
    institution_id                   # FK
    code, title                      # "MTH 101", "Elementary Mathematics"

    # Denormalised, all nullable, all free text. Display + filter only.
    # Never joined on, never enforced, never a table.
    faculty: str | None              # "Faculty of Physical and Computing Sciences"
    department: str | None           # "Mathematics"
    programme: str | None            # "BSc Mathematics"
    level: str | None                # "100 Level" | "Year 1" — whatever the school calls it
    term: str | None                 # "First Semester" | "Autumn"

    syllabus_version: str | None     # "2025/26"
    status: str                      # verified | community | draft
    search_text: str                 # generated: code + title + aliases + department
```

Topics attach to a course exactly the way they already attach to a subject, so the
existing `TopicMastery` / `SyllabusTopic` machinery works unchanged.

Normalise later, when you have 500 courses and a concrete query you cannot serve. Not
before. Denormalised free text with good search is *strictly better* than a wrong
hierarchy, because free text can absorb a shape you didn't anticipate.

---

## 4. The reframe that removes three of your four biggest risks

The source proposal lists copyright, academic integrity and user-generated content
quality as major risks, then proposes mitigations for each. All three are real. All
three are also **optional**, and they all arrive through the same door: accepting
student uploads.

> **Campus, at launch, is the existing Prep engine pointed at a university syllabus.**
> Same topic → lesson → practice → mastery challenge → spaced review loop. Same
> `TopicMastery` state machine. Same question schema. Different topic list.
> **It is not a document repository.**

What this buys:

| Risk | With uploads at launch | Prep-engine Campus |
|---|---|---|
| Copyright / takedown | Full DMCA process, rights declarations, duplicate detection, legal review | **Does not arise.** All content is yours. |
| Academic integrity | Answer-trading, live-assessment leakage, policy + detection | **Does not arise.** No student-supplied assessment content. |
| UGC quality | 5-state verification ladder, community moderation, credibility damage from one wrong solution | **Does not arise.** Same editorial pipeline you already run. |
| Empty-course problem | Severe — an empty course page with an upload button is not a product | Real but bounded — you seed courses deliberately, so no course ships empty. |
| Engineering cost | File storage, virus scanning, OCR, AI generation pipeline, moderation queue, rights UI | **~0.** Reuses everything already built. |

The proposal's own risk #1 — the empty-campus problem — is the argument for this. Its
suggested mitigations (uploads, AI-generated practice from notes) are precisely the
mechanisms that import risks #2, #3 and #4. Uploads look like the cheap way to fill
Campus. They are the expensive way.

**Defer uploads to the point where a course already has content and uploads add to it,
never to the point where uploads are what makes the course non-empty.**

### The launch gate for a Campus course

Do not open a course page below this bar:

```
✓ Topic list mapped to the actual course outline
✓ ≥ 60 questions with worked explanations
✓ ≥ 1 past paper or representative assessment
✓ Lesson notes for ≥ 50% of topics
```

Below the bar, the course is searchable but shows "In preparation — get notified,"
which is honest and costs no trust. An empty course page with an upload prompt costs a
great deal of trust, and you only get one first visit per student.

---

## 5. Navigation — the problem is already live

The source proposal warns against a fragmented navigation bar. That warning arrives
late: `AppShell.tsx` already ships **14 primary destinations.**

```
Dashboard · Subjects · Learn · Leaderboard · League · Battles · Blitz · Mock ·
Study Planner · Flashcards · Achievements · Review · Family · Admin
```

Six of those (Leaderboard, League, Battles, Blitz, Achievements, and arguably Study
Planner) are engagement features competing for attention with the actual learning work.
Fixing this is higher value than anything in the Campus plan, and it can ship next
week.

### Target: five destinations, everything else nested

| Nav item | Absorbs today's routes |
|---|---|
| **Home** | `/dashboard` |
| **Learn** | `/learn`, `/subjects`, `/subjects/:s`, `/subjects/:s/quest`, `/subjects/:s/topics/:t`, `/flashcards` |
| **Practice** | `/quiz`, `/blitz`, `/mock`, `/review`, `/battles`, mistake notebook |
| **Progress** | `/leaderboard`, `/league`, `/achievements`, `/study-planner`, analytics |
| **Profile** | `/family`, settings, subscription, `/admin` (admins only) |

Two rules that keep it that way:

1. **Ask Acelume is not a nav item.** It is a persistent affordance attached to
   content — a button on every question, lesson and result screen, plus
   highlight-to-ask. A student who taps "Tutor" in a nav bar lands on an empty prompt
   box with no context and asks nothing. A student who taps "Explain this" under a
   question they just got wrong asks the best question they will ever ask. The source
   proposal states this correctly in one section and then puts Tutor in the primary nav
   in two others.
2. **Nothing enters primary nav because it is new.** New features enter through the
   surface where they're relevant. If a feature can only be found via nav, it isn't
   integrated yet.

### The path switcher

One control in the header, not a nav item:

```
┌──────────────────────────┐
│ JAMB 2027            ▾   │
├──────────────────────────┤
│ ✓ JAMB 2027              │
│   WAEC Mathematics       │
│   UDUSOK · MTH 101       │
│   ─────────────────      │
│   + Add a learning path  │
└──────────────────────────┘
```

Rules: default to `last_opened_at`. Never show the switcher to a student with one path
— it is confusing chrome advertising a feature they don't use. Switching preserves
scroll and never logs the student out of anything.

---

## 6. Onboarding — one field, not five screens

The source proposal's university flow is Country → University → Programme → Year →
Courses. Five cascading dropdowns before a single question is answered. Every dropdown
is a place to abandon, and dropdown 2 is where a student whose university isn't listed
discovers the product isn't for them.

### Replace with search-first

```
Step 1 — What are you working towards?
   ○ An exam        (JAMB · WAEC · NECO · NABTEB)
   ○ A university course
   ○ Just improving a subject
   ○ I teach                              → educator flow

Step 2 (exam)    →  Which exam? · Which year? · Which subjects?     3 taps
Step 2 (course)  →  ┌──────────────────────────────────────┐
                    │ 🔍 Course code, title or university   │
                    └──────────────────────────────────────┘
                    "MTH 101"  →  MTH 101 · Elementary Mathematics
                                  Usmanu Danfodiyo University · 100 Level
                    One field. Fuzzy across code, title, institution, aliases.

Step 3 — First useful action, chosen for them, never a menu:
         exam path   → 8-question diagnostic
         course path → first topic's lesson
         no content  → nearest matching general course + a notify toggle
```

Three principles the source proposal gets right and should be held to:

- **Never end onboarding on an empty dashboard.** End it inside a question or a lesson.
- **Never make "my university isn't listed" a dead end.** Offer the closest general
  course immediately, record the request, notify on launch.
- **Ask for target date and confidence later**, inside the study planner, once the
  student has a reason to care. Asking during signup is asking a stranger to plan.

---

## 7. URLs — optimise for search intent, not internal structure

The proposal's `/prep/jamb/mathematics` and `/campus/nigeria/university/course` encode
*your* org chart. Nobody searches for "Acelume Prep." They search for
"JAMB 2027 mathematics past questions." Lead with the thing they typed.

```
Public
  /jamb                                    /jamb/mathematics
  /jamb/mathematics/past-questions         /jamb/mathematics/algebra
  /waec/physics                            /neco/biology
  /universities                            /universities/ng
  /universities/ng/udusok                  /universities/ng/udusok/mth-101
  /subjects/mathematics
  /for-educators      /pricing      /how-it-works

App  (unchanged prefix, everything under /app)
  /app/home                 /app/learn/topic/{slug}
  /app/practice             /app/practice/session/{id}
  /app/progress             /app/profile
```

`/prep` and `/campus` become 301s to `/exams` and `/universities` if you ever ship them.
Slugs, never database IDs, on anything public — an ID in a URL is unshareable, tells a
competitor your row count, and can't be changed without breaking links.

---

## 8. The cut list

Nothing in the source proposal is deleted from the *idea*; the following are deleted
from the *plan*, meaning don't design, spec or schema them yet. Each has a re-entry
trigger.

| Cut | Why | Re-entry trigger |
|---|---|---|
| Programme / Faculty / Department as tables | Free-text fields on `course` do the same job | 500+ courses AND a query you can't serve |
| Course versions, programme versions | Zero students affected at pilot scale | A university partner requires it |
| Student uploads & personal study spaces | Imports 3 of your 4 major risks (§4) | Campus courses have content AND students ask to add to them |
| Human tutor marketplace | Two-sided marketplace, payments, safeguarding, vetting — a company in itself | Ask Acelume has clear demand you cannot serve with AI |
| 5-state content verification ladder | You are the only content source today; a ladder with one rung is theatre | First external contributor |
| Full org / RBAC / branding / integrations | Enterprise plumbing before an enterprise customer | First school signs |
| Multi-country expansion | Nigeria isn't saturated | Nigeria retention plateaus |
| "Acelume Campus" as a brand | Fails the naming test (§1) | First institutional contract |
| Lab usability testing with 3 cohorts | Expensive and slow at your stage; §10 is cheaper and continuous | You have a design team |

---

## 9. Sequencing — corrected against what actually ships today

The source proposal's roadmap is behind reality. It lists as V3 or "Future" several
things that are already live. Verified in the codebase:

| Proposal says | Reality |
|---|---|
| V1: Ask Acelume | **Shipped** — `routers/tutor.py`, `TutorQuery` |
| V3: Asynchronous battles | **Shipped** — `routers/battles.py`, async + live modes |
| V3: Weekly leagues | **Shipped** — 6 tiers, cohorts of 20, promote top 5, mastery points |
| Future: Live battles | **Shipped** — 30s/question, shared server clock |
| Future: Parent/guardian dashboard | **Shipped** — `GuardianLink`, `routers/family.py` |
| Recommends: separate Mastery / XP / league points | **Shipped** — `TopicMastery.mastery_score` (falls), `XpLedger` (never falls), `MasteryPointLedger` (weekly reset) |

That last row matters: the proposal's headline measurement recommendation is a
description of the system you already run, not a change to it. Treat it as validation
of existing design, not as work.

### Corrected sequence

**Now — architecture, no new surface** *(this is the whole unlock)*
1. `LearningPath` + `path_id` on academic tables + silent backfill (§2)
2. Path switcher, hidden at one path
3. Nav 14 → 5 (§5)
4. Ask Acelume out of nav, into content surfaces
5. Subject Rating (see `GAMIFICATION.md` §2 — it is the prerequisite for adaptive
   difficulty, honest matchmaking and league seeding)

**Next — depth before breadth**
6. Multi-exam paths: WAEC and NECO as first-class alongside JAMB. Proves the path
   abstraction against a real second case *before* it has to survive universities.
7. Mistake notebook + answer-quality labels (`GAMIFICATION.md` §4)
8. Bot opponents (`GAMIFICATION.md` §3) — fixes battles being unplayable when nobody's online
9. Daily Question (`GAMIFICATION.md` §5)

**Then — Campus pilot, deliberately tiny**
10. `Institution` + `Course` tables (§3)
11. **3–5 courses at one university, at the §4 launch gate.** Not five universities. Not
    a faculty. Three courses you can make genuinely excellent — first-year Mathematics
    is the obvious pick, because it overlaps heavily with content you already own.
12. Course search, request-a-course flow, notify-on-launch

**Later — only if the pilot retains**
13. Acelume for Educators: class creation, assign practice, class mastery view
14. School clubs & inter-school competition (`GAMIFICATION.md` §7)
15. More courses, then more universities, then more countries — in that order

The pilot has one success criterion, decided before it launches: **do students on a
Campus course return in week 2 at a rate comparable to Prep students?** If not, more
courses will not fix it, and the honest move is to stop and put the effort back into
Prep.

---

## 10. How to validate at your actual scale

The source proposal recommends moderated task-based testing with three cohorts. The
task list is good. The method is wrong for a solo developer with a live app: it's slow,
expensive, and you already have real users generating better evidence.

**Instrument instead. Continuous, free, and honest.**

| Question the proposal wants to answer | Measure this instead |
|---|---|
| Do users pick the right pathway? | Step-1 selection → 7-day retention, by choice |
| Time to find content | Signup → first answered question (target: **< 90 seconds**) |
| Confusion between areas | Path switches per session (>2 = the switcher is a search box in disguise) |
| Onboarding completion | Drop-off per step. Any step losing >20% is broken. |
| Do they understand mastery vs XP vs league points? | Support tickets + a single in-app question after 2 weeks |
| Is a resource trusted? | Only measurable once external content exists — which §8 defers |

Then add **five** moderated sessions, not three cohorts — with real JAMB candidates,
on their own phones, on mobile data. Not a lab. Watch for the two things instrumentation
can't see: where they hesitate, and what they say out loud when confused. Five sessions
surfaces most of what twenty would, and you can run them in a week.

The one task worth scripting: *"You want to practise JAMB Mathematics. Start."* If that
takes more than two taps from the home screen, the architecture is wrong regardless of
what the tree diagram says.

---

## 11. Positioning

The source proposal's tagline options both hedge. "Learn now. Master what comes next."
is abstract enough to belong to any product. "Your learning journey, from exams to
university" is clearer but describes your roadmap rather than the student's problem.

A Nigerian student searching at 11pm has a specific problem: **they don't know which
topics will cost them marks, and they're running out of time.** Positioning should
answer that.

> **Acelume — know exactly what to study next.**

Supporting line:

> Practise real past questions, get every answer explained, and see which topics are
> actually costing you marks — with a predicted score that updates as you learn.

This is defensible because it's true of what's built (mastery engine, spaced review,
recommended topics, score estimate) and it scales to university courses without
mentioning universities. "Study hub," as the proposal correctly notes, is generic — but
so is "personalised learning platform." Lead with the outcome, not the category.

---

## 12. Summary of changes from the source proposal

**Kept**
- The category-error diagnosis — Prep, Campus and Tutor are not peers
- One account, one profile, one dashboard; context switcher over sub-product navigation
- Progressive disclosure; gamification never above learning work
- Global platform architecture, narrow launch scope
- "Students choose what to learn, not which internal product contains it"

**Changed**
| Source proposal | This document |
|---|---|
| Prep & Campus as named sub-brands | Path types. Named only on the §1 trigger. |
| One tree covering brand + IA + schema + roadmap | Four separate layers (§0) |
| 13-level academic hierarchy | `Institution` + `Course`, denormalised (§3) |
| Campus as a course-resource repository | Campus as the Prep engine on a syllabus (§4) |
| Uploads as the empty-campus fix | Uploads deferred; launch gate instead (§4) |
| 5-screen cascading onboarding | One search field (§6) |
| `/prep/...`, `/campus/...` | `/jamb/...`, `/universities/...` (§7) |
| Tutor in primary navigation | Contextual affordance only (§5) |
| Roadmap starting from zero | Corrected against what's shipped (§9) |
| Moderated testing, 3 cohorts | Instrumentation + 5 sessions (§10) |

**Added**
- The naming test and its promotion trigger (§1)
- `LearningPath` and the global-vs-per-path scoping rule (§2)
- Silent migration for existing users (§2)
- The Campus launch gate (§4)
- The 14 → 5 navigation collapse — the highest-value change available today (§5)
- An explicit cut list with re-entry triggers (§8)
- A stop condition for the Campus pilot (§9)

---

## The one-line version

> Acelume already has the engine. It is missing the *container* — a learning path — and
> it has too many front doors. Build the container, close the doors, and Campus becomes
> a content problem instead of an architecture problem.
