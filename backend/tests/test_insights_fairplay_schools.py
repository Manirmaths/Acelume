"""
Insights, fair play and school clubs.

Three features with one thing in common: each of them can do real harm if it
is confidently wrong. An insight that is not true wastes a student's revision
week. A fair-play flag that fires on an honest student punishes a child for
nothing. A school table that ranks by size tells everyone at a small school
they cannot win.

So most of what is asserted here is restraint — the conditions under which
each system says nothing at all.
"""

from datetime import date, datetime, timedelta

from app import fair_play, insights, schools as schools_lib
from app.models import (
    MasteryPointLedger, Question, QuizAttempt, School, SchoolMembership,
    SubjectRating, TopicMastery, User, UserResponse,
)


def _user(db_session, username="s1") -> User:
    u = User(username=username, email=f"{username}@example.com", password_hash="x")
    db_session.add(u)
    db_session.commit()
    return u


def _question(db_session, i=0, subject="Mathematics", topic="Algebra", text="Sample?"):
    q = Question(
        question_id=f"ins-{subject}-{topic}-{i}",
        subject=subject, topic=topic, difficulty="medium",
        source="original", status="active",
        question_text=text,
        option_a="A", option_b="B", option_c="C", option_d="D",
        correct_option="B", explanation="Because B.",
    )
    db_session.add(q)
    db_session.commit()
    return q


def _respond(db_session, user, question, *, correct=True, seconds=20, attempt_id=None):
    r = UserResponse(
        user_id=user.id, question_id=question.id, attempt_id=attempt_id,
        selected_option="B" if correct else "A", is_correct=correct,
        answer_seconds=seconds,
    )
    db_session.add(r)
    db_session.commit()
    return r


# ------------------------------------------------------------- insights ----

def test_a_new_student_is_told_nothing(db_session):
    """
    Restraint is the feature. A student with almost no history has almost
    nothing true about them, and filler insights teach people to ignore the
    panel entirely.
    """
    user = _user(db_session)
    q = _question(db_session)
    for _ in range(5):
        _respond(db_session, user, q)

    assert insights.for_user(db_session, user.id) == []


def test_a_weak_question_archetype_is_surfaced(db_session):
    """
    Borrowed from chess.com telling you which openings you are weak in. Often
    more actionable than topic weakness: it is a technique fix, not a
    knowledge one.
    """
    user = _user(db_session)

    # Strong on ordinary questions.
    for i in range(40):
        q = _question(db_session, i=i, text="Find the value of x.")
        _respond(db_session, user, q, correct=True)

    # Weak specifically on negation questions.
    for i in range(20):
        q = _question(db_session, i=100 + i, text="Which of the following is not a prime?")
        _respond(db_session, user, q, correct=(i % 5 == 0))

    found = insights.for_user(db_session, user.id)
    assert any(i.key == "archetype" for i in found)
    text = next(i for i in found if i.key == "archetype").text
    assert "NOT" in text


def test_no_archetype_insight_when_performance_is_even(db_session):
    """No gap, nothing to say."""
    user = _user(db_session)
    for i in range(30):
        q = _question(db_session, i=i, text="Find the value of x.")
        _respond(db_session, user, q, correct=(i % 4 != 0))
    for i in range(20):
        q = _question(db_session, i=100 + i, text="Which of the following is not prime?")
        _respond(db_session, user, q, correct=(i % 4 != 0))

    assert not any(i.key == "archetype" for i in insights.for_user(db_session, user.id))


def test_rushing_is_reported_as_pace_not_as_character(db_session):
    """
    The student is shown a number and left to draw the conclusion. Nowhere
    does the app tell a child it thinks they are guessing.
    """
    user = _user(db_session)
    for i in range(30):
        q = _question(db_session, i=i)
        _respond(db_session, user, q, correct=True, seconds=30)
    for i in range(20):
        q = _question(db_session, i=200 + i)
        _respond(db_session, user, q, correct=False, seconds=2)

    found = insights.for_user(db_session, user.id)
    pace = next((i for i in found if i.key == "pace"), None)
    assert pace is not None
    lowered = pace.text.lower()
    assert "guess" not in lowered and "cheat" not in lowered


