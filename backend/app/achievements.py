"""
Duolingo-style achievement badges. Each entry defines a stable `code` (used
as the DB key in UserAchievement), display copy, and a `check(db, user)`
predicate. Achievements are evaluated on-demand (see routers/achievements.py)
rather than after every answer, and persisted the first time they're earned
so earned_at stays stable and we can report which ones were *just* unlocked.
"""
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    LearningEvent, PersonalBest, QuestionMastery, QuizAttempt, TopicMastery,
    UserResponse, User,
)
from app.gamification import config
from app.subjects import SUBJECTS


# ---------------------------------------------------------------------------
# Learning-based helpers (spec section 7).
#
# The original badges were ACTIVITY-based -- answer a question, keep a streak.
# The spec asks for achievements that "describe something worth being proud
# of", which means measuring what a student has LEARNED, not how long they
# spent. These read from TopicMastery and the LearningEvent ledger rather than
# counting raw answers.
# ---------------------------------------------------------------------------


def _mastered_topics(db: Session, user_id: int, subject: str | None = None) -> int:
    q = db.query(func.count(TopicMastery.id)).filter(
        TopicMastery.user_id == user_id, TopicMastery.mastered_at.isnot(None)
    )
    if subject:
        q = q.filter(TopicMastery.subject == subject)
    return q.scalar() or 0


def _proficient_subjects(db: Session, user_id: int) -> int:
    """Subjects with at least one topic at proficiency or better."""
    rows = (
        db.query(TopicMastery.subject)
        .filter(TopicMastery.user_id == user_id, TopicMastery.proficient_at.isnot(None))
        .distinct()
        .all()
    )
    return len(rows)


def _subject_mastery_ratio(db: Session, user_id: int) -> float:
    """Best per-subject fraction of topics mastered."""
    rows = db.query(TopicMastery).filter(TopicMastery.user_id == user_id).all()
    if not rows:
        return 0.0
    by_subject: dict[str, list[TopicMastery]] = {}
    for r in rows:
        by_subject.setdefault(r.subject, []).append(r)
    best = 0.0
    for topics in by_subject.values():
        mastered = sum(1 for t in topics if t.mastered_at)
        best = max(best, mastered / len(topics))
    return best


def _event_count(db: Session, user_id: int, event_type: str) -> int:
    """Counts from the ledger, so a replayed event cannot inflate progress."""
    return (
        db.query(func.count(LearningEvent.id))
        .filter(
            LearningEvent.user_id == user_id,
            LearningEvent.event_type == event_type,
            LearningEvent.reversed_at.is_(None),
        )
        .scalar()
        or 0
    )


def _personal_bests_beaten(db: Session, user_id: int) -> int:
    """Comparable activities where the student has improved on their baseline."""
    return (
        db.query(func.count(PersonalBest.id))
        .filter(
            PersonalBest.user_id == user_id,
            PersonalBest.attempts > 1,
            PersonalBest.best_pct > PersonalBest.baseline_pct,
        )
        .scalar()
        or 0
    )


@dataclass
class Achievement:
    """
    One badge.

    Most achievements are "reach N of something", so they are defined by a
    `metric` (how much the student has) plus a `target` (how much they need).
    That single change gives three things at once: an earned/not-earned
    decision, a progress bar for the gallery, and a threshold an admin can
    retune from settings without a deploy.

    `check` remains for the handful that are genuinely boolean (did they ever
    score 100%?) and cannot be expressed as a count.

    NOTE on "admin-configurable achievements": thresholds are configurable;
    the PREDICATES are not, and deliberately so. Storing executable rules in
    the database would mean evaluating user-supplied code at runtime, which is
    a remote-code-execution hazard dressed up as a feature. Adding a genuinely
    new KIND of achievement is a code change, and should be.
    """
    code: str
    title: str
    description: str
    icon: str  # Font Awesome class
    check: Callable[[Session, User], bool] | None = None
    metric: Callable[[Session, User], int] | None = None
    target: int = 1
    # Settings key that can override `target` at runtime.
    threshold_key: str | None = None

    def resolve_target(self, db: Session) -> int:
        if self.threshold_key:
            try:
                return config.get(db, self.threshold_key)
            except KeyError:
                return self.target
        return self.target

    def progress(self, db: Session, user: User) -> tuple[int, int]:
        """(current, target). Boolean achievements report 0/1 or 1/1."""
        target = self.resolve_target(db)
        if self.metric is not None:
            return min(self.metric(db, user), target), target
        earned = bool(self.check and self.check(db, user))
        return (1 if earned else 0), 1

    def is_earned(self, db: Session, user: User) -> bool:
        current, target = self.progress(db, user)
        return current >= target


def _answered_count(db: Session, user_id: int) -> int:
    return db.query(func.count(UserResponse.id)).filter(UserResponse.user_id == user_id).scalar() or 0


def _has_finished_mode(db: Session, user_id: int, mode: str) -> bool:
    return (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == user_id, QuizAttempt.mode == mode, QuizAttempt.finished_at.isnot(None))
        .first()
        is not None
    )


def _has_perfect_score(db: Session, user_id: int, min_questions: int = 10) -> bool:
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == user_id, QuizAttempt.finished_at.isnot(None))
        .all()
    )
    for a in attempts:
        total = len(a.question_ids or [])
        if total >= min_questions and a.score == total:
            return True
    return False


