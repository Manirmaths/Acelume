"""
Daily missions.

The rules worth testing are the ones that make a mission list trustworthy: it
must never contain something the student cannot do, it must not regenerate,
and finishing it must pay out exactly once.
"""

from datetime import timedelta

from app.gamification import config, missions as svc
from app.models import DailyMission, DailyReward, Question, SyllabusTopic, TopicMastery, User

_seq = [0]


def _questions(db, subject="Mathematics", topic="Algebraic Processes", n=20):
    for _ in range(n):
        _seq[0] += 1
        db.add(Question(
            question_id=f"MIS-{_seq[0]:05d}", subject=subject, topic=topic,
            difficulty="easy", question_text="Q?", option_a="A", option_b="B",
            option_c="C", option_d="D", correct_option="A",
            explanation="x", source="original", status="active",
        ))
    db.commit()


def _syllabus(db):
    a = SyllabusTopic(subject="Mathematics", topic="Algebraic Processes", order_index=0,
                      estimated_minutes=15)
    db.add(a)
    db.flush()
    b = SyllabusTopic(subject="Mathematics", topic="Calculus", order_index=1,
                      prerequisite_id=a.id, estimated_minutes=20)
    db.add(b)
    db.commit()
    return a, b


def test_three_missions_one_of_each_kind(client, register_user, db_session):
    register_user()
    _questions(db_session)
    _syllabus(db_session)

    data = client.get("/api/missions").json()
    assert len(data["items"]) == 3
    assert {i["kind"] for i in data["items"]} == {"progress", "practice", "improvement"}


def test_missions_do_not_regenerate_on_reload(client, register_user, db_session):
    """A second request must return the same missions, not a new set."""
    register_user()
    _questions(db_session)
    _syllabus(db_session)

    first = client.get("/api/missions").json()
    second = client.get("/api/missions").json()

    assert [i["title"] for i in first["items"]] == [i["title"] for i in second["items"]]
    assert db_session.query(DailyMission).count() == 3


def test_missions_never_target_a_locked_topic(client, register_user, db_session):
    """The hardest rule in the spec: a mission pointing at content the student
    cannot open is worse than no mission at all."""
    register_user()
    _questions(db_session, topic="Algebraic Processes")
    _questions(db_session, topic="Calculus")
    _syllabus(db_session)

    data = client.get("/api/missions").json()
    targeted = {i["topic"] for i in data["items"] if i["topic"]}
    assert "Calculus" not in targeted, "Calculus is locked behind Algebraic Processes"


def test_new_student_gets_no_impossible_correction_mission(client, register_user, db_session):
    """A brand-new student has no mistakes to correct, so asking them to fix
    five would be unachievable on day one."""
    register_user()
    _questions(db_session)
    _syllabus(db_session)

    data = client.get("/api/missions").json()
    improvement = next(i for i in data["items"] if i["kind"] == "improvement")
    assert "previously missed" not in improvement["title"]


def test_daily_budget_stays_reasonable(client, register_user, db_session):
    """The spec budgets 15-30 minutes for the whole day."""
    register_user()
    _questions(db_session)
    _syllabus(db_session)

    data = client.get("/api/missions").json()
    assert 10 <= data["total_minutes"] <= 45, data["total_minutes"]


def test_reward_is_disclosed_before_completion(client, register_user, db_session):
    """No mystery boxes: the spec rules out gambling-style mechanics."""
    register_user()
    _questions(db_session)
    _syllabus(db_session)

    data = client.get("/api/missions").json()
    assert data["reward_xp"] == config.DEFAULTS["xp_all_missions"]
    assert data["reward_claimed"] is False


def test_chest_pays_out_exactly_once(client, register_user, db_session):
    register_user()
    _questions(db_session)
    _syllabus(db_session)
    client.get("/api/missions")

    user = db_session.query(User).first()
    for m in db_session.query(DailyMission).all():
        m.progress = m.target
        m.completed_at = __import__("datetime").datetime.utcnow()
    db_session.commit()

    first = svc.try_award_daily_chest(db_session, user)
    db_session.commit()
    second = svc.try_award_daily_chest(db_session, user)
    db_session.commit()

    assert first == config.DEFAULTS["xp_all_missions"]
    assert second == 0, "the same day must not pay out twice"
    assert db_session.query(DailyReward).count() == 1


def test_incomplete_missions_pay_nothing(client, register_user, db_session):
    register_user()
    _questions(db_session)
    _syllabus(db_session)
    client.get("/api/missions")

    user = db_session.query(User).first()
    assert svc.try_award_daily_chest(db_session, user) == 0


def test_answering_questions_advances_the_practice_mission(client, register_user, db_session):
    register_user()
    _questions(db_session, n=25)
    _syllabus(db_session)
    client.get("/api/missions")

    attempt = client.post("/api/quiz/start", json={"subject": "Mathematics", "n": 3}).json()
    current = attempt["current_question"]
    while current is not None:
        r = client.post(
            f"/api/quiz/{attempt['attempt_id']}/answer",
            json={"question_id": current["id"], "selected_option": "A"},
        ).json()
        if r["next"]["finished"]:
            break
        current = r["next"]["current_question"]

    practice = (
        db_session.query(DailyMission)
        .filter(DailyMission.kind == "practice")
        .first()
    )
    db_session.refresh(practice)
    assert practice.progress > 0, "correct answers should advance the practice mission"
