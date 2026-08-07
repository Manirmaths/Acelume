from datetime import datetime, date, time, timedelta, timezone as _timezone
from zoneinfo import ZoneInfo

UTC = _timezone.utc

from sqlalchemy import String, Integer, Float, Text, Boolean, DateTime, Date, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_practice_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Duolingo-style streak freeze: consumable inventory that auto-protects a
    # single missed day (see record_practice()). Earned every 7-day streak
    # milestone, capped so it can't be hoarded indefinitely.
    streak_freezes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # IANA timezone name. Streak and daily-mission boundaries are calendar days
    # in the STUDENT's timezone -- a Nigerian student practising at 11pm would
    # otherwise lose the day at midnight UTC, an hour before their own.
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Lagos", nullable=False)

    # Second streak type (spec section 6). The Learning streak above counts any
    # meaningful activity; this one requires demonstrated accuracy, so a
    # student who shows up daily but is struggling keeps the first without the
    # second falsely implying they are on top of the material.
    mastery_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_mastery_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_mastery_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Weekly leagues are opt-OUT, not opt-in: a competitive leaderboard is
    # exactly the thing that discourages weaker students, and the spec
    # requires that opting out leaves every learning feature intact.
    league_opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Current tier, carried between weeks. Foundation is the entry tier.
    league_tier: Mapped[str] = mapped_column(String(20), default="foundation", nullable=False)
    STREAK_FREEZE_CAP = 3

    # Duolingo-style daily XP goal. Stored as a points target (points are the
    # app's existing XP-equivalent, +10 per correct answer) rather than a
    # question count, since that's what's already tracked per-user.
    daily_goal: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    has_taken_diagnostic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Daily Question streak. A THIRD streak, deliberately -- the Learning
    # streak needs a real practice session and the Mastery streak needs
    # demonstrated accuracy, so both are things a student can be too tired or
    # too busy to reach. This one costs a single tap.
    #
    # That is the entire point: the cheapest possible reason to open the app
    # on a day the student was not going to study. A streak is at its
    # strongest when the minimum qualifying action is nearly free, and neither
    # existing streak is.
    daily_question_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_daily_question_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_daily_question_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Dormant premium/subscription plumbing -- not enforced anywhere right now.
    premium_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Short shareable code so a parent/guardian/tutor can link themselves as
    # a read-only watcher of this account's progress (see GuardianLink
    # below), without ever needing this account's password. Generated
    # lazily on first request (routers/family.py), not backfilled -- most
    # accounts will never need one.
    guardian_link_code: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    responses: Mapped[list["UserResponse"]] = relationship(back_populates="user")
    review_questions: Mapped[list["ReviewQuestion"]] = relationship(back_populates="user")
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(back_populates="user")

    @property
    def is_premium(self) -> bool:
        return bool(self.premium_until and self.premium_until > datetime.utcnow())

    def local_today(self) -> date:
        """
        Today's date in the STUDENT's timezone.

        Streak days are calendar days where the student lives, not on the
        server. Render runs in UTC, so `date.today()` rolled a Nigerian
        student's day over at 11pm their time -- costing them a streak they
        had actually earned.

        Falls back to UTC if the stored timezone is unrecognised. Bad profile
        data should never make answering a question fail.
        """
        try:
            return datetime.now(ZoneInfo(self.timezone or "Africa/Lagos")).date()
        except Exception:
            return datetime.utcnow().date()

    def local_day_start_utc(self) -> datetime:
        """
        The UTC instant at which the student's current calendar day began.

        Timestamps are stored naive-UTC, so "what did they do today?" needs
        the student's local midnight translated back into UTC -- not UTC
        midnight, which for a Lagos student is 1am their time. Getting this
        wrong makes the daily XP ring reset an hour early.
        """
        try:
            tz = ZoneInfo(self.timezone or "Africa/Lagos")
        except Exception:
            return datetime.combine(datetime.utcnow().date(), time.min)
        local_midnight = datetime.combine(self.local_today(), time.min, tzinfo=tz)
        return local_midnight.astimezone(UTC).replace(tzinfo=None)

    def record_mastery_day(self, met_standard: bool) -> None:
        """
        Extend the Mastery streak, which unlike the Learning streak requires
        the student to have actually performed well that day.

        No streak freeze applies here on purpose: a freeze protects
        attendance, and there is no honest way to protect a day on which no
        competence was demonstrated.
        """
        if not met_standard:
            return
        today = self.local_today()
        if self.last_mastery_date == today:
            return
        gap = (today - self.last_mastery_date).days if self.last_mastery_date else None
        self.mastery_streak = (self.mastery_streak or 0) + 1 if gap == 1 else 1
        self.last_mastery_date = today
        if self.mastery_streak > (self.longest_mastery_streak or 0):
            self.longest_mastery_streak = self.mastery_streak

    def record_practice(self) -> None:
        today = self.local_today()
        if self.last_practice_date == today:
            return
        gap = (today - self.last_practice_date).days if self.last_practice_date else None
        if gap == 1:
            self.current_streak = (self.current_streak or 0) + 1
        elif gap == 2 and (self.streak_freezes or 0) > 0:
            # Missed exactly one day -- spend a streak freeze to keep it alive,
            # same as Duolingo's streak freeze/repair. A gap of 2+ days beyond
            # this isn't covered; the streak resets like normal.
            self.streak_freezes -= 1
            self.current_streak = (self.current_streak or 0) + 1
        else:
            self.current_streak = 1
        self.last_practice_date = today
        if self.current_streak > (self.longest_streak or 0):
            self.longest_streak = self.current_streak
        if self.current_streak > 0 and self.current_streak % 7 == 0:
            self.streak_freezes = min((self.streak_freezes or 0) + 1, self.STREAK_FREEZE_CAP)


