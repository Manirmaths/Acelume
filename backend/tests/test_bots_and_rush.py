"""
Practice bots and Rush mode.

The bot tests are mostly about HONESTY rather than mechanics: a bot must
always be visibly a bot, must never be counted as a player, and must never
earn anything that ranks a student against real people. Those properties are
the difference between "a practice opponent" and "a fake friend", and they are
easy to break accidentally later.

The Rush tests are about the strike count actually ending runs, since that
single rule is what separates Rush from the timed Blitz it sits beside.
"""

import random

from app.bots import BOTS, BOTS_BY_KEY, answer, pick_for, public
from app.models import Question, QuizAttempt
from app.routers.rush import RUSH_MAX_STRIKES, build_ladder


def _seed(db_session, n=40, subject="Mathematics"):
    difficulties = ["easy", "medium", "hard"]
    for i in range(n):
        db_session.add(Question(
            question_id=f"seed-rush-{subject}-{i}",
            subject=subject, topic="Algebra",
            difficulty=difficulties[i % 3],
            source="original", status="active",
            question_text=f"Rush sample {i}?",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="B", explanation="Because B.",
        ))
    db_session.commit()


# ----------------------------------------------------------------- bots ----

def test_a_stronger_bot_gets_more_questions_right():
    """If this failed, bot ratings would be decorative."""
    rng = random.Random(1)
    weak = BOTS_BY_KEY["tunde"]
    strong = BOTS_BY_KEY["ms_bello"]

    def score(bot):
        r = random.Random(7)
        return sum(
            answer(bot, 1200.0, "B", ["A", "B", "C", "D"], r)[0] == "B"
            for _ in range(300)
        )

    assert score(strong) > score(weak)


def test_bots_are_beatable_and_fallible():
    """A bot that never misses is a wall, not an opponent."""
    r = random.Random(3)
    got = [answer(BOTS_BY_KEY["chidi"], 1200.0, "B", ["A", "B", "C", "D"], r)[0] for _ in range(200)]
    assert 0 < got.count("B") < 200


def test_a_bot_never_leaves_a_question_blank():
    """A bot that skipped questions would be trivially beatable and look broken."""
    r = random.Random(5)
    for _ in range(100):
        chosen, _ = answer(BOTS_BY_KEY["amara"], 1500.0, "B", ["A", "B", "C", "D"], r)
        assert chosen in {"A", "B", "C", "D"}


def test_bot_answers_are_deterministic_for_a_given_seed():
    """
    Grading is idempotent and may run more than once. A bot whose score
    changed between two reads of the same battle would look like cheating.
    """
    first = [answer(BOTS_BY_KEY["chidi"], 1200.0, "B", ["A", "B", "C", "D"], random.Random(42))
             for _ in range(5)]
    second = [answer(BOTS_BY_KEY["chidi"], 1200.0, "B", ["A", "B", "C", "D"], random.Random(42))
              for _ in range(5)]
    assert first == second


def test_a_bot_takes_a_plausible_amount_of_time():
    r = random.Random(11)
    times = [answer(BOTS_BY_KEY["ms_bello"], 1200.0, "B", ["A", "B", "C", "D"], r)[1]
             for _ in range(100)]
    assert all(t >= 2 for t in times), "no instant answers"
    assert max(times) < 120, "no implausibly slow answers"


def test_matchmaking_picks_an_opponent_just_above_the_student():
    """Slightly above, not equal -- a coin flip is less motivating than a stretch."""
    bot = pick_for(900.0)
    assert bot.rating >= 900.0


def test_a_brand_new_student_gets_the_easiest_bot():
    """An early thrashing is the fastest way to lose a new student."""
    assert pick_for(None).key == "tunde"


def test_a_strong_student_gets_the_strongest_bot():
    assert pick_for(1500.0).key == "ms_bello"


def test_every_bot_is_publicly_declared_a_bot():
    """Never inferable-only. This is the honesty rule in its simplest form."""
    for bot in BOTS:
        assert public(bot)["is_bot"] is True


def test_bots_are_rated_across_a_useful_spread():
    ratings = sorted(b.rating for b in BOTS)
    assert ratings[0] < 800 and ratings[-1] > 1300


# ------------------------------------------------------------ bot battle ----

def test_a_bot_battle_is_playable_immediately(client, register_user, db_session):
    """The whole point: no waiting, no code to share, no second human."""
    _seed(db_session)
    register_user()

    res = client.post("/api/battles", json={
        "subject": "Mathematics", "questions": 5, "mode": "async", "vs_bot": True,
    })
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["vs_bot"] is True
    assert body["players"] == 2, "the student should not be told to wait for an opponent"


def test_a_bot_battle_resolves_without_a_second_player(client, register_user, db_session):
    _seed(db_session)
    register_user()

    battle = client.post("/api/battles", json={
        "subject": "Mathematics", "questions": 5, "mode": "async", "vs_bot": True,
    }).json()
    questions = client.get(f"/api/battles/{battle['code']}/questions").json()

    answers = {str(q["id"]): {"selected": "B", "seconds": 5} for q in questions}
    result = client.post(f"/api/battles/{battle['code']}/submit", json={"answers": answers}).json()

    assert result["outcome"] in {"won", "lost", "draw"}, "a bot battle must never sit on 'waiting'"
    assert result["opponent"] is not None
    assert result["opponent"]["is_bot"] is True
    assert result["vs_bot"] is True


def test_the_opponent_is_labelled_a_bot_in_the_result(client, register_user, db_session):
    _seed(db_session)
    register_user()
    battle = client.post("/api/battles", json={
        "subject": "Mathematics", "questions": 5, "mode": "async", "vs_bot": True,
    }).json()
    client.post(f"/api/battles/{battle['code']}/submit", json={"answers": {}})

    result = client.get(f"/api/battles/{battle['code']}").json()
    assert result["opponent"]["is_bot"] is True
    assert result["opponent"]["bot_blurb"]


