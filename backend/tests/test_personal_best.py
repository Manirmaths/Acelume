"""
Personal bests.

The point of these tests is the comparability rule. A feature that announces
"new personal best!" because the session was easier or shorter is worse than
no feature at all -- it teaches the student the number means nothing.
"""

from app.gamification import personal_best as pb
from app.models import PersonalBest, User


def _user(db, username="pb", email="pb@example.com"):
    u = User(username=username, email=email, password_hash="x", points=0)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_first_attempt_is_a_baseline_not_a_best(db_session):
    user = _user(db_session)
    result = pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
                       topic="Algebra", correct=6, total=10)
    db_session.commit()

    assert result is not None
    assert result.is_baseline is True
    assert result.is_best is False, "a first attempt must never be called a personal best"
    assert "Baseline" in pb.message_for(result)


def test_improvement_is_reported_in_percentage_points(db_session):
    user = _user(db_session)
    pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
              topic="Algebra", correct=6, total=10)          # 60%
    db_session.commit()
    result = pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
                       topic="Algebra", correct=8, total=10)  # 80%
    db_session.commit()

    assert result.is_best is True
    assert result.delta_points == 20, "60% -> 80% is +20 percentage POINTS"
    msg = pb.message_for(result)
    assert "percentage points" in msg
    assert "20%" not in msg, "must not phrase the delta as a percentage"


def test_different_question_count_bands_are_not_compared(db_session):
    """A 10-question quiz and a 40-question quiz are different activities."""
    user = _user(db_session)
    pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
              topic="Algebra", correct=10, total=10)
    db_session.commit()

    result = pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
                       topic="Algebra", correct=20, total=40)
    db_session.commit()

    assert result.is_baseline is True, "a different count band starts its own baseline"
    assert db_session.query(PersonalBest).count() == 2


def test_easier_activity_cannot_overwrite_a_harder_record(db_session):
    """The core protection: a short easy set must not replace a long one."""
    user = _user(db_session)
    pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
              topic="Algebra", correct=30, total=40)  # 75% over 40 questions
    db_session.commit()
    pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
              topic="Algebra", correct=6, total=6)    # 100% over 6
    db_session.commit()

    long_run = (
        db_session.query(PersonalBest)
        .filter(PersonalBest.activity_key.contains("40+"))
        .first()
    )
    assert long_run.best_pct == 75, "the 6-question 100% must not touch the 40-question record"


def test_different_topics_are_separate_records(db_session):
    user = _user(db_session)
    pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
              topic="Algebra", correct=5, total=10)
    pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
              topic="Calculus", correct=9, total=10)
    db_session.commit()
    assert db_session.query(PersonalBest).count() == 2


def test_very_short_attempts_are_ignored(db_session):
    """Celebrating a best over 3 questions would cheapen the signal."""
    user = _user(db_session)
    assert pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
                     topic="Algebra", correct=3, total=3) is None


def test_lower_score_is_phrased_without_punishment(db_session):
    user = _user(db_session)
    pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
              topic="Algebra", correct=9, total=10)
    db_session.commit()
    result = pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
                       topic="Algebra", correct=6, total=10)
    db_session.commit()

    msg = pb.message_for(result, weakest_topic="Probability")
    assert result.is_best is False
    assert "Probability" in msg
    for punitive in ("failed", "worse", "poor", "bad"):
        assert punitive not in msg.lower()


def test_matching_your_best_is_acknowledged(db_session):
    user = _user(db_session)
    pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
              topic="Algebra", correct=7, total=10)
    db_session.commit()
    result = pb.record(db_session, user=user, mode="quiz", subject="Mathematics",
                       topic="Algebra", correct=7, total=10)
    db_session.commit()

    assert result.delta_points == 0
    assert "matched" in pb.message_for(result).lower()