class Passage(Base):
    """
    A shared reading/comprehension passage (or data set) that one or more
    Questions can reference via Question.passage_id. Most questions won't
    use one -- this exists for English comprehension, data-interpretation
    sets in Geography/Economics, etc.
    """
    __tablename__ = "passage"

    id: Mapped[int] = mapped_column(primary_key=True)
    passage_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    passage_text: Mapped[str] = mapped_column(Text, nullable=False)

    questions: Mapped[list["Question"]] = relationship(back_populates="passage")


class Question(Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stable, human-assigned business key (e.g. "MTH-0001") used for safe
    # re-runnable CSV imports. Nullable for backward compatibility with any
    # row created before this field existed, but every seeded row has one.
    question_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)

    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    subtopic: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # "easy" | "medium" | "hard"
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Text, not String(500): inline SVG data-URIs used for self-contained
    # diagram questions can run well past 500 characters.
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    option_a: Mapped[str] = mapped_column(Text, nullable=False)
    option_b: Mapped[str] = mapped_column(Text, nullable=False)
    option_c: Mapped[str] = mapped_column(Text, nullable=False)
    option_d: Mapped[str] = mapped_column(Text, nullable=False)
    correct_option: Mapped[str] = mapped_column(String(10), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    year: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exam_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)  # pipe-separated
    # "original" | "past-question" | "licensed"
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="original")
    # "active" (visible to students) | "draft" (imported but hidden)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")

    passage_id: Mapped[str | None] = mapped_column(
        String(50), ForeignKey("passage.passage_id"), nullable=True
    )
    passage: Mapped["Passage | None"] = relationship(back_populates="questions")


class UserResponse(Base):
    __tablename__ = "user_response"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False)
    # Which QuizAttempt this response belongs to, if any (nullable so
    # standalone flows like the daily challenge can still log a response).
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("quiz_attempt.id"), nullable=True)
    selected_option: Mapped[str] = mapped_column(String(1), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Wall-clock seconds the student spent on this question, as reported by the
    # client and clamped server-side (see routers/quiz.py::clamp_answer_seconds).
    #
    # Nullable on purpose: every row written before this column existed has no
    # honest value, and inventing one would poison every average computed from
    # it. Any analysis must therefore filter nulls rather than coalesce to 0.
    #
    # Deriving this from consecutive `timestamp` values is NOT an adequate
    # substitute -- it breaks on pauses, backgrounded tabs, and the mock exam's
    # free navigation, where a student can revisit a question much later.
    #
    # This is the input for: answer-quality labels (Lucky / Blunder), pacing
    # insights, and the fair-play time floor. See GAMIFICATION.md.
    answer_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="responses")
    question: Mapped["Question"] = relationship()