def test_a_topic_that_will_not_stick_comes_with_a_lesson_link(db_session):
    """The useful move is to learn it differently, not to grind more questions."""
    user = _user(db_session)
    for i in range(50):
        _respond(db_session, user, _question(db_session, i=i), correct=True)

    db_session.add(TopicMastery(
        user_id=user.id, subject="Mathematics", topic="Simultaneous Equations",
        state="review_due", mastery_score=40, review_stage=4, practice_attempts=12,
    ))
    db_session.commit()

    found = insights.for_user(db_session, user.id)
    sticking = next((i for i in found if i.key == "not_sticking"), None)
    assert sticking is not None
    assert sticking.action_href and "topics" in sticking.action_href


def test_insights_are_capped(db_session):
    user = _user(db_session)
    for i in range(60):
        _respond(db_session, user, _question(db_session, i=i), correct=True)
    assert len(insights.for_user(db_session, user.id, limit=2)) <= 2


# ------------------------------------------------------------ fair play ----

def test_an_ordinary_student_is_never_flagged(db_session):
    """
    The property that matters most. A false positive costs a child their
    trust in the product over something they did not do.
    """
    user = _user(db_session)
    for i in range(60):
        _respond(db_session, user, _question(db_session, i=i), correct=(i % 3 != 0), seconds=25)

    assert fair_play.assess(db_session, user.id).excluded is False


def test_a_fast_but_honest_student_is_not_flagged(db_session):
    """Quick is not the same as impossible. Two seconds is a fast reader."""
    user = _user(db_session)
    for i in range(60):
        _respond(db_session, user, _question(db_session, i=i), correct=True, seconds=3)

    assert fair_play.assess(db_session, user.id).excluded is False


def test_impossibly_fast_correct_answers_are_flagged(db_session):
    user = _user(db_session)
    for i in range(60):
        _respond(db_session, user, _question(db_session, i=i), correct=True, seconds=0)

    assessment = fair_play.assess(db_session, user.id)
    assert assessment.excluded is True
    assert any("under" in r for r in assessment.reasons)


def test_fast_and_wrong_is_not_flagged(db_session):
    """
    Clicking through something you have given up on is not cheating, and it is
    fairly common behaviour near the end of a long session.
    """
    user = _user(db_session)
    for i in range(60):
        _respond(db_session, user, _question(db_session, i=i), correct=False, seconds=0)

    assert fair_play.assess(db_session, user.id).excluded is False


def test_a_small_sample_never_triggers_a_flag(db_session):
    user = _user(db_session)
    for i in range(5):
        _respond(db_session, user, _question(db_session, i=i), correct=True, seconds=0)

    assert fair_play.assess(db_session, user.id).excluded is False


def test_a_settled_rating_that_leaps_is_flagged(db_session):
    user = _user(db_session)
    db_session.add(SubjectRating(
        user_id=user.id, subject="Mathematics",
        rating=1800.0, deviation=50.0, volatility=0.06,
        peak_rating=1800.0, week_start_rating=1200.0,
        week_start_on=date.today(), answers_counted=200,
    ))
    db_session.commit()

    assert fair_play.assess(db_session, user.id).excluded is True


def test_a_fast_improver_with_an_unsettled_rating_is_not_flagged(db_session):
    """
    Glicko-2's uncertainty term means a genuinely fast improver has a HIGH
    deviation by construction. The check must not fire on someone who is
    simply new.
    """
    user = _user(db_session)
    db_session.add(SubjectRating(
        user_id=user.id, subject="Mathematics",
        rating=1800.0, deviation=300.0, volatility=0.06,
        peak_rating=1800.0, week_start_rating=1200.0,
        week_start_on=date.today(), answers_counted=25,
    ))
    db_session.commit()

    assert fair_play.assess(db_session, user.id).excluded is False


def test_a_flag_only_excludes_it_never_punishes(db_session):
    """
    There is deliberately no banned/warned state. The only consequence in the
    whole module is exclusion from competitive surfaces.
    """
    assessment = fair_play.Assessment(signals=[fair_play.Signal("speed", "x")])
    assert assessment.excluded is True
    assert not hasattr(assessment, "banned")
    assert not hasattr(assessment, "warned")


