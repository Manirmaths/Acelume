"""
The learning-event service: the single entry point every gamification feature
reads from.

The spec's central requirement is that one validated event updates several
systems, so each feature does not recompute progress its own way:

    Question answered -> mastery, XP, mission progress, league points
    Topic mastered    -> quest map, XP, league, achievements
    Review completed  -> mastery, XP, streak, daily mission

`record()` is the only supported way to write a learning event. It is
idempotent on `event_key`, so a retried request, a double-tapped button or a
re-synced offline queue cannot be rewarded twice.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.gamification import config
from app.gamification.idempotency import insert_if_new
from app.models import LearningEvent, TopicMastery, User, XpLedger

# Event types (spec: "Shared technical architecture")
LESSON_COMPLETED = "LESSON_COMPLETED"
QUESTION_ANSWERED = "QUESTION_ANSWERED"
MISTAKE_CORRECTED = "MISTAKE_CORRECTED"
PRACTICE_COMPLETED = "PRACTICE_COMPLETED"
TOPIC_PROFICIENT = "TOPIC_PROFICIENT"
TOPIC_MASTERED = "TOPIC_MASTERED"
REVIEW_COMPLETED = "REVIEW_COMPLETED"
MOCK_COMPLETED = "MOCK_COMPLETED"
MISSION_COMPLETED = "MISSION_COMPLETED"
BATTLE_COMPLETED = "BATTLE_COMPLETED"

# event_type -> (settings key for XP, human-readable reason)
XP_RULES: dict[str, tuple[str, str]] = {
    LESSON_COMPLETED: ("xp_lesson_completed", "Lesson completed"),
    QUESTION_ANSWERED: ("xp_correct_answer", "Correct answer"),
    MISTAKE_CORRECTED: ("xp_mistake_corrected", "Mistake corrected"),
    REVIEW_COMPLETED: ("xp_review_passed", "Review passed"),
    TOPIC_PROFICIENT: ("xp_topic_proficient", "Topic proficiency reached"),
    TOPIC_MASTERED: ("xp_topic_mastered", "Topic mastered"),
    MOCK_COMPLETED: ("xp_mock_completed", "Mock exam completed"),
    MISSION_COMPLETED: ("xp_all_missions", "All daily missions completed"),
}

# Answer-level events are the farmable ones, so only these count toward the
# daily XP cap. Mastering a topic or sitting a mock is self-limiting.
CAPPED_EVENT_TYPES = {QUESTION_ANSWERED, MISTAKE_CORRECTED}


def _daily_capped_xp(db: Session, user_id: int, now: datetime) -> int:
    """XP already granted today from farmable activity."""
    start = datetime.combine(now.date(), datetime.min.time())
    reasons = [XP_RULES[t][1] for t in CAPPED_EVENT_TYPES]
    total = (
        db.query(func.coalesce(func.sum(XpLedger.amount), 0))
        .filter(
            XpLedger.user_id == user_id,
            XpLedger.created_at >= start,
            XpLedger.reason.in_(reasons),
        )
        .scalar()
    )
    return int(total or 0)


def record(
    db: Session,
    *,
    user: User,
    event_type: str,
    event_key: str,
    subject: str | None = None,
    topic: str | None = None,
    source_id: str | None = None,
    payload: dict[str, Any] | None = None,
    award_xp: bool = True,
) -> LearningEvent | None:
    """
    Record a validated learning event, awarding XP as a side effect.

    Returns the created event, or None if `event_key` was already recorded --
    callers can treat None as "already handled" rather than an error, which is
    exactly what a retry or an offline re-sync should do.

    The caller is responsible for deciding an event is *valid* (e.g. that the
    answer really was correct and really was a first attempt). This function is
    responsible for making sure a valid event is recorded and rewarded once.
    """
    if event_type not in XP_RULES and event_type not in (
        PRACTICE_COMPLETED,
        BATTLE_COMPLETED,
    ):
        raise ValueError(f"Unknown event_type: {event_type}")

    existing = db.query(LearningEvent).filter(LearningEvent.event_key == event_key).first()
    if existing is not None:
        return None

    now = datetime.utcnow()
    event = LearningEvent(
        user_id=user.id,
        event_type=event_type,
        event_key=event_key,
        subject=subject,
        topic=topic,
        source_id=source_id,
        payload=payload or {},
        occurred_at=now,
        recorded_at=now,
    )
    # Insert inside a SAVEPOINT so the UNIQUE constraint -- not an
    # application-level check -- settles concurrent duplicates. Two
    # simultaneous requests with the same key race past the SELECT above; only
    # one survives, and the loser undoes ONLY this row rather than the caller's
    # whole transaction. See idempotency.insert_if_new.
    if not insert_if_new(db, event):
        return None

    if award_xp and event_type in XP_RULES:
        _award_xp(db, user=user, event=event, event_type=event_type, now=now)

    # Weekly league points. Imported here rather than at module scope to keep
    # the dependency one-way: leagues reads config and models, and calling it
    # from the top of this file would create an import cycle.
    from app.gamification import leagues

    leagues.award(
        db, user,
        event_type=event_type,
        event_key=event_key,
        hard=bool((payload or {}).get("difficulty") == "hard"),
    )

    return event


def _award_xp(db: Session, *, user: User, event: LearningEvent, event_type: str, now: datetime) -> None:
    key, reason = XP_RULES[event_type]
    amount = config.get(db, key)
    if amount <= 0:
        return

    if event_type in CAPPED_EVENT_TYPES:
        cap = config.get(db, "xp_daily_answer_cap")
        used = _daily_capped_xp(db, user.id, now)
        if used >= cap:
            return
        amount = min(amount, cap - used)

    ledger = XpLedger(
        user_id=user.id,
        event_id=event.id,
        amount=amount,
        reason=reason,
        ledger_key=f"xp:{event.event_key}",
    )
    if not insert_if_new(db, ledger):
        return

    # Running total kept on User for cheap reads; the ledger is the truth.
    user.points = (user.points or 0) + amount


# ---------------------------------------------------------------------------
# Topic mastery
# ---------------------------------------------------------------------------

REVIEW_INTERVAL_KEYS = [
    "review_interval_1_days",
    "review_interval_2_days",
    "review_interval_3_days",
    "review_interval_4_days",
]


def get_or_create_topic(db: Session, user_id: int, subject: str, topic: str) -> TopicMastery:
    row = (
        db.query(TopicMastery)
        .filter(
            TopicMastery.user_id == user_id,
            TopicMastery.subject == subject,
            TopicMastery.topic == topic,
        )
        .first()
    )
    if row is None:
        row = TopicMastery(user_id=user_id, subject=subject, topic=topic, state="available")
        db.add(row)
        db.flush()
    return row


def schedule_next_review(db: Session, row: TopicMastery, now: datetime | None = None) -> None:
    """Advance the topic through the 3/7/21/45-day review ladder."""
    now = now or datetime.utcnow()
    stage = min(row.review_stage, len(REVIEW_INTERVAL_KEYS) - 1)
    days = config.get(db, REVIEW_INTERVAL_KEYS[stage])
    row.last_reviewed_at = now
    row.next_review_at = now + timedelta(days=days)
    row.review_stage = min(row.review_stage + 1, len(REVIEW_INTERVAL_KEYS) - 1)


def record_practice_result(
    db: Session,
    *,
    user: User,
    subject: str,
    topic: str,
    correct: int,
    total: int,
    attempt_id: int,
    timed: bool,
) -> list[str]:
    """
    Fold a finished single-topic attempt into that topic's mastery, promoting
    it to proficient or mastered if the thresholds are met.

    Returns the milestones reached, so the caller can surface them in the UI.

    Only single-topic attempts count. A mixed-topic quiz says nothing reliable
    about any one topic, and crediting it would let a student "master" a topic
    they barely touched.

    The Master stage requires a TIMED attempt (spec: timed challenge, no
    hints); an untimed practice run can reach proficient but never mastered,
    however high the score.
    """
    if total <= 0:
        return []

    pct = round(100 * correct / total)
    row = get_or_create_topic(db, user.id, subject, topic)
    row.practice_attempts += 1
    milestones: list[str] = []

    min_practice = config.get(db, "practice_min_questions")
    pass_practice = config.get(db, "practice_pass_pct")
    min_challenge = config.get(db, "challenge_min_questions")
    pass_challenge = config.get(db, "challenge_pass_pct")

    if total >= min_practice:
        row.best_practice_pct = max(row.best_practice_pct, pct)
    if timed and total >= min_challenge:
        row.best_challenge_pct = max(row.best_challenge_pct, pct)

    # mastery_score tracks CURRENT understanding, so it follows the latest
    # attempt rather than the best one -- it is allowed to fall.
    row.mastery_score = pct

    now = datetime.utcnow()

    if (
        row.proficient_at is None
        and total >= min_practice
        and pct >= pass_practice
    ):
        row.proficient_at = now
        row.stars = max(row.stars, 2)
        milestones.append(TOPIC_PROFICIENT)
        record(
            db, user=user, event_type=TOPIC_PROFICIENT,
            event_key=f"{TOPIC_PROFICIENT}:{subject}:{topic}",
            subject=subject, topic=topic, source_id=str(attempt_id),
            payload={"pct": pct, "questions": total},
        )

    if (
        row.mastered_at is None
        and timed
        and total >= min_challenge
        and pct >= pass_challenge
    ):
        row.mastered_at = now
        row.stars = 3
        # Proficiency is implied by mastery -- a student who masters a topic
        # without a separate practice run should not be stuck on two stars.
        if row.proficient_at is None:
            row.proficient_at = now
        milestones.append(TOPIC_MASTERED)
        record(
            db, user=user, event_type=TOPIC_MASTERED,
            event_key=f"{TOPIC_MASTERED}:{subject}:{topic}",
            subject=subject, topic=topic, source_id=str(attempt_id),
            payload={"pct": pct, "questions": total},
        )
        schedule_next_review(db, row, now)
    elif row.mastered_at is not None:
        # A mastered topic practised again counts as a completed review.
        schedule_next_review(db, row, now)

    refresh_state(db, row, now)
    return milestones


def refresh_state(db: Session, row: TopicMastery, now: datetime | None = None) -> str:
    """
    Recompute the topic's state from its stored evidence.

    Deliberately does NOT drop stars when review falls due -- the spec is
    explicit that a student who has earned mastery keeps the visible credit and
    is simply asked to refresh it.
    """
    now = now or datetime.utcnow()
    if row.mastered_at and row.next_review_at and row.next_review_at <= now:
        row.state = "review_due"
    elif row.mastered_at:
        row.state = "mastered"
    elif row.proficient_at:
        row.state = "proficient"
    elif row.practice_attempts > 0:
        row.state = "practising"
    elif row.lesson_completed_at:
        row.state = "learning"
    elif row.state != "locked":
        row.state = "available"
    row.updated_at = now
    return row.state