class ReviewQuestion(Base):
    __tablename__ = "review_question"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="review_questions")
    question: Mapped["Question"] = relationship()


class QuizAttempt(Base):
    """
    Server-side quiz state, replacing what used to live in a Flask server
    session. Each attempt tracks its own question list and progress, so it's
    resumable, auditable, and works cleanly with a stateless JSON API (no
    server session cookie needed for quiz state -- only the JWT auth cookie).
    """
    __tablename__ = "quiz_attempt"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # quiz | cbt | diagnostic | marked | daily | blitz | mock
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)

    question_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    # For CBT: parallel list of {"id": qid, "subject": subj} lives in question_ids as dicts;
    # for other modes it's a flat list of ints.
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)

    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_question_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Question IDs the student has flagged "mark for review" -- only used by
    # the free-navigation Mock exam flow (routers/mock.py); quiz/blitz/
    # smart_review's linear one-question-at-a-time flow doesn't touch this.
    marked_question_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Rush mode only: wrong answers so far. The run ends at RUSH_MAX_STRIKES.
    #
    # A strike count and a timer produce opposite behaviour. A timer makes a
    # student rush -- the whole session is spent trying to go faster. Three
    # strikes makes them careful, then greedy as the score climbs, then careful
    # again, and the run ends on a moment of tension rather than a beep. It is
    # also what makes a personal best mean something: two Rush runs are
    # directly comparable in a way two timed quizzes are not.
    strikes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="quiz_attempts")


class Payment(Base):
    """Dormant Paystack transaction log, carried over for a later re-enable."""
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GuardianLink(Base):
    """
    A parent/guardian/tutor account linked as a read-only watcher of a
    student account's progress, established when the guardian redeems the
    student's `guardian_link_code` (routers/family.py). Deliberately generic
    -- the same link type covers both "parent watching one child" and "tutor
    watching several students" (a tutor is just a guardian_user_id with
    multiple rows), so this doesn't need a separate classroom/cohort model
    for a first version. No password sharing, no elevated access -- a
    guardian can only ever read aggregate stats, never act as the student.
    """
    __tablename__ = "guardian_link"

    id: Mapped[int] = mapped_column(primary_key=True)
    guardian_user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    student_user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("guardian_user_id", "student_user_id", name="uq_guardian_student"),
    )


class PasswordResetToken(Base):
    """
    Single-use password reset token. We store a SHA-256 hash of the token,
    never the raw value, so a DB leak alone can't be used to reset accounts.
    The raw token only ever exists in the emailed link and in-memory for the
    duration of the request that creates/consumes it.
    """
    __tablename__ = "password_reset_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()


class UserAchievement(Base):
    """
    Records that a user has unlocked a given achievement code (see
    app/achievements.py for the registry of codes + unlock criteria).
    Persisted (rather than recomputed on the fly every time) so earned_at is
    stable and we can tell a caller which ones were *just* unlocked.
    """
    __tablename__ = "user_achievement"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()


class QuestionMastery(Base):
    """
    Per-user, per-question spaced-repetition state (Leitner-box style).
    Box 1 = never seen or just missed (reviewed again soonest); each correct
    answer promotes to the next box (reviewed less often); any wrong answer
    drops straight back to box 1. Updated on every quiz answer (see
    routers/quiz.py answer_quiz) and read by the Smart Review mode
    (routers/smart_review.py) to prioritize whatever's actually due.
    """
    __tablename__ = "question_mastery"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False)

    box: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    times_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_question_mastery_user_question"),
    )

    MAX_BOX = 5
    BOX_INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}

    def record_answer(self, is_correct: bool) -> None:
        now = datetime.utcnow()
        self.times_seen = (self.times_seen or 0) + 1
        if is_correct:
            self.times_correct = (self.times_correct or 0) + 1
            self.box = min((self.box or 1) + 1, self.MAX_BOX)
        else:
            self.box = 1
        self.last_seen_at = now
        self.next_review_at = now + timedelta(days=self.BOX_INTERVAL_DAYS[self.box])