def _subjects_with_correct_answer(db: Session, user_id: int) -> set[str]:
    rows = (
        db.query(UserResponse)
        .join(UserResponse.question)
        .filter(UserResponse.user_id == user_id, UserResponse.is_correct.is_(True))
        .all()
    )
    return {r.question.subject for r in rows if r.question.subject}


ACHIEVEMENTS: list[Achievement] = [
    Achievement(
        code="first_quiz",
        title="First Steps",
        description="Answer your first question.",
        icon="fa-solid fa-shoe-prints",
        metric=lambda db, user: _answered_count(db, user.id),
        target=1,
    ),
    Achievement(
        code="streak_3",
        title="On a Roll",
        description="Reach a 3-day practice streak.",
        icon="fa-solid fa-fire",
        metric=lambda db, user: user.longest_streak or 0,
        target=3,
        threshold_key="ach_streak_short",
    ),
    Achievement(
        code="streak_7",
        title="Week Warrior",
        description="Reach a 7-day practice streak.",
        icon="fa-solid fa-fire-flame-curved",
        metric=lambda db, user: user.longest_streak or 0,
        target=7,
        threshold_key="ach_streak_week",
    ),
    Achievement(
        code="streak_30",
        title="Unstoppable",
        description="Reach a 30-day practice streak.",
        icon="fa-solid fa-crown",
        metric=lambda db, user: user.longest_streak or 0,
        target=30,
        threshold_key="ach_streak_month",
    ),
    Achievement(
        code="century",
        title="Century Club",
        description="Answer 100 questions in total.",
        icon="fa-solid fa-medal",
        metric=lambda db, user: _answered_count(db, user.id),
        target=100,
        threshold_key="ach_answers_century",
    ),
    Achievement(
        code="perfectionist",
        title="Perfectionist",
        description="Score 100% on a quiz of 10+ questions.",
        icon="fa-solid fa-star",
        check=lambda db, user: _has_perfect_score(db, user.id),
    ),
    Achievement(
        code="blitz_master",
        title="Blitz Master",
        description="Complete a Blitz Challenge round.",
        icon="fa-solid fa-bolt",
        check=lambda db, user: _has_finished_mode(db, user.id, "blitz"),
    ),
    Achievement(
        code="mock_marathon",
        title="Mock Marathon",
        description="Complete a Full JAMB Mock exam.",
        icon="fa-solid fa-file-signature",
        check=lambda db, user: _has_finished_mode(db, user.id, "mock"),
    ),
    Achievement(
        code="well_rounded",
        title="Well Rounded",
        description="Answer a question correctly in every subject.",
        icon="fa-solid fa-globe",
        metric=lambda db, user: len(_subjects_with_correct_answer(db, user.id)),
        target=len(SUBJECTS),
    ),
    # ---- Learning-based (spec section 7) ---------------------------------
    # Each of these describes an academic accomplishment rather than time
    # spent, so the badge means something a student can be proud of.

    # Mastery
    Achievement(
        code="subject_scholar",
        title="Subject Scholar",
        description="Master 80% of the topics in one subject.",
        icon="fa-solid fa-graduation-cap",
        check=lambda db, user: _subject_mastery_ratio(db, user.id) >= 0.8,
    ),
    Achievement(
        code="all_rounder",
        title="All-Rounder",
        description="Reach proficiency in five different subjects.",
        icon="fa-solid fa-circle-nodes",
        metric=lambda db, user: _proficient_subjects(db, user.id),
        target=5,
        threshold_key="ach_all_rounder_subjects",
    ),
    Achievement(
        code="first_mastery",
        title="Topic Mastered",
        description="Master your first topic.",
        icon="fa-solid fa-trophy",
        metric=lambda db, user: _mastered_topics(db, user.id),
        target=1,
    ),

    # Improvement -- the category that matters most for weaker students,
    # because it rewards getting better rather than being good already.
    Achievement(
        code="comeback_scholar",
        title="Comeback Scholar",
        description="Correctly answer 25 questions you previously got wrong.",
        icon="fa-solid fa-arrow-rotate-left",
        metric=lambda db, user: _event_count(db, user.id, "MISTAKE_CORRECTED"),
        target=25,
        threshold_key="ach_comeback_corrections",
    ),
    Achievement(
        code="personal_best",
        title="Personal Best",
        description="Beat your own baseline on a comparable activity.",
        icon="fa-solid fa-arrow-trend-up",
        metric=lambda db, user: _personal_bests_beaten(db, user.id),
        target=1,
    ),

    # Consistency -- uses the MASTERY streak, not attendance, so the badge
    # cannot be earned by opening the app daily without learning anything.
    Achievement(
        code="consistency_champion",
        title="Consistency Champion",
        description="Reach a 7-day mastery streak — seven days of accurate work.",
        icon="fa-solid fa-calendar-check",
        metric=lambda db, user: user.longest_mastery_streak or 0,
        target=7,
        threshold_key="ach_mastery_streak",
    ),

    # Practice and assessment
    Achievement(
        code="review_expert",
        title="Review Expert",
        description="Successfully complete 20 due reviews.",
        icon="fa-solid fa-clock-rotate-left",
        metric=lambda db, user: _event_count(db, user.id, "REVIEW_COMPLETED"),
        target=20,
        threshold_key="ach_reviews",
    ),
    Achievement(
        code="dedicated_learner",
        title="Dedicated Learner",
        description="Complete all your daily missions on 20 different days.",
        icon="fa-solid fa-list-check",
        metric=lambda db, user: _event_count(db, user.id, "MISSION_COMPLETED"),
        target=20,
        threshold_key="ach_mission_days",
    ),
]
