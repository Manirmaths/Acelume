"""
Levels and the two streak types.

The timezone behaviour is the important part: Render runs in UTC, so before
the `timezone` column existed a Nigerian student practising at 11pm lost the
day at midnight UTC — an hour before their own midnight.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.gamification import config
from app.models import User


def _user(db, **kw):
    u = User(username=kw.pop("username", "s1"), email=kw.pop("email", "s1@example.com"),
             password_hash="x", points=0, **kw)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_lagos_timezone_is_actually_available():
    """
    Guards a trap rather than a feature.

    Python's zoneinfo reads the SYSTEM tz database, which Windows does not
    ship. Without the `tzdata` package this raises, User.local_today() falls
    back to UTC, and the timezone-aware streak logic silently does nothing on
    every Windows dev machine while working fine on Render's Linux hosts.
    """
    from zoneinfo import ZoneInfo

    assert ZoneInfo("Africa/Lagos") is not None


def test_streak_day_uses_the_students_timezone(db_session):
    """23:30 UTC is already tomorrow in Lagos (UTC+1), and the student's own
    calendar day is what counts."""
    from datetime import datetime as real_datetime, timezone as real_tz

    user = _user(db_session, timezone="Africa/Lagos")
    utc_2330 = real_datetime(2026, 7, 30, 23, 30, tzinfo=real_tz.utc)

    with patch("app.models.datetime") as m:
        m.now.side_effect = lambda tz=None: utc_2330.astimezone(tz) if tz else utc_2330
        m.utcnow.return_value = utc_2330.replace(tzinfo=None)
        assert user.local_today() == date(2026, 7, 31), (
            "23:30 UTC is 00:30 the next day in Lagos"
        )


def test_unknown_timezone_falls_back_instead_of_crashing(db_session):
    """Bad profile data must never make answering a question fail."""
    user = _user(db_session, timezone="Not/AZone")
    assert isinstance(user.local_today(), date)
    assert user.local_day_start_utc() is not None


def test_local_day_start_is_the_students_midnight_in_utc(db_session):
    """Lagos is UTC+1, so their day starts at 23:00 UTC the previous day.

    Using UTC midnight instead would reset the daily XP ring an hour early
    for every student.
    """
    from datetime import datetime as real_datetime

    user = _user(db_session, timezone="Africa/Lagos")
    start = user.local_day_start_utc()
    local = user.local_today()

    assert start.tzinfo is None, "stored timestamps are naive UTC; comparisons must match"
    assert start.hour == 23
    assert start.date() == local - timedelta(days=1)


def test_utc_student_day_starts_at_utc_midnight(db_session):
    user = _user(db_session, username="s2", email="s2@example.com", timezone="UTC")
    start = user.local_day_start_utc()
    assert start.hour == 0
    assert start.date() == user.local_today()


def test_learning_streak_extends_once_per_day(db_session):
    user = _user(db_session)
    user.record_practice()
    first = user.current_streak
    user.record_practice()
    assert user.current_streak == first, "same day must not extend twice"


def test_mastery_streak_requires_meeting_the_standard(db_session):
    user = _user(db_session)

    user.record_mastery_day(False)
    assert user.mastery_streak == 0, "a poor day must not extend the mastery streak"

    user.record_mastery_day(True)
    assert user.mastery_streak == 1
    assert user.longest_mastery_streak == 1

    user.record_mastery_day(True)
    assert user.mastery_streak == 1, "same day must not extend twice"


def test_mastery_streak_resets_after_a_gap_but_keeps_the_record(db_session):
    user = _user(db_session)
    user.mastery_streak = 9
    user.longest_mastery_streak = 9
    user.last_mastery_date = date.today() - timedelta(days=3)

    user.record_mastery_day(True)
    assert user.mastery_streak == 1
    assert user.longest_mastery_streak == 9, "the record must survive a broken streak"


def test_streak_freeze_does_not_apply_to_mastery(db_session):
    """A freeze protects attendance. There is no honest way to protect a day
    on which no competence was shown."""
    user = _user(db_session)
    user.streak_freezes = 3
    user.mastery_streak = 5
    user.last_mastery_date = date.today() - timedelta(days=2)

    user.record_mastery_day(True)
    assert user.mastery_streak == 1
    assert user.streak_freezes == 3, "no freeze should have been spent"


@pytest.mark.parametrize("xp,expected_level", [(0, 1), (99, 1), (100, 2), (224, 2), (225, 3)])
def test_level_boundaries(xp, expected_level):
    base = config.DEFAULTS["level_base_xp"]
    step = config.DEFAULTS["level_step_xp"]
    level, _, _ = config.level_for_xp(xp, base, step)
    assert level == expected_level


def test_level_titles_progress():
    assert config.title_for_level(1) == "Explorer"
    assert config.title_for_level(4) == "Explorer"
    assert config.title_for_level(5) == "Learner"
    assert config.title_for_level(30) == "Master Learner"
    assert config.title_for_level(99) == "Master Learner"


def test_dashboard_reports_level_and_both_streaks(client, register_user):
    register_user()
    data = client.get("/api/dashboard").json()

    assert data["level"]["level"] == 1
    assert data["level"]["title"] == "Explorer"
    assert data["level"]["xp_for_next"] == config.DEFAULTS["level_base_xp"]
    assert data["mastery_streak"] == 0
    assert "current_streak" in data, "the learning streak must still be reported"