class TutorQuery(Base):
    """
    Log of AI-tutor requests. Not shown to users -- exists purely so
    routers/tutor.py can enforce a per-user daily cap and keep OpenAI cost
    bounded even if a key is misused or a bug causes runaway requests.
    """
    __tablename__ = "tutor_query"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class PushSubscription(Base):
    """
    A browser's Web Push subscription (from PushManager.subscribe()), one row
    per device/browser a user has opted into notifications on. endpoint is
    unique per subscription -- re-subscribing the same browser upserts rather
    than duplicating. See app/push.py for sending and
    routers/notifications.py for the subscribe/unsubscribe/send endpoints.
    """
    __tablename__ = "push_subscription"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()


class StudyPlan(Base):
    """
    One row per user: their exam date + chosen subjects. Day-by-day tasks
    (routers/study_planner.py) are computed on the fly from this plus their
    existing practice history -- not stored, so they always reflect current
    weak topics rather than going stale.
    """
    __tablename__ = "study_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), unique=True, nullable=False)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subjects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship()


class LessonNote(Base):
    """
    One lesson note per (subject, topic) -- a blog-style teaching page a
    student can read before attempting that topic's questions. AI-drafted
    (routers/admin.py's generate endpoint, app/ai.py's generate_lesson_note)
    grounded in real sample questions from the bank, then reviewed/edited by
    an admin before status flips from "draft" to "active" -- same
    draft/active gate as Question.status, since this is exam-prep content
    where an unreviewed AI mistake actively misleads a student.
    """
    __tablename__ = "lesson_note"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{"term": ..., "definition": ...}, ...]
    glossary: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Body text using a small constrained syntax the frontend renders: "## "
    # headings, "**bold**", "- " bullets, numbered examples, and \( ... \)
    # inline math (same delimiter the rest of the app already uses for KaTeX).
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    # Plain topic-name strings, same subject -- "study this next".
    related_topics: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")  # draft | active
    helpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unhelpful_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("subject", "topic", name="uq_lesson_note_subject_topic"),
    )


class NoteProgress(Base):
    """One row per (user, note) once a student has read/finished a note -- powers the Learn hub's per-subject % complete."""
    __tablename__ = "note_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    note_id: Mapped[int] = mapped_column(ForeignKey("lesson_note.id"), nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "note_id", name="uq_note_progress_user_note"),
    )


class NoteFeedback(Base):
    """One row per (user, note): the student's current helpful/unhelpful vote. Upserted, not appended -- a re-vote overwrites, adjusting LessonNote's denormalized counters."""
    __tablename__ = "note_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    note_id: Mapped[int] = mapped_column(ForeignKey("lesson_note.id"), nullable=False)
    is_helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "note_id", name="uq_note_feedback_user_note"),
    )


class NoteTutorQuery(Base):
    """
    Log of AI-tutor requests asked from a lesson note (as opposed to
    TutorQuery, which is scoped to a specific answered question). Kept as
    its own table rather than repurposing TutorQuery, since question_id
    there is NOT NULL and altering an existing column's nullability isn't a
    safe cross-dialect ALTER -- see database.py's _PENDING_COLUMNS comment.
    Counted together with TutorQuery under one shared daily cap in
    routers/notes.py so the two entry points can't be used to double a
    student's real daily AI budget.
    """
    __tablename__ = "note_tutor_query"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Gamification foundation (Phase 0)
#
# One server-authoritative event ledger that every gamification feature reads
# from, rather than each feature recomputing progress its own way. See
# GAMIFICATION-PLAN.md for how the eight planned features sit on top of this.
# ---------------------------------------------------------------------------


