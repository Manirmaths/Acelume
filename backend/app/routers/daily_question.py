"""
Daily Question -- one question a day, the same one for everybody.

Design notes, since several of the choices here look arbitrary and are not:

  - **The pick is stored, not computed.** A deterministic hash of the date
    would need no table, but it would silently change the "same" day's
    question whenever the question bank changed, and it would make a bad pick
    impossible to correct. A row can be edited; a hash cannot.

  - **The day is Africa/Lagos, not per-student local time.** "Today's
    question" has to mean the same question to two students messaging each
    other about it. Per-student days would break that for anyone travelling,
    which is precisely the student most likely to be comparing.

  - **One attempt each, enforced by a UNIQUE constraint** rather than an
    application check, so a double-tap cannot yield a second, better score.

  - **The correct answer is never sent before the student answers.** Same
    rule as every other question surface in the app.
"""

import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.gamification import events
from app.models import DailyQuestion, DailyQuestionAttempt, Question, User
from app.routers.quiz import clamp_answer_seconds
from app.schemas import DailyQuestionAnswerIn, DailyQuestionOut, DailyQuestionResultOut

router = APIRouter(prefix="/api/daily-question", tags=["daily-question"])

# The shared clock for "today". Everyone gets the same question on the same
# calendar day in Nigeria, wherever they happen to be.
DAILY_TZ = ZoneInfo("Africa/Lagos")

# Rotate the subject by weekday so a student who only ever does the Daily
# Question still sees their whole combination over a week, instead of
# Mathematics every day because it has the largest pool.
WEEKDAY_SUBJECTS = [
    "Mathematics",   # Monday
    "English",       # Tuesday
    "Physics",       # Wednesday
    "Biology",       # Thursday
    "Chemistry",     # Friday
    "Economics",     # Saturday
    "Government",    # Sunday
]

# Don't reuse a question that has been the Daily Question recently.
RECENT_REUSE_DAYS = 180


def today_lagos() -> date:
    return datetime.now(DAILY_TZ).date()


def _pick_question_for(db: Session, on_date: date) -> Question | None:
    """
    Choose the day's question.

    Seeded on the date so the choice is reproducible if this ever has to be
    re-run for a missed day, but still stored afterwards so it stays stable.
    """
    subject = WEEKDAY_SUBJECTS[on_date.weekday() % len(WEEKDAY_SUBJECTS)]

    recently_used = {
        qid for (qid,) in db.query(DailyQuestion.question_id)
        .filter(DailyQuestion.on_date >= on_date - timedelta(days=RECENT_REUSE_DAYS))
        .all()
    }

    def pool_for(subj: str | None) -> list[Question]:
        q = db.query(Question).filter(
            Question.status == "active",
            # An unexplained question is a poor choice for the one question
            # a student might do all day.
            Question.explanation.isnot(None),
            Question.explanation != "",
        )
        if subj:
            q = q.filter(Question.subject == subj)
        return [x for x in q.all() if x.id not in recently_used]

    # Fall back to any subject rather than skipping the day: a missing Daily
    # Question is worse than one from the wrong subject.
    pool = pool_for(subject) or pool_for(None)
    if not pool:
        return None

    return random.Random(on_date.toordinal()).choice(pool)


def get_or_create_for(db: Session, on_date: date) -> DailyQuestion | None:
    existing = db.query(DailyQuestion).filter(DailyQuestion.on_date == on_date).first()
    if existing:
        return existing

    question = _pick_question_for(db, on_date)
    if question is None:
        return None

    row = DailyQuestion(on_date=on_date, question_id=question.id)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Two students opened the app in the same instant on a new day. The
        # unique index on on_date makes this harmless -- take whichever won.
        db.rollback()
        return db.query(DailyQuestion).filter(DailyQuestion.on_date == on_date).first()
    db.refresh(row)
    return row


def _stats(db: Session, daily: DailyQuestion) -> tuple[int, int | None, int | None]:
    """(answered_count, percent_correct, median-ish average seconds)."""
    total = db.query(func.count(DailyQuestionAttempt.id)).filter(
        DailyQuestionAttempt.daily_question_id == daily.id
    ).scalar() or 0
    if total == 0:
        return 0, None, None

    correct = db.query(func.count(DailyQuestionAttempt.id)).filter(
        DailyQuestionAttempt.daily_question_id == daily.id,
        DailyQuestionAttempt.is_correct.is_(True),
    ).scalar() or 0

    avg_seconds = db.query(func.avg(DailyQuestionAttempt.answer_seconds)).filter(
        DailyQuestionAttempt.daily_question_id == daily.id,
        DailyQuestionAttempt.answer_seconds.isnot(None),
    ).scalar()

    return total, round(100 * correct / total), round(avg_seconds) if avg_seconds else None


