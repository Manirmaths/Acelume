"""
Retention and funnel analytics.

Built for one specific decision: after a teacher introduces Acelume to a class
and then stops mentioning it, do those students come back on their own?

That question has a shape, and it dictates everything here:

  - **Cohorts, not totals.** "We have 400 users" is unfalsifiable. "Of the 30
    who signed up in the week of 11 August, 9 came back in week two" is a
    fact you can act on. Totals always go up and therefore always feel like
    progress, which is exactly why they are the wrong number to run a test on.

  - **Week two matters, week one does not.** Week-one activity in a
    teacher-led trial measures compliance with a teacher, not desire for the
    product. The signal lives after the social pressure stops.

  - **Returning means ANSWERING, not opening.** A student who opens the app
    and closes it has not returned in any sense worth counting. Every metric
    here is anchored on UserResponse, which only exists when a question was
    actually answered.

  - **Immature cohorts are excluded, not estimated.** A cohort that signed up
    three days ago cannot have a day-7 number. Reporting one as 0% would make
    every recent week look like a disaster; reporting it as null makes the
    table honest and slightly emptier.

All of it is aggregate queries over data already collected. Nothing here needs
new tracking, which also means it works retroactively on every user you
already have.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import User, UserResponse

# Retention checkpoints, in days after signup.
#
# D1 tells you the product worked at all. D7 tells you it survived a week of
# school. D14 is the one that matters -- by then any teacher-led enthusiasm has
# worn off, and what is left is students who came back because they wanted to.
CHECKPOINTS = (1, 7, 14)

# Signup-to-first-question target, in seconds. From PRODUCT-ARCHITECTURE.md §10:
# if a student cannot get from registration to answering something inside a
# minute and a half, the onboarding is the problem, not the content.
TIME_TO_VALUE_TARGET_SECONDS = 90


@dataclass
class Cohort:
    """One signup week, and what became of it."""
    week_start: str
    signups: int
    # Answered at least one question ever. The rest never started.
    activated: int
    # day -> percentage returning, or None when the cohort is too young to say.
    retention: dict[int, int | None] = field(default_factory=dict)
    # Null until the cohort is old enough for the checkpoint to be meaningful.
    mature_days: int = 0


@dataclass
class Funnel:
    signups: int
    # Reached the app at all.
    answered_one: int
    # Ten answers is roughly "did a real session" rather than poked at it.
    answered_ten: int
    completed_attempt: int
    median_seconds_to_first_question: int | None
    within_target_pct: int | None


def _day(dt: datetime | None) -> date | None:
    return dt.date() if dt else None


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _first_response_at(db: Session, user_ids: list[int]) -> dict[int, datetime]:
    if not user_ids:
        return {}
    rows = (
        db.query(UserResponse.user_id, func.min(UserResponse.timestamp))
        .filter(UserResponse.user_id.in_(user_ids))
        .group_by(UserResponse.user_id)
        .all()
    )
    return {uid: ts for uid, ts in rows if ts}


def _active_days(db: Session, user_ids: list[int]) -> dict[int, set[date]]:
    """Days on which each user actually ANSWERED something."""
    if not user_ids:
        return {}
    rows = (
        db.query(UserResponse.user_id, UserResponse.timestamp)
        .filter(UserResponse.user_id.in_(user_ids))
        .all()
    )
    out: dict[int, set[date]] = {}
    for uid, ts in rows:
        if ts:
            out.setdefault(uid, set()).add(ts.date())
    return out


def cohorts(db: Session, weeks: int = 8) -> list[Cohort]:
    """
    Weekly signup cohorts with retention at each checkpoint.

    "Retained at day N" means: answered at least one question on or after day
    N since signing up. Deliberately not "on exactly day N" -- a student who
    practises on days 6 and 9 is retained, and a strict same-day definition
    would report them as churned.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(weeks=weeks)

    users = (
        db.query(User.id, User.created_at)
        .filter(User.created_at.isnot(None), User.created_at >= cutoff)
        .all()
    )
    if not users:
        return []

    by_week: dict[date, list[tuple[int, datetime]]] = {}
    for uid, created in users:
        by_week.setdefault(_week_start(created.date()), []).append((uid, created))

    all_ids = [uid for uid, _ in users]
    active = _active_days(db, all_ids)

    out: list[Cohort] = []
    for week in sorted(by_week, reverse=True):
        members = by_week[week]
        ids = [uid for uid, _ in members]

        activated = sum(1 for uid in ids if active.get(uid))

        # How much time the YOUNGEST member of this cohort has had. Using the
        # youngest rather than the oldest is what stops a checkpoint being
        # reported before everyone in the cohort could possibly have reached it.
        youngest = max(created for _, created in members)
        mature_days = (now - youngest).days

        retention: dict[int, int | None] = {}
        for day in CHECKPOINTS:
            if mature_days < day:
                # Too young to have an answer. Say so rather than reporting 0%,
                # which would make every recent week look like a failure.
                retention[day] = None
                continue
            returned = 0
            for uid, created in members:
                threshold = created.date() + timedelta(days=day)
                if any(d >= threshold for d in active.get(uid, ())):
                    returned += 1
            retention[day] = round(100 * returned / len(members)) if members else 0

        out.append(Cohort(
            week_start=week.isoformat(),
            signups=len(members),
            activated=activated,
            retention=retention,
            mature_days=mature_days,
        ))

    return out


