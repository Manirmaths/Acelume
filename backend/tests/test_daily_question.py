"""
Daily Question: one question a day, the same one for every student.

The properties worth protecting are mostly about fairness and honesty rather
than mechanics -- everyone must get the same question, nobody may see the
answer before answering, and nobody may answer twice.
"""

from datetime import date, timedelta

import pytest

from app.models import DailyQuestion, DailyQuestionAttempt, Question, User
from app.routers.daily_question import get_or_create_for, _record_streak


def _seed_questions(db_session, n=30):
    subjects = ["Mathematics", "English", "Physics", "Biology", "Chemistry", "Economics", "Government"]
    for i in range(n):
        db_session.add(Question(
            question_id=f"seed-daily-{i}",
            subject=subjects[i % len(subjects)],
            topic="Topic", difficulty="medium",
            source="original", status="active",
            question_text=f"Daily sample {i}?",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="B", explanation="Because B.",
        ))
    db_session.commit()


@pytest.fixture()
def seeded(client, register_user, db_session):
    _seed_questions(db_session)
    register_user()
    return client


# ------------------------------------------------------------ selection ----

def test_the_same_question_is_served_to_everyone_on_a_given_day(db_session):
    """
    The whole feature rests on this. If two students get different questions,
    there is nothing to compare and nothing to talk about, and the feature is
    just a worse version of daily missions.
    """
    _seed_questions(db_session)
    day = date(2026, 8, 7)

    first = get_or_create_for(db_session, day)
    second = get_or_create_for(db_session, day)

    assert first is not None
    assert first.id == second.id
    assert first.question_id == second.question_id


def test_a_day_with_no_usable_questions_returns_none_rather_than_raising(db_session):
    """An empty bank must degrade to 'no card today', never to a 500."""
    assert get_or_create_for(db_session, date(2026, 8, 7)) is None


def test_recently_used_questions_are_not_repeated(db_session):
    _seed_questions(db_session, n=8)
    base = date(2026, 8, 7)

    picked = []
    for offset in range(6):
        row = get_or_create_for(db_session, base + timedelta(days=offset))
        assert row is not None
        picked.append(row.question_id)

    assert len(set(picked)) == len(picked), "a question repeated within the reuse window"


# --------------------------------------------------------------- access ----

def test_answer_is_withheld_until_the_student_has_answered(seeded):
    res = seeded.get("/api/daily-question")
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["answered"] is False
    assert body["correct_option"] is None, "the correct answer leaked before answering"
    assert body["explanation"] is None


def test_answering_reveals_the_answer_and_explanation(seeded):
    res = seeded.post("/api/daily-question/answer", json={"selected_option": "B", "answer_seconds": 12})
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["is_correct"] is True
    assert body["correct_option"] == "B"
    assert body["explanation"]


def test_a_second_attempt_is_refused(seeded):
    first = seeded.post("/api/daily-question/answer", json={"selected_option": "A"})
    assert first.status_code == 200, first.text

    second = seeded.post("/api/daily-question/answer", json={"selected_option": "B"})
    assert second.status_code == 409, "a student got a second, better attempt at the same question"


def test_a_wrong_answer_still_reveals_the_explanation(seeded):
    body = seeded.post("/api/daily-question/answer", json={"selected_option": "A"}).json()
    assert body["is_correct"] is False
    assert body["correct_option"] == "B"
    assert body["explanation"]


def test_invalid_option_is_rejected(seeded):
    assert seeded.post("/api/daily-question/answer", json={"selected_option": "Z"}).status_code == 400


def test_get_after_answering_reports_the_students_own_attempt(seeded, db_session):
    seeded.post("/api/daily-question/answer", json={"selected_option": "A", "answer_seconds": 9})

    body = seeded.get("/api/daily-question").json()
    assert body["answered"] is True
    assert body["your_answer"] == "A"
    assert body["your_seconds"] == 9
    assert body["is_correct"] is False
    assert body["correct_option"] == "B"


def test_timing_is_clamped_like_every_other_answer(seeded, db_session):
    seeded.post("/api/daily-question/answer", json={"selected_option": "B", "answer_seconds": 40_000})
    attempt = db_session.query(DailyQuestionAttempt).one()
    assert attempt.answer_seconds == 600


# --------------------------------------------------------------- streak ----

def test_consecutive_days_extend_the_streak():
    user = User(username="u", email="u@x.com", password_hash="x")
    user.daily_question_streak = 0
    user.longest_daily_question_streak = 0

    _record_streak(user, date(2026, 8, 5))
    _record_streak(user, date(2026, 8, 6))
    _record_streak(user, date(2026, 8, 7))

    assert user.daily_question_streak == 3
    assert user.longest_daily_question_streak == 3


def test_a_missed_day_resets_the_streak_but_not_the_record():
    user = User(username="u", email="u@x.com", password_hash="x")
    user.daily_question_streak = 0
    user.longest_daily_question_streak = 0

    _record_streak(user, date(2026, 8, 1))
    _record_streak(user, date(2026, 8, 2))
    _record_streak(user, date(2026, 8, 3))
    _record_streak(user, date(2026, 8, 7))  # gap

    assert user.daily_question_streak == 1
    assert user.longest_daily_question_streak == 3


def test_answering_twice_on_one_day_does_not_double_count_the_streak():
    user = User(username="u", email="u@x.com", password_hash="x")
    user.daily_question_streak = 0
    user.longest_daily_question_streak = 0

    _record_streak(user, date(2026, 8, 7))
    _record_streak(user, date(2026, 8, 7))

    assert user.daily_question_streak == 1


def test_streak_is_reported_back_to_the_student(seeded):
    body = seeded.post("/api/daily-question/answer", json={"selected_option": "B"}).json()
    assert body["streak"] == 1


# ---------------------------------------------------------------- stats ----

def test_stats_reflect_all_students_not_just_this_one(client, register_user, db_session):
    _seed_questions(db_session)

    register_user(username="alice", email="alice@example.com")
    client.post("/api/daily-question/answer", json={"selected_option": "B"})  # correct
    client.post("/api/auth/logout")

    register_user(username="bob", email="bob@example.com")
    body = client.post("/api/daily-question/answer", json={"selected_option": "A"}).json()  # wrong

    assert body["answered_count"] == 2
    assert body["percent_correct"] == 50


def test_only_one_row_per_day_is_ever_created(seeded, db_session):
    seeded.get("/api/daily-question")
    seeded.get("/api/daily-question")
    seeded.post("/api/daily-question/answer", json={"selected_option": "B"})

    assert db_session.query(DailyQuestion).count() == 1
