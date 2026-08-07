"""
Retention and funnel analytics.

These numbers are going to decide whether a teacher trial counts as success,
so the tests are built around cohorts whose right answer is known by
construction. A retention metric that is quietly wrong is worse than none: it
does not fail loudly, it just produces a confident number that sends you in
the wrong direction for a month.

The properties that matter most are the honest-reporting ones — a cohort too
young to have a day-14 figure must say NULL rather than 0, and "returned" must
mean answered, not opened.
"""

from datetime import datetime, timedelta

from app import analytics
from app.models import Question, QuizAttempt, User, UserResponse


def _question(db_session, i=0):
    q = Question(
        question_id=f"an-{i}", subject="Mathematics", topic="Algebra",
        difficulty="medium", source="original", status="active",
        question_text="?", option_a="A", option_b="B", option_c="C", option_d="D",
        correct_option="B",
    )
    db_session.add(q)
    db_session.commit()
    return q


def _student(db_session, username, days_ago: float):
    u = User(
        username=username, email=f"{username}@example.com", password_hash="x",
        created_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db_session.add(u)
    db_session.commit()
    return u


def _answered(db_session, user, question, days_ago: float, n=1):
    for _ in range(n):
        db_session.add(UserResponse(
            user_id=user.id, question_id=question.id,
            selected_option="B", is_correct=True,
            timestamp=datetime.utcnow() - timedelta(days=days_ago),
        ))
    db_session.commit()


# ------------------------------------------------------------- cohorts ----

def test_no_users_produces_no_cohorts(db_session):
    assert analytics.cohorts(db_session) == []


def test_a_cohort_counts_its_signups(db_session):
    q = _question(db_session)
    for i in range(5):
        _student(db_session, f"s{i}", days_ago=20)

    rows = analytics.cohorts(db_session, weeks=8)
    assert sum(c.signups for c in rows) == 5


def test_activation_counts_only_students_who_answered_something(db_session):
    """Signing up is not using the app."""
    q = _question(db_session)
    for i in range(5):
        u = _student(db_session, f"act{i}", days_ago=20)
        if i < 2:
            _answered(db_session, u, q, days_ago=20)

    rows = analytics.cohorts(db_session, weeks=8)
    assert sum(c.signups for c in rows) == 5
    assert sum(c.activated for c in rows) == 2


def test_returning_means_answering_not_merely_signing_up(db_session):
    """
    A student who registers and never answers has not retained, whatever any
    session or login count might suggest.
    """
    _question(db_session)
    for i in range(4):
        _student(db_session, f"ghost{i}", days_ago=30)

    rows = analytics.cohorts(db_session, weeks=8)
    assert all(c.retention[14] == 0 for c in rows)


def test_a_student_answering_after_two_weeks_counts_as_retained(db_session):
    q = _question(db_session)
    u = _student(db_session, "loyal", days_ago=30)
    _answered(db_session, u, q, days_ago=30)   # day 0
    _answered(db_session, u, q, days_ago=10)   # day 20

    rows = analytics.cohorts(db_session, weeks=8)
    assert rows[0].retention[14] == 100


def test_retention_does_not_require_activity_on_the_exact_checkpoint_day(db_session):
    """
    A student who practises on day 6 and day 20 is retained. Requiring activity
    on day 14 precisely would report them as churned, which is nonsense.
    """
    q = _question(db_session)
    u = _student(db_session, "irregular", days_ago=25)
    _answered(db_session, u, q, days_ago=19)   # day 6
    _answered(db_session, u, q, days_ago=5)    # day 20

    rows = analytics.cohorts(db_session, weeks=8)
    assert rows[0].retention[7] == 100
    assert rows[0].retention[14] == 100


def test_a_student_who_stopped_after_day_one_is_not_retained(db_session):
    """The teacher-trial failure mode: everyone tries it once, nobody returns."""
    q = _question(db_session)
    for i in range(10):
        u = _student(db_session, f"trial{i}", days_ago=30)
        _answered(db_session, u, q, days_ago=30)

    rows = analytics.cohorts(db_session, weeks=8)
    c = rows[0]
    assert c.activated == 10, "they did all try it"
    assert c.retention[14] == 0, "and none of them came back"


def test_a_young_cohort_reports_null_not_zero(db_session):
    """
    The most important honesty property here. A cohort that signed up
    yesterday cannot have a day-14 number, and reporting 0% would make every
    recent week look like a disaster and hide any real signal.
    """
    q = _question(db_session)
    u = _student(db_session, "newbie", days_ago=1)
    _answered(db_session, u, q, days_ago=1)   # at signup
    _answered(db_session, u, q, days_ago=0)   # came back the next day

    rows = analytics.cohorts(db_session, weeks=8)
    c = rows[0]
    assert c.retention[1] == 100, "day 1 is knowable"
    assert c.retention[7] is None, "day 7 is not"
    assert c.retention[14] is None


def test_cohort_maturity_uses_the_youngest_member(db_session):
    """
    A checkpoint must not be reported until EVERY member of the cohort could
    have reached it, or the figure is computed over a mixed population.
    """
    q = _question(db_session)
    _student(db_session, "early", days_ago=6.9)
    _student(db_session, "late", days_ago=3)

    rows = analytics.cohorts(db_session, weeks=8)
    assert rows[0].retention[7] is None


def test_cohorts_are_returned_newest_first(db_session):
    _question(db_session)
    _student(db_session, "old", days_ago=30)
    _student(db_session, "recent", days_ago=2)

    rows = analytics.cohorts(db_session, weeks=8)
    assert rows[0].week_start > rows[-1].week_start


def test_partial_retention_is_computed_correctly(db_session):
    q = _question(db_session)
    for i in range(10):
        u = _student(db_session, f"mix{i}", days_ago=30)
        _answered(db_session, u, q, days_ago=30)
        if i < 3:
            _answered(db_session, u, q, days_ago=8)   # day 22

    rows = analytics.cohorts(db_session, weeks=8)
    assert rows[0].retention[14] == 30


# -------------------------------------------------------------- funnel ----

def test_an_empty_funnel_does_not_divide_by_zero(db_session):
    f = analytics.funnel(db_session)
    assert f.signups == 0
    assert f.median_seconds_to_first_question is None
    assert f.within_target_pct is None


def test_the_funnel_narrows_at_each_step(db_session):
    q = _question(db_session)
    for i in range(10):
        u = _student(db_session, f"fun{i}", days_ago=5)
        if i < 6:
            _answered(db_session, u, q, days_ago=5, n=1)
        if i < 3:
            _answered(db_session, u, q, days_ago=5, n=10)

    f = analytics.funnel(db_session, days=30)
    assert f.signups == 10
    assert f.answered_one == 6
    assert f.answered_ten == 3
    assert f.answered_one >= f.answered_ten


def test_completed_attempts_are_counted(db_session):
    q = _question(db_session)
    u = _student(db_session, "finisher", days_ago=3)
    _answered(db_session, u, q, days_ago=3)
    db_session.add(QuizAttempt(
        user_id=u.id, mode="quiz", subject="Mathematics",
        question_ids=[q.id], current_index=1, score=1,
        finished_at=datetime.utcnow(),
    ))
    db_session.commit()

    assert analytics.funnel(db_session).completed_attempt == 1


def test_time_to_first_question_is_measured_against_the_target(db_session):
    """
    The whole onboarding experience as one number. Below the target means a
    student got to practising; above it means they signed up and wandered off.
    """
    q = _question(db_session)

    fast = _student(db_session, "fast", days_ago=2)
    fast.created_at = datetime.utcnow() - timedelta(days=2)
    db_session.commit()
    db_session.add(UserResponse(
        user_id=fast.id, question_id=q.id, selected_option="B", is_correct=True,
        timestamp=fast.created_at + timedelta(seconds=30),
    ))

    slow = _student(db_session, "slow", days_ago=2)
    slow.created_at = datetime.utcnow() - timedelta(days=2)
    db_session.commit()
    db_session.add(UserResponse(
        user_id=slow.id, question_id=q.id, selected_option="B", is_correct=True,
        timestamp=slow.created_at + timedelta(seconds=600),
    ))
    db_session.commit()

    f = analytics.funnel(db_session, days=30)
    assert f.median_seconds_to_first_question is not None
    assert f.within_target_pct == 50


def test_clock_skew_cannot_produce_a_negative_time_to_first_question(db_session):
    """A response timestamped before signup is bad data, not a fast student."""
    q = _question(db_session)
    u = _student(db_session, "skewed", days_ago=2)
    db_session.add(UserResponse(
        user_id=u.id, question_id=q.id, selected_option="B", is_correct=True,
        timestamp=u.created_at - timedelta(seconds=60),
    ))
    db_session.commit()

    f = analytics.funnel(db_session, days=30)
    assert f.median_seconds_to_first_question is None or f.median_seconds_to_first_question >= 0


# ------------------------------------------------------------ headline ----

def test_the_headline_is_null_before_any_cohort_is_old_enough(db_session):
    _question(db_session)
    _student(db_session, "brandnew", days_ago=1)

    assert analytics.headline(db_session)["week_two_return_pct"] is None


def test_the_headline_weights_by_cohort_size(db_session):
    """
    A 100-student cohort at 10% and a 10-student cohort at 100% must not
    average to 55%. Unweighted averaging is the classic way a retention number
    ends up flattering.
    """
    q = _question(db_session)

    for i in range(20):
        u = _student(db_session, f"big{i}", days_ago=40)
        _answered(db_session, u, q, days_ago=40)
        if i < 2:
            _answered(db_session, u, q, days_ago=20)

    for i in range(2):
        u = _student(db_session, f"small{i}", days_ago=20)
        _answered(db_session, u, q, days_ago=20)
        _answered(db_session, u, q, days_ago=2)

    head = analytics.headline(db_session)
    # 2/20 + 2/2 = 4 of 22 students -> 18%, not the 55% an unweighted mean gives.
    assert head["students_measured"] == 22
    assert head["week_two_return_pct"] < 30


def test_the_headline_reports_how_much_evidence_is_behind_it(db_session):
    q = _question(db_session)
    for i in range(5):
        u = _student(db_session, f"ev{i}", days_ago=30)
        _answered(db_session, u, q, days_ago=30)

    head = analytics.headline(db_session)
    assert head["cohorts_measured"] >= 1
    assert head["students_measured"] == 5


# --------------------------------------------------------------- daily ----

def test_daily_signups_fill_gaps_with_zero(db_session):
    """A day with no signups is a zero, not a missing row — spikes must be visible."""
    _question(db_session)
    _student(db_session, "d1", days_ago=5)

    rows = analytics.daily_signups(db_session, days=10)
    assert len(rows) >= 10
    assert sum(r["signups"] for r in rows) == 1
    assert any(r["signups"] == 0 for r in rows)


# ------------------------------------------------------------ endpoint ----

def test_the_endpoint_requires_an_admin(client, register_user):
    register_user()
    assert client.get("/api/admin/analytics").status_code == 403


def test_the_endpoint_returns_a_full_payload(admin_client, db_session):
    q = _question(db_session)
    u = _student(db_session, "endpoint", days_ago=30)
    _answered(db_session, u, q, days_ago=30)
    _answered(db_session, u, q, days_ago=5)

    res = admin_client.get("/api/admin/analytics")
    assert res.status_code == 200, res.text
    body = res.json()

    assert "week_two_return_pct" in body
    assert body["time_to_value_target_seconds"] == analytics.TIME_TO_VALUE_TARGET_SECONDS
    assert len(body["cohorts"]) >= 1
    assert body["funnel"]["signups"] >= 1
    assert len(body["daily"]) >= 1


def test_the_endpoint_clamps_absurd_ranges(admin_client):
    assert admin_client.get("/api/admin/analytics?weeks=9999&days=9999").status_code == 200
    assert admin_client.get("/api/admin/analytics?weeks=0&days=0").status_code == 200
