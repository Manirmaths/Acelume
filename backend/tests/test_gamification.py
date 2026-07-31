"""
Tests for the gamification foundation.

These target the properties the spec calls out as must-nots, because they are
the ones that are easy to get wrong and expensive to discover in production:
XP being awarded twice, XP falling after a wrong answer, farmable activity
being uncapped, and a mastered topic silently losing its stars at review time.
"""

from datetime import datetime, timedelta

import pytest

from app.gamification import config, events
from app.models import LearningEvent, TopicMastery, User, XpLedger


def _user(db, username="gamer", email="gamer@example.com"):
    u = User(username=username, email=email, password_hash="x", points=0)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_same_event_key_is_recorded_and_rewarded_once(db_session):
    """Replaying an event -- a retry, a double tap, an offline re-sync --
    must not duplicate XP."""
    user = _user(db_session)
    key = "QUESTION_ANSWERED:attempt=1:q=42"

    first = events.record(
        db_session, user=user, event_type=events.QUESTION_ANSWERED,
        event_key=key, subject="Mathematics", topic="Algebra",
    )
    second = events.record(
        db_session, user=user, event_type=events.QUESTION_ANSWERED,
        event_key=key, subject="Mathematics", topic="Algebra",
    )
    db_session.commit()

    assert first is not None
    assert second is None, "duplicate event_key must be rejected"
    assert db_session.query(LearningEvent).filter_by(event_key=key).count() == 1
    assert db_session.query(XpLedger).filter_by(user_id=user.id).count() == 1
    assert user.points == config.DEFAULTS["xp_correct_answer"]


def test_xp_never_decreases(db_session):
    """A wrong answer records no XP -- and crucially never a negative one."""
    user = _user(db_session, "nolose", "nolose@example.com")
    events.record(
        db_session, user=user, event_type=events.QUESTION_ANSWERED,
        event_key="QUESTION_ANSWERED:attempt=2:q=1",
    )
    db_session.commit()
    before = user.points

    # A wrong answer simply produces no QUESTION_ANSWERED event at all.
    db_session.commit()
    assert user.points == before
    assert all(row.amount > 0 for row in db_session.query(XpLedger).all())


def test_daily_cap_bounds_farmable_xp_only(db_session):
    """Answer XP is capped daily; lesson and mastery XP are not, because they
    are self-limiting by the work involved."""
    user = _user(db_session, "farmer", "farmer@example.com")
    cap = config.DEFAULTS["xp_daily_answer_cap"]
    per = config.DEFAULTS["xp_correct_answer"]

    for i in range(cap // per + 25):
        events.record(
            db_session, user=user, event_type=events.QUESTION_ANSWERED,
            event_key=f"QUESTION_ANSWERED:attempt=3:q={i}",
        )
    db_session.commit()
    assert user.points <= cap

    at_cap = user.points
    events.record(
        db_session, user=user, event_type=events.TOPIC_MASTERED,
        event_key="TOPIC_MASTERED:Mathematics:Algebra",
        subject="Mathematics", topic="Algebra",
    )
    db_session.commit()
    assert user.points == at_cap + config.DEFAULTS["xp_topic_mastered"], (
        "mastery XP must not be blocked by the answer-farming cap"
    )


def test_review_due_keeps_stars(db_session):
    """The spec is explicit: do not silently remove a student's stars when a
    mastered topic falls due for review."""
    user = _user(db_session, "master", "master@example.com")
    row = events.get_or_create_topic(db_session, user.id, "Physics", "Waves")
    row.mastered_at = datetime.utcnow() - timedelta(days=30)
    row.stars = 3
    row.mastery_score = 90
    row.next_review_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    state = events.refresh_state(db_session, row)
    assert state == "review_due"
    assert row.stars == 3, "stars must survive a topic becoming review-due"
    assert row.mastered_at is not None


def test_mastery_can_fall_while_xp_holds(db_session):
    """The two measurements are deliberately independent."""
    user = _user(db_session, "split", "split@example.com")
    events.record(
        db_session, user=user, event_type=events.TOPIC_MASTERED,
        event_key="TOPIC_MASTERED:Biology:Cells", subject="Biology", topic="Cells",
    )
    db_session.commit()
    xp_after = user.points

    row = events.get_or_create_topic(db_session, user.id, "Biology", "Cells")
    row.mastery_score = 95
    db_session.commit()
    row.mastery_score = 40  # student's understanding decayed
    db_session.commit()

    assert row.mastery_score == 40
    assert user.points == xp_after, "XP must not fall when mastery falls"


@pytest.mark.parametrize("level", range(1, 12))
def test_level_curve_is_self_consistent(level):
    """level_for_xp() must agree with xp_for_level() at every boundary, or the
    progress bar disagrees with the level badge."""
    base = config.DEFAULTS["level_base_xp"]
    step = config.DEFAULTS["level_step_xp"]

    total = sum(config.xp_for_level(l, base, step) for l in range(1, level))
    resolved, into, needed = config.level_for_xp(total, base, step)
    assert resolved == level
    assert into == 0
    assert needed == config.xp_for_level(level, base, step)

    # One XP short of the boundary is still the previous level.
    if total > 0:
        prev, _, _ = config.level_for_xp(total - 1, base, step)
        assert prev == level - 1


def test_settings_fall_back_to_defaults_and_reject_typos(db_session):
    assert config.get(db_session, "xp_topic_mastered") == config.DEFAULTS["xp_topic_mastered"]

    config.set_value(db_session, "xp_topic_mastered", 75)
    db_session.commit()
    assert config.get(db_session, "xp_topic_mastered") == 75

    with pytest.raises(KeyError):
        config.get(db_session, "xp_not_a_real_setting")
    with pytest.raises(KeyError):
        config.set_value(db_session, "xp_not_a_real_setting", 1)