class LearningEvent(Base):
    """
    Append-only log of validated learning activity. This is the single source
    of truth for XP, mastery, missions, leagues, streaks and achievements.

    Why a ledger rather than incrementing counters: a counter cannot be
    audited, cannot be replayed after a bug, and cannot answer "was this
    already rewarded?". `event_key` makes every write idempotent -- the same
    real-world action (answering question 42 in attempt 7) always produces the
    same key, so a retried request, a double-tapped button, or a re-synced
    offline queue can never be rewarded twice.

    Rows are never updated in place. To undo something, write a reversal row
    and set `reversed_at` on the original.
    """
    __tablename__ = "learning_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)

    # LESSON_COMPLETED | QUESTION_ANSWERED | MISTAKE_CORRECTED | PRACTICE_COMPLETED
    # | TOPIC_PROFICIENT | TOPIC_MASTERED | REVIEW_COMPLETED | MOCK_COMPLETED
    # | MISSION_COMPLETED | BATTLE_COMPLETED
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # Deterministic natural key, e.g. "QUESTION_ANSWERED:attempt=7:q=42".
    # UNIQUE -- this is the idempotency guarantee, enforced by the database
    # rather than by application checks that race under concurrency.
    event_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    subject: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Free-form result data (score, accuracy, duration, difficulty...). JSON so
    # new event types don't need a migration for each new field.
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Client-supplied for offline sync; the SERVER timestamp is what counts for
    # streaks and league weeks, so a device with a wrong clock cannot cheat.
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reversed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class XpLedger(Base):
    """
    Append-only XP transactions. `User.points` stays as the fast running total,
    but this table is the auditable record behind it.

    XP only ever goes up (the spec is explicit: a wrong answer must never cost
    XP), so the only negative rows here are deliberate reversals of invalidated
    activity -- e.g. a mock that was abandoned and later voided.
    """
    __tablename__ = "xp_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("learning_event.id"), nullable=True)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    # Mirrors LearningEvent.event_key so XP is idempotent independently of the
    # event write -- an event can legitimately grant XP from more than one rule.
    ledger_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class TopicMastery(Base):
    """
    Per-user, per-topic state driving the Quest Map.

    Distinct from QuestionMastery, which is per-QUESTION Leitner scheduling.
    That answers "when should this student see this question again?"; this
    answers "does this student understand this topic?". Both are needed and
    neither replaces the other.

    `mastery_score` can go DOWN (it measures current understanding), while XP
    never does. Keeping them in separate tables is what stops a student looking
    academically strong purely from accumulated XP.
    """
    __tablename__ = "topic_mastery"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)

    # locked | available | learning | practising | proficient | mastered | review_due
    state: Mapped[str] = mapped_column(String(20), default="available", nullable=False)

    # 0-100, current understanding. Decays via review scheduling.
    mastery_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 0-3: lesson done / proficient / mastered.
    stars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    lesson_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    proficient_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    practice_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_practice_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_challenge_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Spaced review at the TOPIC level (3/7/21/45 days by default). Separate
    # from QuestionMastery.next_review_at, which schedules individual questions.
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    review_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "subject", "topic", name="uq_topic_mastery_user_topic"),
    )


class GamificationSetting(Base):
    """
    Admin-editable thresholds and reward values.

    The spec requires these to be changeable without shipping a new build --
    which matters more here than usual, because the Android app is a WebView
    shell whose users may be on an old release. Code reads through
    app/gamification/config.py, which falls back to documented defaults when a
    key is absent, so an empty table behaves exactly like the hard-coded values.
    """
    __tablename__ = "gamification_setting"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SyllabusTopic(Base):
    """
    The syllabus graph behind the Quest Map.

    Topics previously existed only as free-text strings on `Question.topic`,
    which meant there was no ordering, no prerequisites, and therefore no
    "locked" state and no Test Out. This table gives them identity.

    `prerequisite_id` is a self-reference forming a per-subject chain. It is
    NULLABLE and seeded sparsely on purpose: a topic with no prerequisite is
    immediately available, so an unsequenced subject degrades to a flat map
    rather than an unreachable one. Sequencing 97 topics across 11 subjects is
    a subject-expert judgement, not a programming one -- see
    backend/seed_syllabus.py for which subjects are ordered and which are
    deliberately left flat pending review.
    """
    __tablename__ = "syllabus_topic"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)

    # Display order within the subject. Ties fall back to topic name so the
    # map never renders in a nondeterministic order.
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    prerequisite_id: Mapped[int | None] = mapped_column(
        ForeignKey("syllabus_topic.id"), nullable=True
    )

    estimated_minutes: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lets an admin retire a topic from the map without deleting student
    # history that references it.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("subject", "topic", name="uq_syllabus_subject_topic"),
    )