# -------------------------------------------------------------- schools ----

def _school(db_session, name="Federal Government College", state="Sokoto"):
    return schools_lib.get_or_create_school(db_session, name=name, state=state, created_by=None)


def test_joining_a_school_is_a_claim_not_a_verification(db_session):
    school = _school(db_session)
    db_session.commit()
    assert school.status == "community"


def test_a_student_can_join_a_school(db_session):
    user = _user(db_session)
    school = _school(db_session)
    schools_lib.join(db_session, user, school)
    db_session.commit()

    membership = db_session.query(SchoolMembership).filter(
        SchoolMembership.user_id == user.id
    ).first()
    assert membership.school_id == school.id


def test_switching_schools_is_blocked_by_the_cooldown(db_session):
    """Without this a student hops to whoever is winning that week."""
    user = _user(db_session)
    first = _school(db_session, name="School A")
    second = _school(db_session, name="School B")
    schools_lib.join(db_session, user, first)
    db_session.commit()

    try:
        schools_lib.join(db_session, user, second)
        assert False, "the cooldown should have blocked an immediate switch"
    except ValueError as e:
        assert "day" in str(e)


def test_switching_is_allowed_once_the_cooldown_has_passed(db_session):
    user = _user(db_session)
    first = _school(db_session, name="School A")
    second = _school(db_session, name="School B")
    schools_lib.join(db_session, user, first)
    db_session.commit()

    membership = db_session.query(SchoolMembership).filter(
        SchoolMembership.user_id == user.id
    ).first()
    membership.last_changed_at = datetime.utcnow() - timedelta(
        days=schools_lib.SWITCH_COOLDOWN_DAYS + 1
    )
    db_session.commit()

    schools_lib.join(db_session, user, second)
    db_session.commit()
    assert membership.school_id == second.id


def test_rejoining_the_same_school_is_always_allowed(db_session):
    user = _user(db_session)
    school = _school(db_session)
    schools_lib.join(db_session, user, school)
    db_session.commit()
    schools_lib.join(db_session, user, school)  # must not raise


def _award(db_session, user, week, amount, key):
    db_session.add(MasteryPointLedger(
        user_id=user.id, week_start=week, amount=amount, reason="test", ledger_key=key,
    ))
    db_session.commit()


def test_school_totals_are_normalised_per_active_member(db_session):
    """
    The rule that decides whether the whole feature is worth having. Ranking
    on raw totals produces a table sorted by enrolment, which tells a student
    at a 200-pupil school they cannot win however hard they work.
    """
    week = schools_lib.week_start_for(date.today())

    big = _school(db_session, name="Big School")
    small = _school(db_session, name="Small School")
    db_session.commit()

    # Big school: more students, more total points, less effort each.
    for i in range(20):
        u = _user(db_session, username=f"big{i}")
        schools_lib.join(db_session, u, big)
        _award(db_session, u, week, 15, f"big-{i}")

    # Small school: fewer students, lower total, far more effort each.
    for i in range(5):
        u = _user(db_session, username=f"small{i}")
        schools_lib.join(db_session, u, small)
        _award(db_session, u, week, 40, f"small-{i}")
    db_session.commit()

    big_summary = schools_lib.week_summary(db_session, big.id, week)
    small_summary = schools_lib.week_summary(db_session, small.id, week)

    assert big_summary["total_points"] > small_summary["total_points"]
    assert small_summary["points_per_member"] > big_summary["points_per_member"]

    board = schools_lib.leaderboard(db_session, week)
    assert board[0]["name"] == "Small School", "the harder-working school must win"


def test_dormant_members_do_not_dilute_a_schools_average(db_session):
    """Otherwise a school is punished for signing up students who never returned."""
    week = schools_lib.week_start_for(date.today())
    school = _school(db_session)
    db_session.commit()

    for i in range(5):
        u = _user(db_session, username=f"active{i}")
        schools_lib.join(db_session, u, school)
        _award(db_session, u, week, 20, f"a-{i}")
    for i in range(20):
        u = _user(db_session, username=f"dormant{i}")
        schools_lib.join(db_session, u, school)
    db_session.commit()

    summary = schools_lib.week_summary(db_session, school.id, week)
    assert summary["active_members"] == 5
    assert summary["points_per_member"] == 20.0