def test_a_bot_battle_awards_no_mastery_points(client, register_user, db_session):
    """
    The load-bearing honesty rule. If farming bots moved league position, a
    student who plays people would be out-ranked by one who plays a
    probability distribution.
    """
    from app.models import MasteryPointLedger, User

    _seed(db_session)
    register_user()
    battle = client.post("/api/battles", json={
        "subject": "Mathematics", "questions": 5, "mode": "async", "vs_bot": True,
    }).json()
    questions = client.get(f"/api/battles/{battle['code']}/questions").json()
    answers = {str(q["id"]): {"selected": "B", "seconds": 5} for q in questions}
    client.post(f"/api/battles/{battle['code']}/submit", json={"answers": answers})

    user = db_session.query(User).filter(User.username == "student1").first()
    points = db_session.query(MasteryPointLedger).filter(
        MasteryPointLedger.user_id == user.id
    ).all()
    assert points == []


def test_a_bots_score_does_not_change_between_reads(client, register_user, db_session):
    _seed(db_session)
    register_user()
    battle = client.post("/api/battles", json={
        "subject": "Mathematics", "questions": 5, "mode": "async", "vs_bot": True,
    }).json()
    client.post(f"/api/battles/{battle['code']}/submit", json={"answers": {}})

    first = client.get(f"/api/battles/{battle['code']}").json()["opponent"]
    second = client.get(f"/api/battles/{battle['code']}").json()["opponent"]
    assert first == second


def test_the_bot_roster_is_listed(client, register_user, db_session):
    register_user()
    res = client.get("/api/battles/bots")
    assert res.status_code == 200
    assert all(b["is_bot"] for b in res.json())


# ------------------------------------------------------------------ rush ----

def test_three_strikes_ends_the_run(client, register_user, db_session):
    """The one rule that makes Rush a different thing from Blitz."""
    _seed(db_session)
    register_user()

    attempt = client.post("/api/rush/start", json={"subject": "Mathematics"}).json()
    attempt_id = attempt["attempt_id"]

    finished = False
    for _ in range(RUSH_MAX_STRIKES):
        current = client.get(f"/api/quiz/{attempt_id}").json()
        if current["finished"]:
            finished = True
            break
        res = client.post(f"/api/quiz/{attempt_id}/answer", json={
            "question_id": current["current_question"]["id"],
            "selected_option": "A",  # wrong: seeded questions are all B
        })
        assert res.status_code == 200, res.text
        finished = res.json()["next"]["finished"]

    assert finished is True, "the run should have ended on the third strike"

    state = client.get(f"/api/rush/{attempt_id}/state").json()
    assert state["strikes"] == RUSH_MAX_STRIKES
    assert state["finished"] is True


def test_correct_answers_do_not_add_strikes(client, register_user, db_session):
    _seed(db_session)
    register_user()

    attempt = client.post("/api/rush/start", json={"subject": "Mathematics"}).json()
    attempt_id = attempt["attempt_id"]

    for _ in range(5):
        current = client.get(f"/api/quiz/{attempt_id}").json()
        if current["finished"]:
            break
        client.post(f"/api/quiz/{attempt_id}/answer", json={
            "question_id": current["current_question"]["id"],
            "selected_option": "B",  # correct
        })

    state = client.get(f"/api/rush/{attempt_id}/state").json()
    assert state["strikes"] == 0
    assert state["score"] == 5
    assert state["finished"] is False


def test_two_strikes_does_not_end_the_run(client, register_user, db_session):
    _seed(db_session)
    register_user()
    attempt = client.post("/api/rush/start", json={"subject": "Mathematics"}).json()
    attempt_id = attempt["attempt_id"]

    for _ in range(RUSH_MAX_STRIKES - 1):
        current = client.get(f"/api/quiz/{attempt_id}").json()
        client.post(f"/api/quiz/{attempt_id}/answer", json={
            "question_id": current["current_question"]["id"],
            "selected_option": "A",
        })

    state = client.get(f"/api/rush/{attempt_id}/state").json()
    assert state["strikes"] == RUSH_MAX_STRIKES - 1
    assert state["finished"] is False


def test_rush_has_no_timer(client, register_user, db_session):
    """
    Adding a clock as well would collapse Rush back into Blitz. The strike
    count is supposed to be the entire source of pressure.
    """
    _seed(db_session)
    register_user()
    attempt = client.post("/api/rush/start", json={"subject": "Mathematics"}).json()
    assert attempt["time_limit_seconds"] is None


def test_the_ladder_gets_harder(db_session):
    """
    Escalating difficulty is what gives every student a natural ceiling. A flat
    random order would bore a strong student and bury a weak one.
    """
    _seed(db_session, n=60)
    pool = db_session.query(Question).all()
    ladder = build_ladder(db_session, user_id=1, subject="Mathematics", pool=pool, n=30)

    from app.rating_service import question_rating_for
    ratings = [question_rating_for(db_session, q)[0] for q in ladder]

    first_third = sum(ratings[:10]) / 10
    last_third = sum(ratings[-10:]) / 10
    assert last_third > first_third


def test_rush_refuses_an_unknown_subject(client, register_user, db_session):
    register_user()
    assert client.post("/api/rush/start", json={"subject": "Astrology"}).status_code == 404


def test_rush_needs_a_reasonable_pool(client, register_user, db_session):
    _seed(db_session, n=3)
    register_user()
    assert client.post("/api/rush/start", json={"subject": "Mathematics"}).status_code == 400
