"""
Weekly leagues.

The tests that matter are the ones protecting students from the feature:
opting out must cost nothing, an inactive account must not be demoted week
after week, and league points must not be XP.
"""

from datetime import date, timedelta

from app.gamification import config, leagues
from app.models import LeagueCohort, LeagueMembership, MasteryPointLedger, User, XpLedger


def _user(db, name, tier="foundation", opted_out=False):
    u = User(username=name, email=f"{name}@example.com", password_hash="x", points=0,
             league_tier=tier, league_opted_out=opted_out)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_points_are_idempotent_on_event_key(db_session):
    user = _user(db_session, "l1")
    key = "QUESTION_ANSWERED:attempt=1:q=1"

    first = leagues.award(db_session, user, event_type="QUESTION_ANSWERED", event_key=key)
    second = leagues.award(db_session, user, event_type="QUESTION_ANSWERED", event_key=key)
    db_session.commit()

    assert first == config.DEFAULTS["mp_correct_answer"]
    assert second == 0, "the same event must not score twice"
    assert db_session.query(MasteryPointLedger).count() == 1


def test_league_points_are_not_xp(db_session):
    """Ranking on XP would let a long-standing user top every league forever."""
    user = _user(db_session, "l2")
    leagues.award(db_session, user, event_type="TOPIC_MASTERED", event_key="TOPIC_MASTERED:M:Alg")
    db_session.commit()

    assert db_session.query(MasteryPointLedger).count() == 1
    assert db_session.query(XpLedger).count() == 0, "league points must not touch the XP ledger"
    assert user.points == 0


def test_opted_out_student_scores_nothing_and_joins_nothing(db_session):
    user = _user(db_session, "l3", opted_out=True)
    awarded = leagues.award(db_session, user, event_type="QUESTION_ANSWERED", event_key="k1")
    db_session.commit()

    assert awarded == 0
    assert db_session.query(LeagueMembership).count() == 0
    assert leagues.ensure_membership(db_session, user, leagues.current_week_start(user)) is None


def test_opting_out_leaves_learning_features_intact(client, register_user, db_session):
    register_user()
    r = client.put("/api/leagues/opt-out", json={"opted_out": True})
    assert r.status_code == 200
    assert r.json()["opted_out"] is True

    # The point of the requirement: nothing else breaks.
    assert client.get("/api/dashboard").status_code == 200
    assert client.get("/api/achievements").status_code == 200


def test_cohort_fills_to_capacity_then_opens_another(db_session):
    week = date(2026, 7, 27)
    for i in range(leagues.COHORT_SIZE + 3):
        u = _user(db_session, f"c{i}")
        leagues.ensure_membership(db_session, u, week)
    db_session.commit()

    cohorts = db_session.query(LeagueCohort).filter(LeagueCohort.week_start == week).all()
    assert len(cohorts) == 2, "a 21st student should open a second cohort"
    counts = sorted(
        db_session.query(LeagueMembership).filter(LeagueMembership.cohort_id == c.id).count()
        for c in cohorts
    )
    assert counts[-1] == leagues.COHORT_SIZE


def test_students_are_matched_within_their_own_tier(db_session):
    """A new student must not be dropped in with long-term heavy users."""
    week = date(2026, 7, 27)
    beginner = _user(db_session, "newbie", tier="foundation")
    veteran = _user(db_session, "veteran", tier="diamond")
    m1 = leagues.ensure_membership(db_session, beginner, week)
    m2 = leagues.ensure_membership(db_session, veteran, week)
    db_session.commit()

    assert m1.cohort_id != m2.cohort_id


def test_close_week_promotes_top_and_demotes_bottom(db_session):
    week = date(2026, 7, 27)
    users = []
    for i in range(10):
        u = _user(db_session, f"p{i}", tier="bronze")
        m = leagues.ensure_membership(db_session, u, week)
        m.points = 100 - i * 10  # p0 highest, p9 lowest
        users.append(u)
    db_session.commit()

    leagues.close_week(db_session, week)
    db_session.commit()

    assert users[0].league_tier == "silver", "top finisher should be promoted"
    assert users[9].league_tier == "foundation", "bottom finisher should be demoted"
    assert users[5].league_tier == "bronze", "mid-table stays"


