from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


def _normalize_email(v: str) -> str:
    # Emails are looked up case-insensitively everywhere (login, register
    # dupe-check, forgot-password) -- normalizing at the schema boundary
    # means every router just compares plain strings without needing to
    # remember to .lower() at each call site. See also
    # database.normalize_emails() for the one-time cleanup of any accounts
    # that were stored with mixed case before this existed.
    return v.strip().lower()


# ---------- Auth ----------
class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return _normalize_email(v)


class LoginIn(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return _normalize_email(v)


class ForgotPasswordIn(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return _normalize_email(v)


class ResetPasswordIn(BaseModel):
    token: str
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    points: int
    is_admin: bool
    is_premium: bool
    current_streak: int
    longest_streak: int
    streak_freezes: int
    daily_goal: int
    has_taken_diagnostic: bool

    class Config:
        from_attributes = True


# ---------- Subjects ----------
class SubjectOut(BaseModel):
    name: str
    question_count: int


class TopicOut(BaseModel):
    name: str
    count: int


# ---------- Passages ----------
class PassageOut(BaseModel):
    passage_id: str
    subject: Optional[str] = None
    title: Optional[str] = None
    passage_text: str

    class Config:
        from_attributes = True


# ---------- Questions / Quiz ----------
class QuestionPublic(BaseModel):
    """Question shape sent to the client BEFORE it's answered -- no correct_option."""
    id: int
    question_id: Optional[str] = None
    subject: Optional[str]
    topic: Optional[str]
    subtopic: Optional[str] = None
    difficulty: str
    question_text: str
    image_url: Optional[str] = None
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    year: Optional[str] = None
    passage: Optional[PassageOut] = None


class QuizStartIn(BaseModel):
    subject: Optional[str] = None
    topic: Optional[str] = None
    n: int = 5
    difficulty: Optional[str] = None  # easy | medium | hard
    year: Optional[str] = None
    per_q: Optional[int] = None


class BlitzStartIn(BaseModel):
    subject: str
    difficulty: Optional[str] = None  # easy | medium | hard


# ---------- Schools ----------
class SchoolOut(BaseModel):
    id: int
    slug: str
    name: str
    state: Optional[str] = None
    # community | claimed | verified. A student typing a name is a claim, not
    # the school's endorsement -- the UI must not present the two the same way.
    status: str


class SchoolJoinIn(BaseModel):
    school_id: Optional[int] = None
    name: Optional[str] = None
    state: Optional[str] = None


class SchoolLeaderboardEntry(BaseModel):
    rank: int
    school_id: int
    slug: str
    name: str
    state: Optional[str] = None
    status: str
    total_points: int
    active_members: int
    # The ranked figure. Normalised so the table is not a size ranking.
    points_per_member: float


class MySchoolOut(BaseModel):
    school: SchoolOut
    total_points: int
    active_members: int
    points_per_member: float
    # The ONLY individual figure in the schools API, and only ever the
    # requesting student's own. Never another child's.
    your_contribution: int
    state_rank: Optional[int] = None
    national_rank: Optional[int] = None
    last_week_national_rank: Optional[int] = None
    can_change_after: Optional[str] = None


# ---------- Insights ----------
class InsightOut(BaseModel):
    key: str
    icon: str
    text: str
    action_label: Optional[str] = None
    action_href: Optional[str] = None


class RushStateOut(BaseModel):
    """Live state of a Rush run -- score, strikes and the bar to beat."""
    attempt_id: int
    score: int
    strikes: int
    strikes_allowed: int
    finished: bool
    personal_best: int = 0


class MockStartIn(BaseModel):
    subjects: list[str]  # exactly 3 candidate-chosen subjects, sat alongside compulsory English


class SmartReviewStartIn(BaseModel):
    n: Optional[int] = None


# ---------- Mock exam free navigation ----------
# ---------- Daily Question ----------
class DailyQuestionOut(BaseModel):
    date: str
    question_id: int
    subject: Optional[str]
    topic: str
    question_text: str
    image_url: Optional[str]
    option_a: str
    option_b: str
    option_c: str
    option_d: str

    answered: bool
    your_answer: Optional[str] = None
    your_seconds: Optional[int] = None
    is_correct: Optional[bool] = None
    # Withheld until this student has answered -- see routers/daily_question.py.
    correct_option: Optional[str] = None
    explanation: Optional[str] = None

    answered_count: int = 0
    percent_correct: Optional[int] = None
    average_seconds: Optional[int] = None
    streak: int = 0


class DailyQuestionAnswerIn(BaseModel):
    selected_option: str
    answer_seconds: Optional[int] = Field(default=None, ge=0, le=86400)


class DailyQuestionResultOut(BaseModel):
    is_correct: bool
    correct_option: str
    explanation: Optional[str]
    your_seconds: Optional[int]
    answered_count: int
    percent_correct: Optional[int]
    average_seconds: Optional[int]
    # e.g. 88 -> "faster than 88% of students today". Null until enough people
    # have answered for the comparison to mean anything.
    faster_than_percent: Optional[int]
    streak: int


class MockAnswerIn(BaseModel):
    selected_option: Optional[str] = None  # None/empty = clear this answer
    # Seconds spent on this question since it was last opened. Accumulated
    # server-side across revisits (see routers/mock.py) because a mock exam
    # allows free navigation. Optional for older clients.
    answer_seconds: Optional[int] = Field(default=None, ge=0, le=86400)


class MockNavItem(BaseModel):
    index: int
    question_id: int
    answered: bool
    marked: bool


class MockNavOut(BaseModel):
    items: list[MockNavItem]
    finished: bool
    time_limit_seconds: Optional[int]
    started_at: datetime


class MockQuestionOut(BaseModel):
    index: int
    total: int
    question: QuestionPublic
    selected_option: Optional[str] = None
    marked: bool


class QuizAttemptOut(BaseModel):
    attempt_id: int
    mode: str
    total: int
    current_index: int
    time_limit_seconds: Optional[int]
    per_question_seconds: Optional[int]
    current_question: Optional[QuestionPublic]
    finished: bool
    score: int


class AnswerIn(BaseModel):
    question_id: int
    selected_option: Optional[str] = None  # None/omitted = timeout / no answer
    # Wall-clock seconds on this question, measured by the client. Optional so
    # older app builds (which don't send it) keep working -- their answers are
    # simply stored with no timing rather than rejected. Bounds here are a
    # first line of defence only; see quiz.clamp_answer_seconds for the real
    # clamp, which also handles nonsense the client may send in good faith
    # (a backgrounded tab, a phone that slept mid-question).
    answer_seconds: Optional[int] = Field(default=None, ge=0, le=86400)


class AnswerOut(BaseModel):
    is_correct: bool
    correct_option: str
    explanation: Optional[str]
    next: QuizAttemptOut


class ResultItem(BaseModel):
    question_id: int
    question_text: str
    image_url: Optional[str] = None
    selected_option: str
    correct_option: str
    is_correct: bool
    is_marked: bool
    explanation: Optional[str] = None
    # Named mistake type: sharp | solid | lucky | slip | gap | blunder.
    # Null for an unanswered question -- see app/answer_labels.py.
    label: Optional[str] = None
    label_title: Optional[str] = None
    label_message: Optional[str] = None
    label_tone: Optional[str] = None


class PersonalBestOut(BaseModel):
    """How this attempt compares with the student's best COMPARABLE attempt."""
    is_baseline: bool
    is_best: bool
    current_pct: int
    previous_best_pct: Optional[int] = None
    # Percentage POINTS, not percent: 62% -> 74% is +12 percentage points,
    # not a 12% improvement. Named explicitly so the UI cannot mislabel it.
    delta_points: Optional[int] = None
    attempts: int
    message: str


class AnswerQualityOut(BaseModel):
    """Chess.com-style review of a finished attempt."""
    # Weighted, so a lucky guess does not read the same as a clean answer.
    # Deliberately not equal to percent correct.
    accuracy: Optional[int] = None
    counts: dict[str, int] = {}
    # The single most actionable sentence about this attempt.
    headline: Optional[str] = None
    # Topics to send them to, drawn from slips first -- a lapse on known
    # material is the cheapest thing to fix.
    focus_topics: list[str] = []


class ResultsOut(BaseModel):
    score: int
    total: int
    items: list[ResultItem]
    personal_best: Optional[PersonalBestOut] = None
    quality: Optional[AnswerQualityOut] = None
    # So the results screen can link straight into more practice on a focus
    # topic without a second round-trip to work out which subject it was.
    subject: Optional[str] = None


class SubjectRatingOut(BaseModel):
    """
    A subject rating, as the student is allowed to see it.

    Note what is absent: the raw Glicko number. It stays internal on purpose.
    "I'm a 900 and my friend is a 1400" is the failure mode the predicted-score
    framing exists to avoid.
    """
    subject: str
    predicted_score: int
    range_low: int
    range_high: int
    provisional: bool
    answers_counted: int
    # Only ever rendered when positive. A fall is never announced on its own --
    # it must arrive attached to an action.
    week_delta: Optional[int] = None


# ---------- Dashboard ----------
class TopicStat(BaseModel):
    topic: str
    subject: Optional[str] = None
    correct: int
    total: int
    percentage: float


class PracticeDay(BaseModel):
    date: str  # ISO date
    label: str  # single-letter day label, e.g. "M"
    practiced: bool
    is_today: bool
    is_future: bool


class ScoreEstimate(BaseModel):
    available: bool
    projected_low: Optional[int] = None
    projected_high: Optional[int] = None
    based_on_answers: int
    message: Optional[str] = None


class UnfinishedAttempt(BaseModel):
    """A quiz the student started but never finished, so it can be resumed.

    Without this the attempt is effectively lost: nothing in the UI links back
    to an in-progress QuizAttempt, so closing the tab mid-quiz silently threw
    the progress away.
    """
    id: int
    mode: str
    subject: str | None
    answered: int
    total: int


class LevelOut(BaseModel):
    """Learning level derived from lifetime XP.

    Deliberately reported alongside, never instead of, mastery: the spec is
    explicit that XP measures participation and must not read as proof of
    academic understanding.
    """
    level: int
    title: str
    xp_into_level: int
    xp_for_next: int
    percent: int


class DashboardOut(BaseModel):
    points: int
    current_streak: int
    longest_streak: int
    streak_freezes: int
    daily_goal: int
    points_today: int
    goal_met: bool
    has_taken_diagnostic: bool
    topic_stats: list[TopicStat]
    review_count: int
    exam_years: list[str]
    recommended_topics: list[TopicStat] = []
    due_for_review_count: int = 0
    score_estimate: ScoreEstimate
    practice_days: list[PracticeDay] = []
    # Best single Blitz round, mirroring the Blitz leaderboard metric.
    blitz_best: int = 0
    unfinished_attempt: UnfinishedAttempt | None = None
    level: LevelOut | None = None
    # Second streak type: requires demonstrated accuracy, not just attendance.
    mastery_streak: int = 0
    longest_mastery_streak: int = 0


class DailyGoalIn(BaseModel):
    daily_goal: int = Field(ge=10, le=200)


# ---------- Achievements ----------
class AchievementOut(BaseModel):
    code: str
    title: str
    description: str
    icon: str
    earned: bool
    earned_at: Optional[datetime] = None
    newly_unlocked: bool = False
    # How close the student is, so a locked badge can show "17/25".
    progress: int = 0
    target: int = 1


class AchievementsOut(BaseModel):
    items: list[AchievementOut]
    newly_unlocked: list[str]


# ---------- Study planner ----------
class StudyPlanIn(BaseModel):
    exam_date: Optional[date] = None
    subjects: list[str]


class StudyPlanTask(BaseModel):
    date: str
    subject: str
    topic: Optional[str] = None
    question_count: int


class StudyPlanOut(BaseModel):
    configured: bool
    exam_date: Optional[str] = None
    subjects: list[str] = []
    days_until_exam: Optional[int] = None
    today: Optional[StudyPlanTask] = None
    week: list[StudyPlanTask] = []


# ---------- Flashcards ----------
class FlashcardOut(BaseModel):
    id: int
    question_text: str
    image_url: Optional[str] = None
    answer_text: str
    explanation: Optional[str] = None
    subject: Optional[str] = None
    topic: str


class FlashcardsOut(BaseModel):
    items: list[FlashcardOut]


# ---------- Lesson notes ----------
class GlossaryTerm(BaseModel):
    term: str
    definition: str


class LessonNoteOut(BaseModel):
    id: int
    subject: str
    topic: str
    title: str
    summary: Optional[str] = None
    glossary: list[GlossaryTerm] = []
    content_md: str
    related_topics: list[str] = []
    status: str
    helpful_count: int
    unhelpful_count: int
    updated_at: datetime
    is_read: bool = False
    my_feedback: Optional[bool] = None  # this user's current vote, if any


class NoteStatusItem(BaseModel):
    subject: str
    topic: str
    note_id: Optional[int] = None
    status: str  # "missing" | "draft" | "active"
    question_count: int


class NoteGenerateIn(BaseModel):
    subject: str
    topic: str
    force: bool = False  # regenerate even if a note already exists and isn't a draft


class NoteUpdateIn(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    glossary: Optional[list[GlossaryTerm]] = None
    content_md: Optional[str] = None
    related_topics: Optional[list[str]] = None
    status: Optional[str] = None  # draft | active


class NoteFeedbackIn(BaseModel):
    is_helpful: bool


class NoteTutorAskIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class NoteTutorAskOut(BaseModel):
    reply: str
    queries_remaining_today: int


class LearnSubjectProgress(BaseModel):
    subject: str
    total_topics: int
    read_topics: int
    percentage: float


class LearnHubOut(BaseModel):
    subjects: list[LearnSubjectProgress]


# ---------- Public homepage widgets ----------
class PublicQuestionOut(BaseModel):
    date: str  # ISO date this question is "for" -- stable all day, no auth/state needed
    subject: Optional[str] = None
    topic: str
    question_text: str
    image_url: Optional[str] = None
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    explanation: Optional[str] = None


# ---------- Guest (unauthenticated) practice ----------
class GuestQuestionOut(BaseModel):
    id: int  # not persisted anywhere server-side for a guest -- only used
    # client-side to key React list items, never sent back to the API.
    subject: str
    topic: str
    question_text: str
    image_url: Optional[str] = None
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    explanation: Optional[str] = None


class GuestPracticeOut(BaseModel):
    subject: str
    questions: list[GuestQuestionOut]


# ---------- Payments (Paystack) ----------
class PaymentInitializeOut(BaseModel):
    authorization_url: str
    reference: str


class PremiumStatusOut(BaseModel):
    is_premium: bool
    premium_until: Optional[datetime] = None
    free_mock_exams_remaining: int


# ---------- Family / guardian links (Phase 5) ----------
class MyCodeOut(BaseModel):
    code: str


class LinkIn(BaseModel):
    code: str = Field(min_length=1, max_length=16)


class LinkedChildOut(BaseModel):
    id: int
    username: str
    current_streak: int
    points: int
    linked_at: datetime


class ChildSummaryOut(BaseModel):
    id: int
    username: str
    points: int
    current_streak: int
    longest_streak: int
    topic_stats: list[TopicStat]
    recommended_topics: list[TopicStat]
    score_estimate: ScoreEstimate


class TopStudentEntry(BaseModel):
    rank: int
    username: str
    points: int
    current_streak: int


class TopStudentsOut(BaseModel):
    entries: list[TopStudentEntry]


# ---------- AI tutor ----------
class TutorAskIn(BaseModel):
    question_id: int
    message: str = Field(min_length=1, max_length=500)


class TutorAskOut(BaseModel):
    reply: str
    queries_remaining_today: int


# ---------- Push notifications ----------
class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeIn(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class PushUnsubscribeIn(BaseModel):
    endpoint: str


class VapidPublicKeyOut(BaseModel):
    public_key: str
    configured: bool


class SendRemindersOut(BaseModel):
    eligible_users: int
    sent: int
    expired_removed: int
    failed: int


# ---------- Admin ----------
class SuggestTagsIn(BaseModel):
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str


class SuggestTagsOut(BaseModel):
    subject: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    difficulty: Optional[str] = None
    note: Optional[str] = None



class QuestionIn(BaseModel):
    question_id: str = Field(min_length=1, max_length=50)
    subject: str
    topic: str
    subtopic: Optional[str] = None
    difficulty: str = "medium"  # easy | medium | hard
    exam_type: Optional[str] = None
    year: Optional[str] = None
    passage_id: Optional[str] = None
    question_text: str
    image_url: Optional[str] = None
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    explanation: Optional[str] = None
    tags: Optional[str] = None
    source: str = "original"  # original | past-question | licensed
    status: str = "active"  # active | draft


class QuestionOut(QuestionIn):
    id: int

    class Config:
        from_attributes = True


class AdminStats(BaseModel):
    total_questions: int
    total_users: int
    subjects: list[str]


# ---------- Admin: Analytics ----------
class CohortOut(BaseModel):
    week_start: str
    signups: int
    # Answered at least one question, ever. The rest never started.
    activated: int
    # Percentage returning at each checkpoint. NULL means the cohort is too
    # young to have an answer -- reporting 0 would make every recent week look
    # like a failure.
    d1: Optional[int] = None
    d7: Optional[int] = None
    d14: Optional[int] = None


class FunnelOut(BaseModel):
    signups: int
    answered_one: int
    answered_ten: int
    completed_attempt: int
    median_seconds_to_first_question: Optional[int] = None
    # Share reaching their first question inside the 90s target.
    within_target_pct: Optional[int] = None


class DailySignupOut(BaseModel):
    date: str
    signups: int
    activated: int


class AnalyticsOut(BaseModel):
    # The single number the teacher trial exists to produce.
    week_two_return_pct: Optional[int] = None
    cohorts_measured: int = 0
    students_measured: int = 0
    time_to_value_target_seconds: int
    cohorts: list[CohortOut] = []
    funnel: FunnelOut
    daily: list[DailySignupOut] = []


# ---------- Admin: Users ----------
class AdminUserOut(BaseModel):
    id: int
    username: str
    email: str
    points: int
    is_admin: bool
    current_streak: int
    longest_streak: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Leaderboard ----------
class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    points: int
    current_streak: int
    is_you: bool


class LeaderboardOut(BaseModel):
    entries: list[LeaderboardEntry]
    your_rank: int
    your_points: int


# ---------- Quest Map ----------
class QuestTopicOut(BaseModel):
    topic: str
    description: str | None = None
    estimated_minutes: int
    # locked | available | learning | practising | proficient | mastered | review_due
    state: str
    stars: int
    mastery_score: int
    prerequisite: str | None = None
    can_test_out: bool = False
    next_review_at: str | None = None


class QuestMapOut(BaseModel):
    subject: str
    total_topics: int
    mastered_topics: int
    review_due_topics: int
    percent_complete: int
    recommended_topic: str | None = None
    # Echoed so the client shows the same thresholds the server enforces,
    # even after an admin changes them -- the Android shell may be an old build.
    practice_pass_pct: int
    challenge_pass_pct: int
    topics: list[QuestTopicOut]


# ---------- Daily missions ----------
class DailyMissionOut(BaseModel):
    kind: str  # progress | practice | improvement
    title: str
    subject: str | None = None
    topic: str | None = None
    target: int
    progress: int
    completed: bool
    estimated_minutes: int
    action_path: str | None = None


class DailyMissionsOut(BaseModel):
    local_date: str
    items: list[DailyMissionOut]
    all_complete: bool
    # Disclosed up front rather than revealed on opening -- the spec rules out
    # gambling-style reward mechanics.
    reward_xp: int
    reward_claimed: bool
    total_minutes: int


# ---------- Weekly leagues ----------
class LeagueEntryOut(BaseModel):
    rank: int
    # Self-chosen username only. Never email, school or location.
    username: str
    points: int
    is_you: bool
    zone: str  # promotion | safe | demotion


class LeagueOut(BaseModel):
    opted_out: bool
    tier: str
    tier_label: str
    week_start: str
    days_remaining: int
    your_rank: Optional[int] = None
    your_points: int = 0
    entries: list[LeagueEntryOut] = []
    promote_top: int
    demote_bottom: int


class LeagueOptIn(BaseModel):
    opted_out: bool


# ---------- Quiz battles ----------
class BattleCreateIn(BaseModel):
    subject: str
    topic: Optional[str] = None
    questions: int = 5  # 5 or 10
    mode: str = "async"  # async | live
    # Play a calibrated practice opponent instead of waiting for a human.
    # Solves the 10pm-with-no-friends-online case; see app/bots.py.
    vs_bot: bool = False


class RecentOpponentOut(BaseModel):
    """
    Someone this student has already played.

    Deliberately thin: a username, the subject and when. No profile, no
    rating, no way to reach them outside a battle -- see app/matchmaking.py
    for why this is the only shape of social graph the app offers.
    """
    user_id: int
    username: str
    subject: str
    last_played: Optional[str] = None
    played: int = 1


class BattleAnswerIn(BaseModel):
    selected: Optional[str] = None
    seconds: Optional[int] = None


class BattleSubmitIn(BaseModel):
    # question_id -> answer. Graded server-side; the client's own idea of
    # correctness is never trusted.
    answers: dict[str, BattleAnswerIn] = {}


class BattleQuestionOut(BaseModel):
    """Battle question as sent BEFORE submission -- deliberately no
    correct_option and no explanation, so neither can be read from the
    network response mid-battle."""
    id: int
    question_text: str
    image_url: Optional[str] = None
    option_a: str
    option_b: str
    option_c: str
    option_d: str


class BattleOut(BaseModel):
    code: str
    subject: str
    topic: Optional[str] = None
    questions: int
    seconds_per_question: int
    status: str
    expires_at: str
    players: int
    you_submitted: bool
    mode: str = "async"
    started_at: Optional[str] = None
    vs_bot: bool = False


class BattleSideOut(BaseModel):
    username: str
    score: int
    attempted: int
    submitted: bool
    avg_correct_seconds: Optional[int] = None
    # Always sent, never inferred from the name. Every surface that renders an
    # opponent must be able to say plainly that this one is not a person.
    is_bot: bool = False
    bot_blurb: Optional[str] = None


class BattleResultOut(BaseModel):
    code: str
    subject: str
    status: str
    # Included so the client can tell live from async WITHOUT calling join --
    # a read must never have the side effect of entering a battle.
    mode: str = "async"
    outcome: str  # waiting | won | lost | draw
    you: BattleSideOut
    opponent: Optional[BattleSideOut] = None
    review: list[dict] = []
    # True when the opponent was a practice bot. Such a result never counts
    # toward league points or leaderboards -- see routers/battles.py.
    vs_bot: bool = False


class BattleLiveOut(BaseModel):
    """
    Live battle state, computed entirely from the server clock.

    `current_index` and `seconds_remaining` are derived from Battle.started_at
    rather than exchanged in messages, so both players are always on the same
    question and no client clock can affect pacing.
    """
    code: str
    started: bool
    current_index: Optional[int] = None
    # The client MUST select the question by this id, not by indexing its own
    # list at current_index. /questions silently omits any question deleted
    # since the battle was created, which shortens that list and slides every
    # later position -- so the student would be shown one question and graded
    # on another. Positions are not a shared coordinate system; ids are.
    current_question_id: Optional[int] = None
    seconds_remaining: Optional[int] = None
    total: int
    finished: bool
    you_answered: int
    opponent_answered: int
    # Presentational only -- a dropped connection never forfeits a battle.
    opponent_present: bool


class BattleLiveAnswerIn(BaseModel):
    index: int
    selected: Optional[str] = None