def _record_streak(user: User, on_date: date) -> None:
    """
    Advance the Daily Question streak.

    Uses the shared Lagos day, not the student's own -- the streak has to
    agree with the question it is counting.
    """
    last = user.last_daily_question_date
    if last == on_date:
        return  # already counted today
    if last == on_date - timedelta(days=1):
        user.daily_question_streak = (user.daily_question_streak or 0) + 1
    else:
        user.daily_question_streak = 1
    user.last_daily_question_date = on_date
    user.longest_daily_question_streak = max(
        user.longest_daily_question_streak or 0, user.daily_question_streak
    )


@router.get("", response_model=DailyQuestionOut)
def get_daily_question(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    on_date = today_lagos()
    daily = get_or_create_for(db, on_date)
    if daily is None:
        raise HTTPException(status_code=404, detail="No question available today.")

    question = db.get(Question, daily.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="No question available today.")

    attempt = (
        db.query(DailyQuestionAttempt)
        .filter(
            DailyQuestionAttempt.user_id == user.id,
            DailyQuestionAttempt.daily_question_id == daily.id,
        )
        .first()
    )
    answered = attempt is not None
    total, pct_correct, avg_seconds = _stats(db, daily)

    return DailyQuestionOut(
        date=on_date.isoformat(),
        question_id=question.id,
        subject=question.subject,
        topic=question.topic,
        question_text=question.question_text,
        image_url=question.image_url,
        option_a=question.option_a,
        option_b=question.option_b,
        option_c=question.option_c,
        option_d=question.option_d,
        answered=answered,
        # Everything below is withheld until this student has answered --
        # otherwise the endpoint hands out the answer for free.
        your_answer=attempt.selected_option if attempt else None,
        your_seconds=attempt.answer_seconds if attempt else None,
        is_correct=attempt.is_correct if attempt else None,
        correct_option=question.correct_option if answered else None,
        explanation=question.explanation if answered else None,
        answered_count=total,
        percent_correct=pct_correct if answered else None,
        average_seconds=avg_seconds if answered else None,
        streak=user.daily_question_streak or 0,
    )


@router.post("/answer", response_model=DailyQuestionResultOut)
def answer_daily_question(
    payload: DailyQuestionAnswerIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    on_date = today_lagos()
    daily = get_or_create_for(db, on_date)
    if daily is None:
        raise HTTPException(status_code=404, detail="No question available today.")

    question = db.get(Question, daily.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="No question available today.")

    selected = (payload.selected_option or "").strip().upper()[:1]
    if selected not in ("A", "B", "C", "D"):
        raise HTTPException(status_code=400, detail="Choose one of A, B, C or D.")

    is_correct = selected == question.correct_option
    seconds = clamp_answer_seconds(payload.answer_seconds)

    attempt = DailyQuestionAttempt(
        user_id=user.id,
        daily_question_id=daily.id,
        selected_option=selected,
        is_correct=is_correct,
        answer_seconds=seconds,
    )
    db.add(attempt)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already answered today's question.")

    _record_streak(user, on_date)

    # XP only for a correct answer, and only through the normal ledger so the
    # daily cap and idempotency guards apply exactly as they do elsewhere.
    # A one-tap feature must not become the cheapest way to farm XP.
    if is_correct:
        events.record(
            db, user=user, event_type=events.QUESTION_ANSWERED,
            event_key=f"daily:{daily.id}:user={user.id}",
            subject=question.subject, topic=question.topic,
            source_id=str(question.id),
            payload={"daily": True},
        )

    db.commit()

    total, pct_correct, avg_seconds = _stats(db, daily)
    faster_than = None
    if seconds is not None and total > 1:
        slower = db.query(func.count(DailyQuestionAttempt.id)).filter(
            DailyQuestionAttempt.daily_question_id == daily.id,
            DailyQuestionAttempt.answer_seconds.isnot(None),
            DailyQuestionAttempt.answer_seconds > seconds,
        ).scalar() or 0
        timed = db.query(func.count(DailyQuestionAttempt.id)).filter(
            DailyQuestionAttempt.daily_question_id == daily.id,
            DailyQuestionAttempt.answer_seconds.isnot(None),
        ).scalar() or 0
        if timed > 1:
            faster_than = round(100 * slower / timed)

    return DailyQuestionResultOut(
        is_correct=is_correct,
        correct_option=question.correct_option,
        explanation=question.explanation,
        your_seconds=seconds,
        answered_count=total,
        percent_correct=pct_correct,
        average_seconds=avg_seconds,
        faster_than_percent=faster_than,
        streak=user.daily_question_streak or 0,
    )