def test_inactive_accounts_are_not_demoted(db_session):
    """The spec calls out repeatedly displaying inactive accounts at the
    bottom as humiliating and pointless."""
    week = date(2026, 7, 27)
    active = _user(db_session, "active1", tier="silver")
    idle = _user(db_session, "idle1", tier="silver")
    m1 = leagues.ensure_membership(db_session, active, week)
    m1.points = 50
    leagues.ensure_membership(db_session, idle, week)  # 0 points
    db_session.commit()

    leagues.close_week(db_session, week)
    db_session.commit()

    assert idle.league_tier == "silver", "an inactive account must not be demoted"
    membership = (
        db_session.query(LeagueMembership)
        .filter(LeagueMembership.user_id == idle.id)
        .first()
    )
    assert membership.outcome == "stayed"


def test_closing_twice_does_not_promote_twice(db_session):
    week = date(2026, 7, 27)
    u = _user(db_session, "once", tier="bronze")
    m = leagues.ensure_membership(db_session, u, week)
    m.points = 500
    db_session.commit()

    leagues.close_week(db_session, week)
    db_session.commit()
    tier_after_first = u.league_tier

    leagues.close_week(db_session, week)
    db_session.commit()

    assert u.league_tier == tier_after_first, "a re-run must not promote again"


def test_scholar_tier_does_not_overflow(db_session):
    week = date(2026, 7, 27)
    u = _user(db_session, "top", tier="scholar")
    m = leagues.ensure_membership(db_session, u, week)
    m.points = 999
    db_session.commit()

    leagues.close_week(db_session, week)
    db_session.commit()
    assert u.league_tier == "scholar", "there is no tier above the highest"


def test_league_endpoint_exposes_no_personal_data(client, register_user, db_session):
    register_user()
    data = client.get("/api/leagues").json()
    body = str(data)
    assert "@" not in body, "email addresses must never appear in league data"
    assert "tier" in data and "entries" in data


def test_duplicate_award_does_not_discard_other_pending_work(db_session):
    """A replayed event must undo its own row and nothing else.

    Regression, and the nastiest bug in this module's history. The duplicate
    handler called `db.rollback()`, which discards the entire transaction --
    not the failed INSERT. `award()` runs inside the same session as the
    request that triggered it, so a replayed key threw away whatever that
    request had already written. In practice: the student answers a question,
    a duplicate event key collides, and their ANSWER vanishes. No exception,
    no log line, HTTP 200.
    """
    user = _user(db_session, "l-tx")
    key = "QUESTION_ANSWERED:attempt=9:q=9"
    leagues.award(db_session, user, event_type="QUESTION_ANSWERED", event_key=key)

    # Unrelated work, pending in the same transaction -- stands in for the
    # student's answer row.
    bystander = User(username="bystander", email="bystander@example.com", password_hash="x")
    db_session.add(bystander)
    db_session.flush()

    assert leagues.award(db_session, user, event_type="QUESTION_ANSWERED", event_key=key) == 0
    db_session.commit()

    assert db_session.query(User).filter(User.username == "bystander").count() == 1, \
        "the duplicate rolled back work it did not own"
    assert db_session.query(MasteryPointLedger).count() == 1


def test_winner_of_a_small_cohort_is_never_demoted(db_session):
    """With few active students the top and bottom zones overlap.

    Early cohorts are undersized by definition -- they fill to COHORT_SIZE over
    time. Coming first must never relegate you, at any tier.
    """
    week = date(2026, 7, 27)
    users = [_user(db_session, f"small{i}", tier="bronze") for i in range(3)]
    for i, u in enumerate(users):
        m = leagues.ensure_membership(db_session, u, week)
        m.points = 100 - i * 10
    db_session.commit()

    leagues.close_week(db_session, week)
    db_session.commit()

    assert all(u.league_tier != "foundation" for u in users), \
        "nobody is demoted out of a cohort too small to have a bottom"