class DailyMission(Base):
    """
    One of the three missions generated for a student each day.

    Progress is derived, not clicked: `progress` is updated from validated
    learning events, so a student never has to claim anything manually and a
    replayed event cannot advance a mission twice (see gamification/missions.py).

    `local_date` is the student's OWN calendar date, not the server's. Missions
    reset at the student's midnight, which for a Lagos student is 23:00 UTC the
    day before -- the same boundary streaks use.
    """
    __tablename__ = "daily_mission"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # progress | practice | improvement -- one of each per day, so the day
    # always contains something new, something repetitive, and something
    # corrective rather than three of the same shape.
    kind: Mapped[str] = mapped_column(String(20), nullable=False)

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)

    target: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    estimated_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    # Deep link the client follows when the mission is tapped.
    action_path: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # One mission of each kind per student per day. This is what stops a
        # repeated timezone change, or two concurrent requests on first load,
        # from minting extra missions and therefore extra rewards.
        UniqueConstraint("user_id", "local_date", "kind", name="uq_daily_mission_user_date_kind"),
    )


class DailyReward(Base):
    """
    The once-per-day chest for completing all three missions.

    Its own table with a UNIQUE (user, date) rather than a flag on the user,
    so the "exactly one reward per day" guarantee is enforced by the database
    and survives concurrent requests.
    """
    __tablename__ = "daily_reward"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="uq_daily_reward_user_date"),
    )


class PersonalBest(Base):
    """
    A student's best result for a *comparable* kind of activity.

    The comparability key is the whole point. Without it an easier session
    silently overwrites a harder record and the feature actively misleads --
    a student is told they improved when they simply answered fewer, easier
    questions. So bests are scoped to mode, subject, topic, a question-count
    BAND and a difficulty band, and only attempts sharing all of those are
    ever compared.

    `attempts` and `baseline_pct` are kept alongside the best so the first
    result can be reported honestly as a baseline rather than dressed up as an
    achievement.
    """
    __tablename__ = "personal_best"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)

    # Deterministic string built by gamification/personal_best.py, e.g.
    # "quiz:Mathematics:Algebraic Processes:10-19:any".
    activity_key: Mapped[str] = mapped_column(String(255), nullable=False)

    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)

    best_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_attempt_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    baseline_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "activity_key", name="uq_personal_best_user_activity"),
    )


class LeagueCohort(Base):
    """
    One weekly group of ~20 students competing at the same tier.

    Cohorts are per (tier, week_start) and fill up to a cap, so a student is
    always matched against a small, comparable group rather than the entire
    user base. `week_start` is the Monday of the competition week.
    """
    __tablename__ = "league_cohort"

    id: Mapped[int] = mapped_column(primary_key=True)
    # foundation | bronze | silver | gold | diamond | scholar
    tier: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LeagueMembership(Base):
    """
    A student's place in one weekly cohort.

    `points` here are MASTERY POINTS, deliberately not XP: league position must
    reflect the quality of this week's learning, not lifetime accumulation.
    Otherwise a long-standing user tops every league forever and the
    competition is meaningless for everyone else.
    """
    __tablename__ = "league_membership"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("league_cohort.id"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Recorded at close so the result screen can explain what happened.
    final_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)  # promoted|stayed|demoted

    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # One cohort per student per week -- the constraint that stops a
        # repeated request, or a timezone flip, from joining twice.
        UniqueConstraint("user_id", "week_start", name="uq_league_member_user_week"),
    )


