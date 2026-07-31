"""
Tests for the live wiring: real quiz/mock/lesson actions producing events.

Phase 0 built the ledger; these check it is actually fed, and — more
importantly — that the anti-farming rules hold when driven through the real
endpoints rather than called directly.
"""

from app.gamification import config
from app.models import LearningEvent, Question, TopicMastery, User, XpLedger


# question_id is UNIQUE, and several tests seed more than one batch, so the
# counter has to be global rather than per-call.
_seq = [0]


def _questions(db, subject="Mathematics", topic="Algebraic Processes", n=12):
    made = []
    for _ in range(n):
        _seq[0] += 1
        q = Question(
            question_id=f"WIRE-{_seq[0]:05d}",
            subject=subject, topic=topic, difficulty="easy",
            question_text="Q?", option_a="A", option_b="B",
            option_c="C", option_d="D", correct_option="A",
            explanation="because", source="original", status="active",
        )
        db.add(q)
        made.append(q)
    db.commit()
    return made


def _start(client, **payload):
    r = client.post("/api/quiz/start", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _answer_all(client, attempt, correct=True):
    """
    Answer through an attempt, following the server's `current_question`.

    Deliberately does NOT iterate a locally-held list of questions: /start
    selects them at RANDOM, so any local ordering disagrees with the attempt
    after the first answer. Driving off the response chain is also exactly
    what a real client does.
    """
    current = attempt["current_question"]
    answered = 0
    while current is not None:
        r = client.post(
            f"/api/quiz/{attempt['attempt_id']}/answer",
            json={"question_id": current["id"], "selected_option": "A" if correct else "B"},
        )
        assert r.status_code == 200, r.text
        answered += 1
        nxt = r.json()["next"]
        if nxt["finished"]:
            break
        current = nxt["current_question"]
    return answered


def test_correct_answer_writes_event_and_ledger(client, register_user, db_session):
    register_user()
    _questions(db_session, n=3)

    attempt = _start(client, subject="Mathematics", n=3)
    r = client.post(
        f"/api/quiz/{attempt['attempt_id']}/answer",
        json={"question_id": attempt["current_question"]["id"], "selected_option": "A"},
    )
    assert r.status_code == 200, r.text

    events_rows = db_session.query(LearningEvent).filter_by(event_type="QUESTION_ANSWERED").all()
    assert len(events_rows) == 1
    ledger = db_session.query(XpLedger).all()
    assert len(ledger) == 1
    assert ledger[0].amount == config.DEFAULTS["xp_correct_answer"]


def test_points_match_the_ledger(client, register_user, db_session):
    """User.points is a cached total; it must not drift from the ledger."""
    register_user()
    _questions(db_session, n=4)
    _answer_all(client, _start(client, subject="Mathematics", n=4))

    user = db_session.query(User).first()
    db_session.refresh(user)
    total = sum(r.amount for r in db_session.query(XpLedger).filter_by(user_id=user.id))
    assert user.points == total


def test_wrong_answer_awards_nothing(client, register_user, db_session):
    register_user()
    _questions(db_session, n=4)
    attempt = _start(client, subject="Mathematics", n=2)

    r = client.post(
        f"/api/quiz/{attempt['attempt_id']}/answer",
        json={"question_id": attempt["current_question"]["id"], "selected_option": "B"},
    )
    assert r.status_code == 200, r.text
    user = db_session.query(User).first()
    db_session.refresh(user)
    assert user.points == 0
    assert db_session.query(XpLedger).count() == 0


def test_reading_a_lesson_awards_the_first_star_once(client, register_user, db_session, monkeypatch):
    """Re-reading a note must not re-award the lesson."""
    from app.models import LessonNote

    register_user()
    note = LessonNote(
        subject="Mathematics", topic="Algebraic Processes", title="Algebra",
        summary="s", content_md="## Hello", status="active",
    )
    db_session.add(note)
    db_session.commit()

    for _ in range(3):
        r = client.post("/api/notes/Mathematics/Algebraic Processes/read")
        assert r.status_code == 200, r.text

    lessons = db_session.query(LearningEvent).filter_by(event_type="LESSON_COMPLETED").all()
    assert len(lessons) == 1, "re-reading must not re-award"

    row = db_session.query(TopicMastery).filter_by(topic="Algebraic Processes").first()
    assert row is not None and row.stars == 1
    assert row.state == "learning"


def test_single_topic_pass_reaches_proficiency(client, register_user, db_session):
    """10+ questions at 70%+ earns the second star."""
    register_user()
    _questions(db_session, n=10)

    attempt = _start(client, subject="Mathematics", topic="Algebraic Processes", n=10)
    assert _answer_all(client, attempt) == 10

    row = db_session.query(TopicMastery).filter_by(topic="Algebraic Processes").first()
    assert row is not None
    assert row.proficient_at is not None
    assert row.stars == 2
    assert row.state == "proficient"
    assert row.mastery_score == 100

    proficient = db_session.query(LearningEvent).filter_by(event_type="TOPIC_PROFICIENT").all()
    assert len(proficient) == 1


def test_untimed_practice_never_reaches_mastery(client, register_user, db_session):
    """The Master stage requires a timed challenge, however high the score."""
    register_user()
    _questions(db_session, n=16)

    attempt = _start(client, subject="Mathematics", topic="Algebraic Processes", n=16)
    assert _answer_all(client, attempt) == 16

    row = db_session.query(TopicMastery).filter_by(topic="Algebraic Processes").first()
    assert row.proficient_at is not None
    assert row.mastered_at is None, "untimed practice must not grant three stars"
    assert row.stars == 2


def test_mixed_topic_quiz_does_not_credit_any_topic(client, register_user, db_session):
    """A quiz spanning topics is not evidence about any one of them."""
    register_user()
    _questions(db_session, topic="Algebraic Processes", n=6)
    _questions(db_session, topic="Calculus", n=6)

    attempt = _start(client, subject="Mathematics", n=12)
    assert _answer_all(client, attempt) == 12

    rows = db_session.query(TopicMastery).all()
    assert all(r.proficient_at is None for r in rows), (
        "a mixed-topic attempt must not grant proficiency in any topic"
    )
