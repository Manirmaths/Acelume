"""
Quest Map tests.

The properties that matter here are the ones that would silently harm students:
a topic locking after they've already started it, or a prerequisite chain with
no escape hatch.
"""

from datetime import datetime

from app.models import SyllabusTopic, TopicMastery, User


def _syllabus(db, subject="Mathematics"):
    """A three-topic chain: A -> B -> C."""
    a = SyllabusTopic(subject=subject, topic="Number, Fractions, and Approximation", order_index=0)
    db.add(a)
    db.flush()
    b = SyllabusTopic(subject=subject, topic="Algebraic Processes", order_index=1, prerequisite_id=a.id)
    db.add(b)
    db.flush()
    c = SyllabusTopic(subject=subject, topic="Calculus", order_index=2, prerequisite_id=b.id)
    db.add(c)
    db.commit()
    return a, b, c


def test_first_topic_available_rest_locked(client, register_user, db_session):
    register_user()
    _syllabus(db_session)

    r = client.get("/api/quest/Mathematics")
    assert r.status_code == 200
    data = r.json()

    states = {t["topic"]: t["state"] for t in data["topics"]}
    assert states["Number, Fractions, and Approximation"] == "available"
    assert states["Algebraic Processes"] == "locked"
    assert states["Calculus"] == "locked"
    assert data["total_topics"] == 3
    assert data["mastered_topics"] == 0


def test_locked_topics_offer_test_out(client, register_user, db_session):
    """A student who already knows the material must never be permanently
    blocked behind a prerequisite."""
    register_user()
    _syllabus(db_session)

    topics = client.get("/api/quest/Mathematics").json()["topics"]
    locked = [t for t in topics if t["state"] == "locked"]
    assert locked, "expected some locked topics in this fixture"
    assert all(t["can_test_out"] for t in locked)


def test_proficiency_unlocks_the_next_topic(client, register_user, db_session):
    register_user()
    _syllabus(db_session)

    user = db_session.query(User).first()
    db_session.add(TopicMastery(
        user_id=user.id, subject="Mathematics",
        topic="Number, Fractions, and Approximation",
        state="proficient", stars=2, mastery_score=75,
        proficient_at=datetime.utcnow(),
    ))
    db_session.commit()

    states = {t["topic"]: t["state"] for t in client.get("/api/quest/Mathematics").json()["topics"]}
    assert states["Algebraic Processes"] == "available", "proficiency should unlock the next topic"
    assert states["Calculus"] == "locked", "but not the one after it"


def test_started_topic_is_never_relocked(client, register_user, db_session):
    """Losing access to work already begun would be punitive. A topic the
    student has engaged with stays reachable even if its prerequisite is not
    met (e.g. after an admin reorders the syllabus)."""
    register_user()
    _syllabus(db_session)

    user = db_session.query(User).first()
    db_session.add(TopicMastery(
        user_id=user.id, subject="Mathematics", topic="Calculus",
        state="practising", practice_attempts=3, mastery_score=40,
    ))
    db_session.commit()

    states = {t["topic"]: t["state"] for t in client.get("/api/quest/Mathematics").json()["topics"]}
    assert states["Calculus"] == "practising", "an in-progress topic must not be re-locked"


def test_unknown_subject_is_404(client, register_user):
    register_user()
    assert client.get("/api/quest/Astrology").status_code == 404


def test_subject_without_syllabus_is_404_not_empty_map(client, register_user):
    """Better an explicit error than a blank map that looks like a bug."""
    register_user()
    assert client.get("/api/quest/Physics").status_code == 404
