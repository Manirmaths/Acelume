"""
Asynchronous quiz battles.

The tests worth having are the anti-cheating ones: answers must not be
readable before submitting, both players must get the same questions, one
attempt each, and expired invitations must be dead.
"""

from datetime import datetime, timedelta

from app.models import Battle, BattleParticipant, Question, User

_seq = [0]


def _questions(db, subject="Mathematics", topic="Algebraic Processes", n=12):
    for _ in range(n):
        _seq[0] += 1
        db.add(Question(
            question_id=f"BAT-{_seq[0]:05d}", subject=subject, topic=topic,
            difficulty="easy", question_text="Q?", option_a="A", option_b="B",
            option_c="C", option_d="D", correct_option="A",
            explanation="because", source="original", status="active",
        ))
    db.commit()


def _second_user(client, db):
    """Register a second account and return a client logged in as them."""
    r = client.post("/api/auth/register", json={
        "username": "rival", "email": "rival@example.com", "password": "password123",
    })
    assert r.status_code == 201, r.text
    return r


def test_questions_never_include_the_answer(client, register_user, db_session):
    """A player must not be able to read correct_option from the network."""
    register_user()
    _questions(db_session)

    battle = client.post("/api/battles", json={"subject": "Mathematics", "questions": 5}).json()
    qs = client.get(f"/api/battles/{battle['code']}/questions").json()

    assert len(qs) == 5
    body = str(qs)
    assert "correct_option" not in body
    assert "explanation" not in body


def test_both_players_get_the_same_questions(client, register_user, db_session):
    register_user()
    _questions(db_session)
    battle = client.post("/api/battles", json={"subject": "Mathematics", "questions": 5}).json()
    mine = [q["id"] for q in client.get(f"/api/battles/{battle['code']}/questions").json()]

    _second_user(client, db_session)
    client.post(f"/api/battles/{battle['code']}/join")
    theirs = [q["id"] for q in client.get(f"/api/battles/{battle['code']}/questions").json()]

    assert mine == theirs, "the question set is fixed server-side at creation"


def test_answers_appear_only_after_you_submit(client, register_user, db_session):
    register_user()
    _questions(db_session)
    battle = client.post("/api/battles", json={"subject": "Mathematics", "questions": 5}).json()

    before = client.get(f"/api/battles/{battle['code']}").json()
    assert before["review"] == [], "no review before submitting"

    qs = client.get(f"/api/battles/{battle['code']}/questions").json()
    answers = {str(q["id"]): {"selected": "A", "seconds": 5} for q in qs}
    after = client.post(f"/api/battles/{battle['code']}/submit", json={"answers": answers}).json()

    assert after["you"]["score"] == 5
    assert len(after["review"]) == 5
    assert after["review"][0]["correct_option"] == "A"


def test_resubmitting_cannot_improve_a_score(client, register_user, db_session):
    register_user()
    _questions(db_session)
    battle = client.post("/api/battles", json={"subject": "Mathematics", "questions": 5}).json()
    qs = client.get(f"/api/battles/{battle['code']}/questions").json()

    wrong = {str(q["id"]): {"selected": "B", "seconds": 3} for q in qs}
    first = client.post(f"/api/battles/{battle['code']}/submit", json={"answers": wrong}).json()
    assert first["you"]["score"] == 0

    right = {str(q["id"]): {"selected": "A", "seconds": 3} for q in qs}
    second = client.post(f"/api/battles/{battle['code']}/submit", json={"answers": right}).json()
    assert second["you"]["score"] == 0, "one valid attempt each -- a retry must not re-grade"


def test_expired_invitation_cannot_be_joined(client, register_user, db_session):
    register_user()
    _questions(db_session)
    battle = client.post("/api/battles", json={"subject": "Mathematics", "questions": 5}).json()

    row = db_session.query(Battle).filter(Battle.code == battle["code"]).first()
    row.expires_at = datetime.utcnow() - timedelta(hours=1)
    db_session.commit()

    _second_user(client, db_session)
    r = client.post(f"/api/battles/{battle['code']}/join")
    assert r.status_code == 410


def test_a_third_player_cannot_join(client, register_user, db_session):
    register_user()
    _questions(db_session)
    battle = client.post("/api/battles", json={"subject": "Mathematics", "questions": 5}).json()

    _second_user(client, db_session)
    assert client.post(f"/api/battles/{battle['code']}/join").status_code == 200

    r = client.post("/api/auth/register", json={
        "username": "third", "email": "third@example.com", "password": "password123",
    })
    assert r.status_code == 201
    assert client.post(f"/api/battles/{battle['code']}/join").status_code == 400


def test_non_participant_cannot_read_a_battle(client, register_user, db_session):
    register_user()
    _questions(db_session)
    battle = client.post("/api/battles", json={"subject": "Mathematics", "questions": 5}).json()

    client.post("/api/auth/register", json={
        "username": "nosy", "email": "nosy@example.com", "password": "password123",
    })
    assert client.get(f"/api/battles/{battle['code']}/questions").status_code == 403


def test_correctness_beats_speed(db_session):
    """The whole tiebreak design: a faster player with fewer correct loses."""
    from app.routers.battles import _decide

    slow_accurate = BattleParticipant(battle_id=1, user_id=1, score=8, attempted=10, correct_seconds=200)
    fast_sloppy = BattleParticipant(battle_id=1, user_id=2, score=5, attempted=10, correct_seconds=25)
    assert _decide(slow_accurate, fast_sloppy) == "won"
    assert _decide(fast_sloppy, slow_accurate) == "lost"


def test_speed_only_breaks_a_genuine_tie(db_session):
    from app.routers.battles import _decide

    a = BattleParticipant(battle_id=1, user_id=1, score=7, attempted=10, correct_seconds=70)
    b = BattleParticipant(battle_id=1, user_id=2, score=7, attempted=10, correct_seconds=140)
    assert _decide(a, b) == "won", "equal scores -> faster on correct answers wins"

    c = BattleParticipant(battle_id=1, user_id=3, score=7, attempted=10, correct_seconds=70)
    assert _decide(a, c) == "draw"


def test_attempting_more_beats_attempting_fewer_at_equal_score(db_session):
    from app.routers.battles import _decide

    braver = BattleParticipant(battle_id=1, user_id=1, score=5, attempted=10, correct_seconds=50)
    cautious = BattleParticipant(battle_id=1, user_id=2, score=5, attempted=5, correct_seconds=25)
    assert _decide(braver, cautious) == "won"
