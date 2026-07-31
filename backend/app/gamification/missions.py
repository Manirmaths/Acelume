"""
Daily Missions: three personalised tasks per student per day.

The point of missions is to remove the decision "what should I study today?",
which is the moment most students give up. So a mission must always be
*possible* with the content that student actually has: never a locked topic,
never a subject with no questions, never three of the same shape.

Progress is derived from validated learning events rather than claimed by the
student, and the reward is guarded by a UNIQUE constraint so the same day can
never pay out twice.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.gamification import config, events
from app.models import (
    DailyMission,
    DailyReward,
    Question,
    QuestionMastery,
    SyllabusTopic,
    TopicMastery,
    User,
    UserResponse,
)

PROGRESS = "progress"
PRACTICE = "practice"
IMPROVEMENT = "improvement"

# Kept modest deliberately. The spec budgets 15-30 minutes for all three, and
# a mission a student cannot finish in a sitting is worse than no mission --
# it teaches them the list is not achievable.
PRACTICE_QUESTIONS = 15
IMPROVEMENT_CORRECTIONS = 5
# A brand-new student gets a gentler version of each.
NEW_STUDENT_PRACTICE = 8


def _answered_count(db: Session, user_id: int) -> int:
    return db.query(func.count(UserResponse.id)).filter(UserResponse.user_id == user_id).scalar() or 0


def _available_topics(db: Session, user: User) -> list[tuple[SyllabusTopic, TopicMastery | None]]:
    """
    Topics the student may actually work on right now.

    Excludes locked topics, which is the spec's hardest rule to get right: a
    mission pointing at content the student cannot open is worse than having
    no mission at all.
    """
    syllabus = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.active.is_(True))
        .order_by(SyllabusTopic.subject, SyllabusTopic.order_index)
        .all()
    )
    if not syllabus:
        return []

    mastery = {
        (m.subject, m.topic): m
        for m in db.query(TopicMastery).filter(TopicMastery.user_id == user.id)
    }
    by_id = {t.id: t for t in syllabus}

    out: list[tuple[SyllabusTopic, TopicMastery | None]] = []
    for t in syllabus:
        row = mastery.get((t.subject, t.topic))
        if t.prerequisite_id:
            prereq = by_id.get(t.prerequisite_id)
            prereq_row = mastery.get((prereq.subject, prereq.topic)) if prereq else None
            unlocked = bool(prereq_row and prereq_row.proficient_at)
            started = bool(row and (row.lesson_completed_at or row.practice_attempts))
            if not unlocked and not started:
                continue
        out.append((t, row))
    return out


def _subject_with_questions(db: Session, exclude: set[str]) -> str | None:
    row = (
        db.query(Question.subject, func.count(Question.id).label("n"))
        .filter(Question.status == "active")
        .group_by(Question.subject)
        .order_by(func.count(Question.id).desc())
        .all()
    )
    for subject, _ in row:
        if subject and subject not in exclude:
            return subject
    return row[0][0] if row else None


def _missed_question_count(db: Session, user_id: int) -> int:
    """Questions the student has seen and got wrong at least once."""
    return (
        db.query(func.count(QuestionMastery.id))
        .filter(
            QuestionMastery.user_id == user_id,
            QuestionMastery.times_seen > 0,
            QuestionMastery.times_correct < QuestionMastery.times_seen,
        )
        .scalar()
        or 0
    )


def generate_for_day(db: Session, user: User, local_date: date) -> list[DailyMission]:
    """
    Build (or return the existing) three missions for this student's day.

    Idempotent: the UNIQUE (user, date, kind) constraint means a repeated call
    -- including two concurrent requests on first page load, or a student
    flipping timezone back and forth -- cannot mint extra missions.
    """
    existing = (
        db.query(DailyMission)
        .filter(DailyMission.user_id == user.id, DailyMission.local_date == local_date)
        .all()
    )
    if existing:
        return sorted(existing, key=lambda m: m.kind)

    answered = _answered_count(db, user.id)
    is_new = answered < 20
    topics = _available_topics(db, user)
    used_subjects: set[str] = set()
    missions: list[DailyMission] = []

    # 1. Progress -- continue something started, else start something new.
    started = [(t, r) for t, r in topics if r and r.lesson_completed_at and not r.proficient_at]
    target_topic = started[0] if started else (topics[0] if topics else None)
    if target_topic:
        t, row = target_topic
        continuing = bool(row and row.lesson_completed_at)
        missions.append(DailyMission(
            user_id=user.id, local_date=local_date, kind=PROGRESS,
            title=("Keep going with " if continuing else "Start ") + t.topic,
            subject=t.subject, topic=t.topic, target=1,
            estimated_minutes=min(t.estimated_minutes, 20),
            action_path=f"/subjects/{t.subject}/topics/{t.topic}",
        ))
        used_subjects.add(t.subject)

    # 2. Practice -- a different subject where possible, so a day is not three
    #    missions deep in one subject.
    subject = _subject_with_questions(db, exclude=used_subjects)
    if subject:
        n = NEW_STUDENT_PRACTICE if is_new else PRACTICE_QUESTIONS
        missions.append(DailyMission(
            user_id=user.id, local_date=local_date, kind=PRACTICE,
            title=f"Answer {n} {subject} questions",
            subject=subject, target=n,
            estimated_minutes=max(5, n // 2),
            action_path=f"/quiz?subject={subject}&n={n}",
        ))
        used_subjects.add(subject)

    # 3. Improvement -- correct past mistakes, or review, or (for a student
    #    with no history yet) simply read a lesson. A brand-new student has
    #    nothing to improve, and asking them to fix mistakes they have not
    #    made would be an impossible mission.
    missed = _missed_question_count(db, user.id)
    due = [t for t, r in topics if r and r.next_review_at and r.next_review_at <= datetime.utcnow()]
    if missed >= IMPROVEMENT_CORRECTIONS:
        missions.append(DailyMission(
            user_id=user.id, local_date=local_date, kind=IMPROVEMENT,
            title=f"Correct {IMPROVEMENT_CORRECTIONS} questions you previously missed",
            target=IMPROVEMENT_CORRECTIONS, estimated_minutes=8,
            action_path="/review",
        ))
    elif due:
        t = due[0]
        missions.append(DailyMission(
            user_id=user.id, local_date=local_date, kind=IMPROVEMENT,
            title=f"Refresh {t.topic} — it's due for review",
            subject=t.subject, topic=t.topic, target=1, estimated_minutes=10,
            action_path=f"/subjects/{t.subject}/topics/{t.topic}",
        ))
    elif topics:
        t = topics[0][0]
        missions.append(DailyMission(
            user_id=user.id, local_date=local_date, kind=IMPROVEMENT,
            title=f"Read the {t.topic} lesson",
            subject=t.subject, topic=t.topic, target=1, estimated_minutes=10,
            action_path=f"/learn",
        ))

    for m in missions:
        db.add(m)
    try:
        db.flush()
    except IntegrityError:
        # Another request generated them first. Its set is as valid as ours.
        db.rollback()
        return sorted(
            db.query(DailyMission)
            .filter(DailyMission.user_id == user.id, DailyMission.local_date == local_date)
            .all(),
            key=lambda m: m.kind,
        )
    return sorted(missions, key=lambda m: m.kind)


def advance(
    db: Session,
    user: User,
    *,
    kind: str,
    amount: int = 1,
    subject: str | None = None,
) -> None:
    """
    Move a mission forward. Called from the event pipeline, never by the client.

    Silently does nothing when there is no matching open mission, so callers
    do not have to know what today's missions are.
    """
    today = user.local_today()
    q = (
        db.query(DailyMission)
        .filter(
            DailyMission.user_id == user.id,
            DailyMission.local_date == today,
            DailyMission.kind == kind,
            DailyMission.completed_at.is_(None),
        )
    )
    mission = q.first()
    if mission is None:
        return
    # A subject-scoped mission only counts work in that subject.
    if mission.subject and subject and mission.subject != subject and kind == PRACTICE:
        return

    mission.progress = min(mission.target, mission.progress + amount)
    if mission.progress >= mission.target:
        mission.completed_at = datetime.utcnow()


def try_award_daily_chest(db: Session, user: User) -> int:
    """
    Award the once-per-day chest if all three missions are complete.

    Returns the XP awarded, or 0. The UNIQUE (user, date) on DailyReward is
    what guarantees "exactly one reward per day" under concurrency -- an
    application-level check would race.
    """
    today = user.local_today()
    missions = (
        db.query(DailyMission)
        .filter(DailyMission.user_id == user.id, DailyMission.local_date == today)
        .all()
    )
    if not missions or any(m.completed_at is None for m in missions):
        return 0

    amount = config.get(db, "xp_all_missions")
    reward = DailyReward(user_id=user.id, local_date=today, xp_awarded=amount)
    db.add(reward)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return 0

    events.record(
        db, user=user, event_type=events.MISSION_COMPLETED,
        event_key=f"{events.MISSION_COMPLETED}:{user.id}:{today.isoformat()}",
        payload={"missions": len(missions)},
    )
    return amount
