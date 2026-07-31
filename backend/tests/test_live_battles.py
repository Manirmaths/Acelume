"""
Live (synchronous) battles.

Every test here is about the same property: the SERVER owns the clock. A
client cannot answer early, answer late, revise an answer after seeing the
opponent, or forfeit by losing signal.
"""

from datetime import datetime, timedelta

from app.models import Battle, BattleParticipant, Question

_seq = [0]


def _questions(db, n=10):
    for _ in range(n):
        _seq[0] += 1
        db.add(Question(
            question_id=f"LIVE-{_seq[0]:05d}", subject="Mathematics",
            topic="Algebraic Processes", difficulty="easy", question_text="Q?",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="A", explanation="x", source="original", status="active",
        ))
    db.commit()


def _make_live(client, db, questions=5):
    _questions(db)
    b = client.post("/api/battles", json={
        "subject": "Mathematics", "questions": questions, "mode": "live",
    }).json()
    return b


def _rewind(db, code, seconds):
    """Pretend the battle started `seconds` ago."""
    row = db.query(Battle).filter(Battle.code == code).first()
    row.started_at = datetime.utcnow() - timedelta(seconds=seconds)
    db.commit()
    return row


def test_live_battle_does_not_start_until_the_second_player_joins(client, register_user, db_session):
    register_user()
    b = _make_live(client, db_session)

    state = client.get(f"/api/battles/{b['code']}/live").json()
    assert state["started"] is False
    assert state["current_index"] is None


def test_current_question_is_derived_from_the_server_clock(client, register_user, db_session):
    register_user()
    b = _make_live(client, db_session, questions=5)
    _rewind(db_session, b["code"], 0)

    # 30s per question: 65 seconds in means question index 2.
    _rewind(db_session, b["code"], 65)
    state = client.get(f"/api/battles/{b['code']}/live").json()
    assert state["started"] is True
    assert state["current_index"] == 2
    assert 0 <= state["seconds_remaining"] <= 30


def test_cannot_answer_a_future_question(client, register_user, db_session):
    register_user()
    b = _make_live(client, db_session)
    _rewind(db_session, b["code"], 5)  # on question 0

    r = client.post(f"/api/battles/{b['code']}/live/answer", json={"index": 3, "selected": "A"})
    assert r.status_code == 409, "answering ahead must be rejected"


def test_cannot_answer_a_closed_question(client, register_user, db_session):
    register_user()
    b = _make_live(client, db_session)
    _rewind(db_session, b["code"], 100)  # well past question 0

    r = client.post(f"/api/battles/{b['code']}/live/answer", json={"index": 0, "selected": "A"})
    assert r.status_code == 409


def test_grace_window_accepts_a_slightly_late_answer(client, register_user, db_session):
    """A student on a slow connection must not lose an answer that left
    their phone in time."""
    register_user()
    b = _make_live(client, db_session)
    # 31 seconds in: question 1 has just opened, question 0 closed 1s ago.
    _rewind(db_session, b["code"], 31)

    r = client.post(f"/api/battles/{b['code']}/live/answer", json={"index": 0, "selected": "A"})
    assert r.status_code == 200, "within the grace window this should be accepted"


def test_an_answer_cannot_be_revised(client, register_user, db_session):
    """Otherwise a player could change their mind after seeing the opponent
    pull ahead."""
    register_user()
    b = _make_live(client, db_session)
    _rewind(db_session, b["code"], 5)

    assert client.post(f"/api/battles/{b['code']}/live/answer",
                       json={"index": 0, "selected": "B"}).status_code == 200
    r = client.post(f"/api/battles/{b['code']}/live/answer", json={"index": 0, "selected": "A"})
    assert r.status_code == 409


def test_cannot_finish_while_the_battle_is_still_running(client, register_user, db_session):
    register_user()
    b = _make_live(client, db_session, questions=5)
    _rewind(db_session, b["code"], 60)  # 5 x 30s = 150s needed

    r = client.post(f"/api/battles/{b['code']}/live/finish")
    assert r.status_code == 400


def test_disconnected_player_still_scores_what_they_answered(client, register_user, db_session):
    """Losing signal must never forfeit a battle -- answers already given
    still count."""
    register_user()
    b = _make_live(client, db_session, questions=5)
    _rewind(db_session, b["code"], 5)
    client.post(f"/api/battles/{b['code']}/live/answer", json={"index": 0, "selected": "A"})

    # ...then vanish for the rest of the battle.
    _rewind(db_session, b["code"], 200)
    result = client.post(f"/api/battles/{b['code']}/live/finish").json()

    assert result["you"]["score"] == 1
    assert result["you"]["attempted"] == 1


def test_finishing_twice_does_not_re_grade(client, register_user, db_session):
    register_user()
    b = _make_live(client, db_session, questions=5)
    _rewind(db_session, b["code"], 200)

    first = client.post(f"/api/battles/{b['code']}/live/finish").json()
    second = client.post(f"/api/battles/{b['code']}/live/finish").json()
    assert first["you"]["score"] == second["you"]["score"]


def test_live_endpoints_reject_async_battles(client, register_user, db_session):
    register_user()
    _questions(db_session)
    b = client.post("/api/battles", json={
        "subject": "Mathematics", "questions": 5, "mode": "async",
    }).json()

    assert client.get(f"/api/battles/{b['code']}/live").status_code == 400


def test_reading_a_battle_reports_its_mode_without_joining_it(client, register_user, db_session):
    """The client must be able to tell live from async with a plain read.

    Regression: the UI briefly learned the mode by calling POST /join on page
    load, which meant merely opening a battle link entered you into the battle
    and consumed the second player slot. The mode belongs on the read.
    """
    register_user()
    b = _make_live(client, db_session)

    r = client.get(f"/api/battles/{b['code']}")
    assert r.status_code == 200
    assert r.json()["mode"] == "live"

    # And the read left the battle open -- nobody was silently enrolled.
    row = db_session.query(Battle).filter(Battle.code == b["code"]).first()
    joined = db_session.query(BattleParticipant).filter(
        BattleParticipant.battle_id == row.id
    ).count()
    assert joined == 1
    assert row.status == "open"
