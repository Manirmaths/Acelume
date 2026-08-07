"""
Ratings end to end: which answers count, and what the student is shown.

The maths is covered in test_rating.py. What matters here is the policy around
it, and the policy has one rule that is easy to get wrong and expensive to get
wrong: revision must not lower your rating.

Spaced review and marked-question replay serve, by design, the material a
student is weakest on. If those counted, every conscientious student's rating
would fall for doing exactly the revision the app told them to do.
"""

from app.models import Question, SubjectRating
from app.rating_service import MIN_ANSWERS_FOR_PREDICTION
from app.subjects import SUBJECTS


def _seed_every_subject(db_session, per_subject=5):
    """The diagnostic samples across every subject, so all of them need a pool."""
    for subject in SUBJECTS:
        _seed(db_session, n=per_subject, subject=subject)


def _seed(db_session, n=40, subject="Mathematics", correct="B"):
    for i in range(n):
        db_session.add(Question(
            question_id=f"seed-rate-{subject}-{i}",
            subject=subject, topic="Algebra", difficulty="medium",
            source="original", status="active",
            question_text=f"Rating sample {i}?",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option=correct, explanation="Because B.",
        ))
    db_session.commit()


def _play(client, attempt_id, answer_option, limit=99):
    """Answer through an attempt, returning how many questions were answered."""
    answered = 0
    for _ in range(limit):
        current = client.get(f"/api/quiz/{attempt_id}").json()
        if current["finished"] or not current.get("current_question"):
            break
        client.post(f"/api/quiz/{attempt_id}/answer", json={
            "question_id": current["current_question"]["id"],
            "selected_option": answer_option,
            "answer_seconds": 20,
        })
        answered += 1
    return answered


def _rating_row(db_session, subject="Mathematics"):
    return db_session.query(SubjectRating).filter(SubjectRating.subject == subject).first()


# --------------------------------------------------------------- earning ----

def test_a_finished_quiz_creates_a_rating(client, register_user, db_session):
    _seed(db_session)
    register_user()
    attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 5}).json()
    _play(client, attempt["attempt_id"], "B")

    row = _rating_row(db_session)
    assert row is not None
    assert row.answers_counted == 5


def test_answering_everything_correctly_raises_the_rating(client, register_user, db_session):
    _seed(db_session)
    register_user()
    attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 10}).json()
    _play(client, attempt["attempt_id"], "B")

    assert _rating_row(db_session).rating > 1200.0


def test_answering_everything_wrong_lowers_the_rating(client, register_user, db_session):
    """
    The whole reason for having a rating at all: it must be able to fall. XP
    and level cannot, which is why neither answers "how good am I?".
    """
    _seed(db_session)
    register_user()
    attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 10}).json()
    _play(client, attempt["attempt_id"], "A")

    assert _rating_row(db_session).rating < 1200.0


def test_the_rating_updates_once_per_attempt_not_once_per_answer(client, register_user, db_session):
    """
    Glicko-2 is defined over a rating period. A per-answer update overreacts to
    each result and makes the number visibly jitter.
    """
    _seed(db_session)
    register_user()
    attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 5}).json()
    attempt_id = attempt["attempt_id"]

    # Mid-attempt: nothing yet.
    current = client.get(f"/api/quiz/{attempt_id}").json()
    client.post(f"/api/quiz/{attempt_id}/answer", json={
        "question_id": current["current_question"]["id"], "selected_option": "B",
    })
    assert _rating_row(db_session) is None

    _play(client, attempt_id, "B")
    assert _rating_row(db_session) is not None


def test_a_timed_out_attempt_still_counts_what_was_answered(client, register_user, db_session):
    _seed(db_session)
    register_user()
    attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 10}).json()
    attempt_id = attempt["attempt_id"]

    for _ in range(3):
        current = client.get(f"/api/quiz/{attempt_id}").json()
        client.post(f"/api/quiz/{attempt_id}/answer", json={
            "question_id": current["current_question"]["id"], "selected_option": "B",
        })
    client.post(f"/api/quiz/{attempt_id}/finish")

    row = _rating_row(db_session)
    assert row is not None
    assert row.answers_counted == 3, "unanswered questions must not count as wrong"