class MasteryPointLedger(Base):
    """
    Append-only weekly points, mirroring XpLedger.

    Separate from XP because the two answer different questions and must be
    able to disagree: XP never falls and accumulates for life, Mastery Points
    reset every Monday. Sharing one table would make "reset the league" mean
    "delete someone's XP history".
    """
    __tablename__ = "mastery_point_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    ledger_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class School(Base):
    """
    A school students can represent.

    The Nigerian analogue of a chess.com Club is stronger than the chess one,
    because the unit already exists and already competes -- inter-school
    academic competition is a live cultural tradition here, not something the
    product has to invent.

    Membership is a CLAIM, not a verification. `status` records how much we
    actually know. Nothing here should ever be presented as the school's own
    endorsement until an educator has claimed it.
    """
    __tablename__ = "school"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Nigerian state, or equivalent region elsewhere. Free text rather than an
    # enum: the list changes, and a wrong enum is harder to fix than a typo.
    state: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    country_code: Mapped[str] = mapped_column(String(2), default="NG", nullable=False)

    # community | claimed | verified
    status: Mapped[str] = mapped_column(String(20), default="community", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SchoolMembership(Base):
    """
    One student's school.

    One school at a time, with a cooldown on changing. Without the cooldown a
    student could hop to whichever school was about to win that week, which
    turns the whole competition into a farming exercise.
    """
    __tablename__ = "school_membership"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, unique=True, index=True
    )
    school_id: Mapped[int] = mapped_column(ForeignKey("school.id"), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Separate from joined_at so the cooldown survives a re-join to the same
    # school without granting a free switch.
    last_changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SchoolWeek(Base):
    """
    A school's finished week, frozen at close.

    Stored rather than recomputed so a past week cannot silently change when a
    student later joins, leaves, or is excluded by fair play. A leaderboard
    that rewrites its own history is not a leaderboard.
    """
    __tablename__ = "school_week"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("school.id"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    total_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_members: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # The ranked figure. Normalised per active member so a 2,000-student school
    # does not beat a 200-student one purely on headcount -- without this the
    # table is a size ranking wearing an effort ranking's clothes.
    points_per_member: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    state_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    national_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("school_id", "week_start", name="uq_school_week"),
    )


class SubjectRating(Base):
    """
    A student's Glicko-2 rating in one subject.

    The one number that can go DOWN and is comparable between people. See
    app/rating.py for why this exists when XP, level, mastery and league tier
    already do.

    `path_id` is present but unused: learning paths (JAMB 2027, WAEC, a
    university course) are the next architectural change, and mastery in one
    must never blend into another. Adding the column now, nullable, means the
    migration later is a backfill rather than an ALTER on a hot table. Until
    then every rating hangs off the single implicit path.
    """
    __tablename__ = "subject_rating"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    path_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)

    rating: Mapped[float] = mapped_column(Float, default=1200.0, nullable=False)
    # RD -- uncertainty. High means "we do not know yet", and the UI must say
    # so rather than showing a confident-looking number.
    deviation: Mapped[float] = mapped_column(Float, default=350.0, nullable=False)
    volatility: Mapped[float] = mapped_column(Float, default=0.06, nullable=False)

    peak_rating: Mapped[float] = mapped_column(Float, default=1200.0, nullable=False)
    # Snapshot taken at the start of the current week, so the UI can say
    # "+4 this week" without storing a full history.
    week_start_rating: Mapped[float] = mapped_column(Float, default=1200.0, nullable=False)
    week_start_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    answers_counted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "path_id", "subject", name="uq_subject_rating_user_path_subject"),
    )