def funnel(db: Session, days: int = 30) -> Funnel:
    """
    Where new students stop.

    Time-to-first-question is the number to watch. It is the whole of the
    onboarding experience expressed as one figure, and it is the difference
    between a student who starts practising and one who signs up and leaves.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    users = (
        db.query(User.id, User.created_at)
        .filter(User.created_at.isnot(None), User.created_at >= cutoff)
        .all()
    )
    if not users:
        return Funnel(0, 0, 0, 0, None, None)

    ids = [uid for uid, _ in users]
    created_by_id = {uid: created for uid, created in users}

    counts = dict(
        db.query(UserResponse.user_id, func.count(UserResponse.id))
        .filter(UserResponse.user_id.in_(ids))
        .group_by(UserResponse.user_id)
        .all()
    )
    firsts = _first_response_at(db, ids)

    from app.models import QuizAttempt
    finished = {
        uid for (uid,) in
        db.query(QuizAttempt.user_id)
        .filter(QuizAttempt.user_id.in_(ids), QuizAttempt.finished_at.isnot(None))
        .distinct()
        .all()
    }

    gaps = sorted(
        (firsts[uid] - created_by_id[uid]).total_seconds()
        for uid in firsts
        # Guard against clock skew producing a negative gap.
        if (firsts[uid] - created_by_id[uid]).total_seconds() >= 0
    )
    median = int(gaps[len(gaps) // 2]) if gaps else None
    within = (
        round(100 * sum(1 for g in gaps if g <= TIME_TO_VALUE_TARGET_SECONDS) / len(gaps))
        if gaps else None
    )

    return Funnel(
        signups=len(users),
        answered_one=sum(1 for uid in ids if counts.get(uid, 0) >= 1),
        answered_ten=sum(1 for uid in ids if counts.get(uid, 0) >= 10),
        completed_attempt=len(finished),
        median_seconds_to_first_question=median,
        within_target_pct=within,
    )


def daily_signups(db: Session, days: int = 30) -> list[dict]:
    """Signups and newly-activated students per day, for spotting a trial start."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    users = (
        db.query(User.id, User.created_at)
        .filter(User.created_at.isnot(None), User.created_at >= cutoff)
        .all()
    )
    firsts = _first_response_at(db, [uid for uid, _ in users])

    signups: dict[date, int] = {}
    activated: dict[date, int] = {}
    for uid, created in users:
        d = created.date()
        signups[d] = signups.get(d, 0) + 1
        if uid in firsts:
            activated[d] = activated.get(d, 0) + 1

    start = cutoff.date()
    today = datetime.utcnow().date()
    out = []
    d = start
    while d <= today:
        out.append({
            "date": d.isoformat(),
            "signups": signups.get(d, 0),
            "activated": activated.get(d, 0),
        })
        d += timedelta(days=1)
    return out


def headline(db: Session) -> dict:
    """
    The one-line answer to "is this working?".

    Week-two return rate across all cohorts old enough to have one. This is
    the number the teacher trial exists to produce, so it gets its own field
    rather than being something you squint at in a table.
    """
    rows = [c for c in cohorts(db, weeks=12) if c.retention.get(14) is not None]
    if not rows:
        return {"week_two_return_pct": None, "cohorts_measured": 0, "students_measured": 0}

    students = sum(c.signups for c in rows)
    weighted = sum(c.retention[14] * c.signups for c in rows)
    return {
        "week_two_return_pct": round(weighted / students) if students else None,
        "cohorts_measured": len(rows),
        "students_measured": students,
    }