def test_a_tiny_school_is_not_ranked(db_session):
    """One keen student at a two-person school would otherwise top the country."""
    week = schools_lib.week_start_for(date.today())
    school = _school(db_session, name="Two Pupils")
    db_session.commit()

    for i in range(2):
        u = _user(db_session, username=f"tiny{i}")
        schools_lib.join(db_session, u, school)
        _award(db_session, u, week, 500, f"t-{i}")
    db_session.commit()

    assert schools_lib.leaderboard(db_session, week) == []


def test_a_flagged_student_stops_contributing_quietly(db_session):
    """
    Excluded from BOTH the total and the member count -- removing only their
    points would accidentally improve the school's average.
    """
    week = schools_lib.week_start_for(date.today())
    school = _school(db_session)
    db_session.commit()

    for i in range(5):
        u = _user(db_session, username=f"clean{i}")
        schools_lib.join(db_session, u, school)
        _award(db_session, u, week, 20, f"c-{i}")

    cheat = _user(db_session, username="flagged")
    schools_lib.join(db_session, cheat, school)
    _award(db_session, cheat, week, 500, "cheat")
    for i in range(60):
        _respond(db_session, cheat, _question(db_session, i=900 + i), correct=True, seconds=0)
    db_session.commit()

    summary = schools_lib.week_summary(db_session, school.id, week)
    assert summary["active_members"] == 5
    assert summary["total_points"] == 100


def test_a_closed_week_is_frozen(db_session):
    """A leaderboard that rewrites its own history is not a leaderboard."""
    week = schools_lib.week_start_for(date.today())
    school = _school(db_session)
    db_session.commit()
    for i in range(5):
        u = _user(db_session, username=f"f{i}")
        schools_lib.join(db_session, u, school)
        _award(db_session, u, week, 10, f"f-{i}")
    db_session.commit()

    assert schools_lib.close_week(db_session, week) == 1

    from app.models import SchoolWeek
    row = db_session.query(SchoolWeek).filter(SchoolWeek.school_id == school.id).one()
    assert row.national_rank == 1
    assert row.points_per_member == 10.0

    # Later activity must not change the closed week.
    late = _user(db_session, username="latecomer")
    schools_lib.join(db_session, late, school)
    _award(db_session, late, week, 9999, "late")
    db_session.commit()

    row = db_session.query(SchoolWeek).filter(SchoolWeek.school_id == school.id).one()
    assert row.points_per_member == 10.0


def test_closing_a_week_twice_is_idempotent(db_session):
    week = schools_lib.week_start_for(date.today())
    school = _school(db_session)
    db_session.commit()
    for i in range(5):
        u = _user(db_session, username=f"g{i}")
        schools_lib.join(db_session, u, school)
        _award(db_session, u, week, 10, f"g-{i}")
    db_session.commit()

    schools_lib.close_week(db_session, week)
    schools_lib.close_week(db_session, week)

    from app.models import SchoolWeek
    assert db_session.query(SchoolWeek).filter(SchoolWeek.school_id == school.id).count() == 1


def test_the_leaderboard_never_exposes_individual_students(db_session):
    """
    Safeguarding, not preference. A public per-child ranking attached to a
    named school is a problem, and the API shape is where that is enforced.
    """
    week = schools_lib.week_start_for(date.today())
    school = _school(db_session)
    db_session.commit()
    for i in range(6):
        u = _user(db_session, username=f"private{i}")
        schools_lib.join(db_session, u, school)
        _award(db_session, u, week, 15, f"p-{i}")
    db_session.commit()

    board = schools_lib.leaderboard(db_session, week)
    serialised = str(board)
    assert "private0" not in serialised
    for entry in board:
        assert "members" not in entry or isinstance(entry.get("active_members"), int)
        assert "usernames" not in entry


def test_a_student_sees_only_their_own_contribution(db_session):
    week = schools_lib.week_start_for(date.today())
    me = _user(db_session, username="me")
    other = _user(db_session, username="other")
    _award(db_session, me, week, 42, "me-1")
    _award(db_session, other, week, 999, "other-1")

    assert schools_lib.contribution(db_session, me.id, week) == 42
