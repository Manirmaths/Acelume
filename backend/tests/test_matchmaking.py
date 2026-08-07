"""
Matchmaking and recent opponents.

Two things are being protected here.

The product one: **nobody ever waits.** "Find an opponent" must always produce
a playable battle. A matchmaking button that yields a spinner is worse than no
button, because it converts a working feature into a broken-looking one.

The safeguarding one: **no way to reach a specific child.** There is no search
and no friend request anywhere in this system. A student cannot choose their
opponent; the system pairs them. Recent opponents only ever contains people
they already agreed to play. If a future change adds discovery, these tests
should be the thing that notices.
"""

import itertools
from datetime import datetime, timedelta

from app import matchmaking
from app.models import Battle, BattleParticipant, Question, SubjectRating, User


def _seed(db_session, n=40, subject="Mathematics"):
    for i in range(n):
        db_session.add(Question(
            question_id=f"mm-{subject}-{i}", subject=subject, topic="Algebra",
            difficulty="medium", source="original", status="active",
            question_text=f"Q{i}?", option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="B", explanation="Because B.",
        ))
    db_session.commit()


def _user(db_session, username, rating=None, subject="Mathematics"):
    u = User(username=username, email=f"{username}@example.com", password_hash="x")
    db_session.add(u)
    db_session.commit()
    if rating is not None:
        db_session.add(SubjectRating(
            user_id=u.id, subject=subject, rating=rating,
            deviation=60.0, volatility=0.06, peak_rating=rating,
            week_start_rating=rating, answers_counted=50,
        ))
        db_session.commit()
    return u


# Battle.code is UNIQUE, so a fixed-per-creator code breaks any test that
# creates two battles for the same person.
_codes = itertools.count(1)


def _open_battle(db_session, creator, subject="Mathematics", questions=5, mode="async", minutes_ago=1):
    qs = db_session.query(Question).filter(Question.subject == subject).limit(questions).all()
    b = Battle(
        code=f"T{next(_codes):05d}",
        created_by=creator.id, subject=subject, topic=None,
        question_ids=[q.id for q in qs], seconds_per_question=30,
        mode=mode, status="open",
        expires_at=datetime.utcnow() + timedelta(hours=48),
        created_at=datetime.utcnow() - timedelta(minutes=minutes_ago),
    )
    db_session.add(b)
    db_session.commit()
    db_session.add(BattleParticipant(battle_id=b.id, user_id=creator.id))
    db_session.commit()
    return b


# --------------------------------------------------------- pairing ----

def test_no_open_battles_means_no_match(db_session):
    """The caller then gives them a bot -- see the endpoint test below."""
    _seed(db_session)
    me = _user(db_session, "solo", rating=1200)
    assert matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async") is None


def test_a_comparable_opponent_is_matched(db_session):
    _seed(db_session)
    me = _user(db_session, "me", rating=1200)
    peer = _user(db_session, "peer", rating=1230)
    battle = _open_battle(db_session, peer)

    found = matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async")
    assert found is not None and found.id == battle.id


def test_the_closest_rating_wins(db_session):
    """A tight pairing is better practice than any warm body."""
    _seed(db_session)
    me = _user(db_session, "me", rating=1200)
    _user(db_session, "faraway", rating=1900)
    close = _user(db_session, "close", rating=1215)

    far_battle = _open_battle(db_session, db_session.query(User).filter(User.username == "faraway").one())
    close_battle = _open_battle(db_session, close)

    found = matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async")
    assert found.id == close_battle.id
    assert found.id != far_battle.id


def test_a_distant_opponent_is_better_than_none(db_session):
    """
    The bands widen rather than insisting on a perfect match. An empty result
    when someone IS waiting would be the worst of both worlds.
    """
    _seed(db_session)
    me = _user(db_session, "me", rating=1200)
    distant = _user(db_session, "distant", rating=1700)
    _open_battle(db_session, distant)

    assert matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async") is not None


def test_you_are_never_matched_into_your_own_challenge(db_session):
    _seed(db_session)
    me = _user(db_session, "me", rating=1200)
    _open_battle(db_session, me)

    assert matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async") is None


def test_you_are_never_matched_into_a_bot_game(db_session):
    """
    Somebody else's practice game is not a pairing. Joining one would put two
    humans and a simulated opponent in the same battle.
    """
    _seed(db_session)
    me = _user(db_session, "me", rating=1200)
    peer = _user(db_session, "peer", rating=1200)
    b = _open_battle(db_session, peer)
    b.bot_key = "tunde"
    db_session.commit()

    assert matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async") is None


def test_a_full_battle_is_not_offered(db_session):
    _seed(db_session)
    me = _user(db_session, "me", rating=1200)
    a = _user(db_session, "a", rating=1200)
    b = _user(db_session, "b", rating=1200)
    battle = _open_battle(db_session, a)
    db_session.add(BattleParticipant(battle_id=battle.id, user_id=b.id))
    db_session.commit()

    assert matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async") is None


def test_a_stale_challenge_is_not_offered(db_session):
    """Whoever made it hours ago has moved on. Pairing into it wastes a session."""
    _seed(db_session)
    me = _user(db_session, "me", rating=1200)
    peer = _user(db_session, "peer", rating=1200)
    _open_battle(db_session, peer, minutes_ago=matchmaking.OPEN_BATTLE_FRESHNESS_MINUTES + 30)

    assert matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async") is None