class QuestionRating(Base):
    """
    How hard a question actually is, measured rather than asserted.

    `Question.difficulty` is a human tag and is frequently wrong -- a question
    tagged easy that 5% of students get right is not easy. These counters are
    the raw material for the real number (see
    rating.question_rating_from_responses).

    Stored as counters rather than recomputed from UserResponse on every read:
    the aggregate query over a table that grows with every answer in the app
    is exactly the sort of thing that is fine at 10k rows and a problem at 10m.
    """
    __tablename__ = "question_rating"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("question.id"), nullable=False, unique=True, index=True
    )
    times_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyQuestion(Base):
    """
    One question per calendar day, THE SAME for every student.

    Deliberately distinct from DailyMission, which is personalised. That
    personalisation is exactly what stops missions being social: no two
    students have the same one, so there is nothing to compare, and nothing
    to talk about. A shared question is a shared experience -- students
    compare times and scores, which in this market means it travels through
    WhatsApp study groups on its own.

    The date is a plain calendar date in Africa/Lagos rather than per-student
    local time. "Today's question" has to mean the same question to two
    students messaging each other, and a timezone-relative version would give
    a student who travelled a different question from their classmates.
    """
    __tablename__ = "daily_question"

    id: Mapped[int] = mapped_column(primary_key=True)
    on_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    question: Mapped["Question"] = relationship()


class DailyQuestionAttempt(Base):
    """
    One student's single attempt at a given day's question.

    UNIQUE on (user_id, daily_question_id): one attempt each, enforced by the
    database rather than an application check, so a double-tap or a replayed
    request cannot produce a second, better score.
    """
    __tablename__ = "daily_question_attempt"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    daily_question_id: Mapped[int] = mapped_column(ForeignKey("daily_question.id"), nullable=False, index=True)

    selected_option: Mapped[str] = mapped_column(String(1), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answer_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "daily_question_id", name="uq_daily_attempt_user_question"),
    )


class Battle(Base):
    """
    An asynchronous head-to-head over an identical question set.

    Async first, deliberately: live synchronous battles need reliable
    reconnection and clock handling, and getting those wrong ruins a match
    that a student cared about. Both players simply answer the same questions
    whenever they can, and the result settles when the second finishes or the
    invitation expires.

    The question set is chosen and stored SERVER-SIDE at creation, so both
    participants provably get the same questions and neither client can
    influence the selection.
    """
    __tablename__ = "battle"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Short shareable code, so a challenge can be sent over WhatsApp without
    # the app needing a friend graph.
    code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)

    created_by: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)

    question_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    seconds_per_question: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    # async | live. Async battles are answered whenever each player likes;
    # live battles advance on a shared server clock.
    mode: Mapped[str] = mapped_column(String(10), default="async", nullable=False)
    # Set when the second player joins a LIVE battle. Every deadline is derived
    # from this one server timestamp, so no client clock can influence pacing.
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # open | complete | expired
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Set when the opponent is a calibrated practice bot rather than a person
    # (see app/bots.py). Stored on the battle rather than as a fake
    # BattleParticipant row so a bot can never appear in a query that counts
    # players, and can never accidentally accrue league points or leaderboard
    # position -- the honesty rules are enforced by the schema shape, not by
    # remembering to filter.
    bot_key: Mapped[str | None] = mapped_column(String(20), nullable=True)


class BattleParticipant(Base):
    """
    One side of a battle. Exactly one attempt each -- enforced by the UNIQUE
    below rather than by an application check, so a retried join cannot create
    a second attempt with a fresh score.

    `answers` holds the submitted choices only. Correct answers are never sent
    to the client until the participant has submitted, so a player cannot read
    them out of the network response mid-battle.
    """
    __tablename__ = "battle_participant"

    id: Mapped[int] = mapped_column(primary_key=True)
    battle_id: Mapped[int] = mapped_column(ForeignKey("battle.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)

    answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Total seconds spent on questions answered CORRECTLY. Used only to break
    # a tie -- correctness always outranks speed.
    correct_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Updated on every poll. Used only to show "opponent connected" -- a
    # dropped connection must never forfeit a live battle, so this is
    # presentational, not authoritative.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("battle_id", "user_id", name="uq_battle_participant"),
    )
