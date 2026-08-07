"""
Per-question timing capture (UserResponse.answer_seconds).

This column is the input for answer-quality labels, pacing insights and the
fair-play time floor (see GAMIFICATION.md). The properties that matter are
less about storing a number and more about never storing a dishonest one:

  - clients that don't send timing store NULL, not 0
  - absurd values (slept phone, backgrounded tab) are clamped, not trusted
  - a clamped row still keeps its answer
"""



from app.models import Question, UserResponse
from app.routers.quiz import MAX_ANSWER_SECONDS, clamp_answer_seconds


# ---------------------------------------------------------------- unit ----

def test_missing_timing_stays_none_rather_than_becoming_zero():
    """
    Zero would mean "answered instantly", which is a claim about the student.
    Absent timing is not a claim at all and must stay distinguishable.
    """
    assert clamp_answer_seconds(None) is None


def test_ordinary_value_passes_through():
    assert clamp_answer_seconds(42) == 42


def test_absurd_value_is_clamped_not_dropped():
    """A phone that slept for two hours mid-question reports 7200s."""
    assert clamp_answer_seconds(7200) == MAX_ANSWER_SECONDS


def test_negative_value_is_floored_at_zero():
    """Clock skew between client and server can produce a negative delta."""
    assert clamp_answer_seconds(-5) == 0


def test_boundary_is_inclusive():
    assert clamp_answer_seconds(MAX_ANSWER_SECONDS) == MAX_ANSWER_SECONDS


# --------------------------------------------------------- integration ----

def _seed_questions(db_session, n=5, subject="Mathematics", topic="Algebra"):
    for i in range(n):
        db_session.add(Question(
            question_id=f"seed-timing-{subject}-{i}",
            subject=subject, topic=topic, difficulty="easy",
            source="original", status="active",
            question_text=f"Sample question {i}?",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="B", explanation="Because B is correct.",
        ))
    db_session.commit()


def _start(client, register_user, db_session, n=5):
    _seed_questions(db_session, n=n)
    register_user()
    resp = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": n})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _answer(client, attempt, **extra):
    return client.post(f"/api/quiz/{attempt['attempt_id']}/answer", json={
        "question_id": attempt["current_question"]["id"],
        "selected_option": "B",
        **extra,
    })


def test_answer_seconds_is_persisted(client, register_user, db_session):
    attempt = _start(client, register_user, db_session)

    resp = _answer(client, attempt, answer_seconds=37)
    assert resp.status_code == 200, resp.text

    stored = db_session.query(UserResponse).one()
    assert stored.answer_seconds == 37


def test_older_clients_omitting_timing_are_still_accepted(client, register_user, db_session):
    """
    The shipped Android build does not send this field. Rejecting it, or
    coercing it to 0, would either break those users or silently corrupt the
    dataset with fake instant answers.
    """
    attempt = _start(client, register_user, db_session)

    resp = _answer(client, attempt)
    assert resp.status_code == 200, resp.text

    stored = db_session.query(UserResponse).one()
    assert stored.answer_seconds is None


def test_absurd_client_value_is_clamped_but_answer_is_kept(client, register_user, db_session):
    attempt = _start(client, register_user, db_session)

    resp = _answer(client, attempt, answer_seconds=50_000)
    assert resp.status_code == 200, resp.text

    stored = db_session.query(UserResponse).one()
    assert stored.answer_seconds == MAX_ANSWER_SECONDS
    # The point of clamping instead of rejecting: the answer itself survives.
    assert stored.selected_option == "B"
    assert stored.is_correct is True


def test_wildly_out_of_range_value_is_rejected_by_schema(client, register_user, db_session):
    """Beyond a day is not a slow student, it is a broken or hostile client."""
    attempt = _start(client, register_user, db_session)
    assert _answer(client, attempt, answer_seconds=999_999).status_code == 422


def test_negative_seconds_are_rejected_by_schema(client, register_user, db_session):
    attempt = _start(client, register_user, db_session)
    assert _answer(client, attempt, answer_seconds=-1).status_code == 422