def test_subject_and_length_must_agree(db_session):
    _seed(db_session)
    _seed(db_session, subject="Physics")
    me = _user(db_session, "me", rating=1200)
    peer = _user(db_session, "peer", rating=1200)
    _open_battle(db_session, peer, subject="Physics")

    assert matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async") is None


def test_mode_must_agree(db_session):
    _seed(db_session)
    me = _user(db_session, "me", rating=1200)
    peer = _user(db_session, "peer", rating=1200)
    _open_battle(db_session, peer, mode="live")

    assert matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async") is None


def test_an_unrated_student_still_gets_matched(db_session):
    """A brand-new student must not be locked out of the only social feature."""
    _seed(db_session)
    me = _user(db_session, "fresh")           # no SubjectRating row
    peer = _user(db_session, "peer", rating=1250)
    _open_battle(db_session, peer)

    assert matchmaking.find_open_battle(db_session, me, "Mathematics", 5, "async") is not None


# ------------------------------------------------------- endpoint ----

def test_find_always_returns_a_playable_battle(client, register_user, db_session):
    """
    The load-bearing product guarantee. With nobody waiting, the student gets a
    bot rather than a queue -- a spinner here would make the feature look broken.
    """
    _seed(db_session)
    register_user()

    res = client.post("/api/battles/find", json={
        "subject": "Mathematics", "questions": 5, "mode": "async",
    })
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["players"] == 2, "never left waiting for an opponent"
    assert body["vs_bot"] is True


def test_find_prefers_a_human_over_a_bot(client, register_user, db_session):
    _seed(db_session)
    waiting = _user(db_session, "waiting", rating=1200)
    _open_battle(db_session, waiting)
    register_user()

    body = client.post("/api/battles/find", json={
        "subject": "Mathematics", "questions": 5, "mode": "async",
    }).json()

    assert body["vs_bot"] is False, "a real opponent was available and should have been used"


def test_find_validates_its_input(client, register_user, db_session):
    _seed(db_session)
    register_user()
    assert client.post("/api/battles/find", json={"subject": "Astrology", "questions": 5}).status_code == 404
    assert client.post("/api/battles/find", json={"subject": "Mathematics", "questions": 7}).status_code == 400


# ----------------------------------------------- recent opponents ----

def test_no_history_means_no_recent_opponents(client, register_user, db_session):
    register_user()
    assert client.get("/api/battles/recent-opponents").json() == []


def test_someone_you_played_appears(db_session):
    _seed(db_session)
    me = _user(db_session, "me")
    them = _user(db_session, "them")
    battle = _open_battle(db_session, them)
    db_session.add(BattleParticipant(battle_id=battle.id, user_id=me.id))
    db_session.commit()

    rows = matchmaking.recent_opponents(db_session, me.id)
    assert len(rows) == 1
    assert rows[0]["username"] == "them"


def test_bot_games_never_appear_as_opponents(db_session):
    """
    A bot is not someone you played. Listing one here would blur the honesty
    line the whole bot design rests on.
    """
    _seed(db_session)
    me = _user(db_session, "me")
    battle = _open_battle(db_session, me)
    battle.bot_key = "amara"
    db_session.commit()

    assert matchmaking.recent_opponents(db_session, me.id) == []


def test_you_never_appear_in_your_own_list(db_session):
    _seed(db_session)
    me = _user(db_session, "me")
    them = _user(db_session, "them")
    battle = _open_battle(db_session, them)
    db_session.add(BattleParticipant(battle_id=battle.id, user_id=me.id))
    db_session.commit()

    assert all(r["username"] != "me" for r in matchmaking.recent_opponents(db_session, me.id))


def test_a_repeat_opponent_is_listed_once_with_a_count(db_session):
    _seed(db_session)
    me = _user(db_session, "me")
    them = _user(db_session, "them")
    for _ in range(3):
        battle = _open_battle(db_session, them)
        db_session.add(BattleParticipant(battle_id=battle.id, user_id=me.id))
        db_session.commit()

    rows = matchmaking.recent_opponents(db_session, me.id)
    assert len(rows) == 1
    assert rows[0]["played"] == 3


def test_recent_opponents_exposes_nothing_beyond_a_username(db_session):
    """
    Safeguarding, enforced by shape. No email, no rating, no contact details --
    there must be no way to reach a student outside a battle.
    """
    _seed(db_session)
    me = _user(db_session, "me")
    them = _user(db_session, "them", rating=1400)
    battle = _open_battle(db_session, them)
    db_session.add(BattleParticipant(battle_id=battle.id, user_id=me.id))
    db_session.commit()

    row = matchmaking.recent_opponents(db_session, me.id)[0]
    assert set(row) == {"user_id", "username", "subject", "last_played", "played"}
    assert "email" not in row and "rating" not in row


def test_there_is_no_way_to_search_for_a_student(client, register_user, db_session):
    """
    The design decision this whole module rests on. If a future change adds
    user search, this test is what should stop it going out unnoticed.
    """
    register_user()
    for path in ("/api/battles/search", "/api/battles/users", "/api/users/search"):
        assert client.get(path).status_code in (404, 405), f"{path} should not exist"