# ---------------------------------------------------- revision is exempt ----

def test_a_diagnostic_does_not_move_the_rating(client, register_user, db_session):
    """
    A diagnostic is a deliberately shallow sweep taken cold, before any
    teaching. Rating it would punish a student for taking the onboarding step
    the app asked them to take.
    """
    _seed_every_subject(db_session)
    register_user()

    attempt = client.post("/api/quiz/start-diagnostic").json()
    _play(client, attempt["attempt_id"], "A")

    assert db_session.query(SubjectRating).count() == 0


def test_replaying_marked_questions_does_not_move_the_rating(client, register_user, db_session):
    """
    Marked questions are a sample the student selected FOR being confusing.
    Rating them would mean revising your hardest material always costs you.
    """
    from app.models import QuizAttempt

    _seed(db_session)
    register_user()
    attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 5}).json()
    _play(client, attempt["attempt_id"], "B")

    before = _rating_row(db_session).rating

    marked = QuizAttempt(
        user_id=db_session.query(SubjectRating).first().user_id,
        mode="marked", subject="Mathematics",
        question_ids=[q.id for q in db_session.query(Question).limit(5).all()],
        current_index=0, score=0,
    )
    db_session.add(marked)
    db_session.commit()
    _play(client, marked.id, "A")

    assert _rating_row(db_session).rating == before


# ------------------------------------------------- what the student sees ----

def test_no_prediction_is_offered_from_too_few_answers(client, register_user, db_session):
    """A prediction from four questions is a guess wearing a number's clothes."""
    _seed(db_session)
    register_user()
    attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 5}).json()
    _play(client, attempt["attempt_id"], "B")

    assert client.get("/api/dashboard/ratings").json() == []


def test_a_prediction_appears_once_there_is_enough_evidence(client, register_user, db_session):
    _seed(db_session, n=60)
    register_user()
    for _ in range(3):
        attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 10}).json()
        _play(client, attempt["attempt_id"], "B")

    ratings = client.get("/api/dashboard/ratings").json()
    assert len(ratings) == 1
    entry = ratings[0]

    assert entry["subject"] == "Mathematics"
    assert 0 <= entry["predicted_score"] <= 100
    assert entry["range_low"] <= entry["predicted_score"] <= entry["range_high"]
    assert entry["answers_counted"] >= MIN_ANSWERS_FOR_PREDICTION


def test_the_raw_glicko_rating_is_never_sent_to_the_client(client, register_user, db_session):
    """
    The internal number stays internal. "I'm a 900 and my friend is a 1400" is
    the exact damage the predicted-score framing exists to avoid.
    """
    _seed(db_session, n=60)
    register_user()
    for _ in range(3):
        attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 10}).json()
        _play(client, attempt["attempt_id"], "B")

    body = client.get("/api/dashboard/ratings").json()[0]
    assert "rating" not in body
    assert "deviation" not in body
    assert "volatility" not in body


# ------------------------------------------------- question calibration ----

def test_question_difficulty_is_learned_from_real_answers(client, register_user, db_session):
    from app.models import QuestionRating

    _seed(db_session)
    register_user()
    attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 5}).json()
    _play(client, attempt["attempt_id"], "B")

    stats = db_session.query(QuestionRating).all()
    assert len(stats) == 5
    assert all(s.times_seen == 1 and s.times_correct == 1 for s in stats)


def test_question_stats_are_collected_even_in_unrated_modes(client, register_user, db_session):
    """
    A question's difficulty is not distorted by which mode served it, so it
    calibrates from every answer -- unlike the student's own rating.
    """
    from app.models import QuestionRating

    _seed_every_subject(db_session)
    register_user()

    attempt = client.post("/api/quiz/start-diagnostic").json()
    answered = _play(client, attempt["attempt_id"], "B")

    assert db_session.query(QuestionRating).count() == answered
