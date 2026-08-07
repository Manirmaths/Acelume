"""
Database-facing layer over app/rating.py.

The maths lives in rating.py and is pure. This module owns the questions that
maths cannot answer: which answers count, when a rating is updated, and what
the student is allowed to see.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import rating as glicko
from app.models import Question, QuestionRating, SubjectRating, User

# Modes whose answers move a student's rating.
#
# The exclusions are not arbitrary -- each is a mode whose question sample is
# BIASED, so rating it would measure the sampling rather than the student:
#
#   marked        replays questions the student flagged as confusing, i.e. a
#                 sample deliberately selected for being hard for them
#   smart_review  spaced repetition, which by construction serves the material
#                 they are weakest on
#   diagnostic    a cold, deliberately shallow sweep taken before any teaching
#
# Rating those would push every conscientious student's rating down for doing
# exactly the revision the app told them to do. That is worse than not having
# a rating at all.
RATED_MODES = {"quiz", "blitz", "rush", "mock", "test_out", "cbt", "daily"}

# Enough answers in a subject before a predicted score is worth showing at all.
MIN_ANSWERS_FOR_PREDICTION = 10


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def get_or_create(db: Session, user_id: int, subject: str) -> SubjectRating:
    row = (
        db.query(SubjectRating)
        .filter(SubjectRating.user_id == user_id, SubjectRating.subject == subject)
        .first()
    )
    if row is None:
        row = SubjectRating(
            user_id=user_id,
            subject=subject,
            rating=glicko.DEFAULT_RATING,
            deviation=glicko.DEFAULT_DEVIATION,
            volatility=glicko.DEFAULT_VOLATILITY,
            peak_rating=glicko.DEFAULT_RATING,
            week_start_rating=glicko.DEFAULT_RATING,
            week_start_on=_week_start(datetime.utcnow().date()),
        )
        db.add(row)
        db.flush()
    return row


def as_rating(row: SubjectRating) -> glicko.Rating:
    return glicko.Rating(rating=row.rating, deviation=row.deviation, volatility=row.volatility)


def question_rating_for(db: Session, question: Question) -> tuple[float, float]:
    """
    How hard this question really is, from observed performance.

    Falls back to the hand-assigned difficulty until enough students have
    attempted it. See rating.question_rating_from_responses.
    """
    seed = glicko.DIFFICULTY_SEED_RATING.get(
        (question.difficulty or "medium").lower(), glicko.DEFAULT_RATING
    )
    stats = (
        db.query(QuestionRating)
        .filter(QuestionRating.question_id == question.id)
        .first()
    )
    if stats is None:
        return seed, glicko.SEED_QUESTION_RD
    return glicko.question_rating_from_responses(
        times_seen=stats.times_seen, times_correct=stats.times_correct, seed_rating=seed
    )


def record_question_result(db: Session, question_id: int, is_correct: bool) -> None:
    """
    Update the counters that make a question's rating self-calibrating.

    Called for EVERY answer regardless of mode -- unlike a student's rating,
    a question's difficulty is not distorted by which mode it was served in.
    """
    stats = db.query(QuestionRating).filter(QuestionRating.question_id == question_id).first()
    if stats is None:
        stats = QuestionRating(question_id=question_id, times_seen=0, times_correct=0)
        db.add(stats)
    stats.times_seen += 1
    if is_correct:
        stats.times_correct += 1
    stats.updated_at = datetime.utcnow()


def apply_attempt(
    db: Session,
    user: User,
    subject: str | None,
    outcomes: list[glicko.Outcome],
    mode: str,
) -> SubjectRating | None:
    """
    Apply one finished attempt's worth of answers as a single rating update.

    Batched deliberately: Glicko-2 is defined over a rating PERIOD containing
    several results. Updating once per answer overreacts to each one and makes
    the number jitter in a way that reads as broken.
    """
    if mode not in RATED_MODES or not subject or not outcomes:
        return None

    row = get_or_create(db, user.id, subject)

    today = datetime.utcnow().date()
    this_week = _week_start(today)
    if row.week_start_on != this_week:
        # Roll the weekly baseline forward so "+4 this week" stays truthful
        # without keeping a full rating history.
        row.week_start_on = this_week
        row.week_start_rating = row.rating

    updated = glicko.update(as_rating(row), outcomes)

    row.rating = updated.rating
    row.deviation = updated.deviation
    row.volatility = updated.volatility
    row.peak_rating = max(row.peak_rating or 0.0, updated.rating)
    row.answers_counted = (row.answers_counted or 0) + len(outcomes)
    row.updated_at = datetime.utcnow()
    return row


def summary_for(db: Session, user_id: int, subject: str) -> dict | None:
    """
    What the student is allowed to see.

    Three guardrails are enforced here rather than in the UI, so no future
    screen can accidentally bypass them:

      1. Nothing at all below MIN_ANSWERS_FOR_PREDICTION answers. A prediction
         from four questions is a guess wearing a number's clothes.
      2. While provisional, the band is returned but the point estimate is
         flagged so the UI says "still getting a read on you".
      3. The raw Glicko rating is NEVER included. It is internal. A student
         comparing "I'm 900, my friend is 1400" is the failure mode this whole
         design exists to avoid; the predicted score is the public surface.
    """
    row = (
        db.query(SubjectRating)
        .filter(SubjectRating.user_id == user_id, SubjectRating.subject == subject)
        .first()
    )
    if row is None or (row.answers_counted or 0) < MIN_ANSWERS_FOR_PREDICTION:
        return None

    current = as_rating(row)
    low, high = glicko.confidence_band(current)

    week_delta = None
    if row.week_start_on == _week_start(datetime.utcnow().date()):
        week_delta = glicko.predicted_score(current) - glicko.predicted_score(
            glicko.Rating(row.week_start_rating, row.deviation, row.volatility)
        )

    return {
        "subject": subject,
        "predicted_score": glicko.predicted_score(current),
        "range_low": low,
        "range_high": high,
        "provisional": current.is_provisional,
        "answers_counted": row.answers_counted,
        # Only ever shown as "▲ 4 this week". A fall is never announced on its
        # own -- see the note in the schema and the UI.
        "week_delta": week_delta,
    }


def target_difficulty_band(db: Session, user_id: int, subject: str) -> tuple[float, float] | None:
    """
    The rating band to serve questions from.

    +50 to +150 above the student is the range where they are likely but not
    certain to succeed -- hard enough to teach, not so hard as to be noise.
    Returns None while the rating is still provisional, so a student who has
    barely started gets the ordinary random mix rather than adaptive selection
    driven by a number the app does not trust yet.
    """
    row = (
        db.query(SubjectRating)
        .filter(SubjectRating.user_id == user_id, SubjectRating.subject == subject)
        .first()
    )
    if row is None or (row.answers_counted or 0) < MIN_ANSWERS_FOR_PREDICTION:
        return None
    if as_rating(row).is_provisional:
        return None
    return row.rating + 50.0, row.rating + 150.0
