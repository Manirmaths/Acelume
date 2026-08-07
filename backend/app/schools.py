"""
School clubs and inter-school competition.

Two rules do most of the work here, and both are easy to get wrong.

**Normalise per member.** A school's weekly figure is points divided by ACTIVE
members, not total points. Ranking on the raw total produces a table sorted by
enrolment, which tells a student from a 200-pupil school that they cannot win
however hard they work. That is the fastest way to make a competition stop
mattering.

**Never expose individual students publicly.** A student sees their own
contribution; everyone else sees only the school aggregate. These are minors,
and a public per-child ranking attached to a named school is a safeguarding
problem, not a feature. It is also the same reasoning that made weekly leagues
opt-out rather than opt-in.

Fair-play exclusions are applied when totals are computed, so a flagged
account quietly stops contributing without anyone being told anything about
them.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import fair_play
from app.models import (
    MasteryPointLedger, School, SchoolMembership, SchoolWeek, User,
)

# Changing schools is allowed, but not weekly -- otherwise a student hops to
# whoever is winning. Long enough to prevent farming, short enough that a real
# transfer is not punished for a whole term.
SWITCH_COOLDOWN_DAYS = 30

# A member counts as "active" for the week if they scored anything at all.
# Dormant accounts must not dilute a school's average, or a school would be
# punished for having signed up students who never returned.
MIN_POINTS_FOR_ACTIVE = 1

# Below this a per-member average is noise -- one keen student would put a
# two-person school top of the country.
MIN_ACTIVE_FOR_RANKING = 5


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:120] or "school"


def week_start_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def get_or_create_school(
    db: Session, *, name: str, state: str | None, created_by: int | None
) -> School:
    """
    Find a school by name, or create it as community-status.

    Community, never verified: a student typing their school's name is a
    claim. Only an educator claiming it should ever change that.
    """
    slug = slugify(name)
    existing = db.query(School).filter(School.slug == slug).first()
    if existing:
        return existing

    school = School(
        slug=slug,
        name=name.strip()[:200],
        state=(state or "").strip()[:80] or None,
        status="community",
        created_by=created_by,
    )
    db.add(school)
    db.flush()
    return school


def join(db: Session, user: User, school: School) -> SchoolMembership:
    """
    Put a student in a school, respecting the switch cooldown.

    Raises ValueError with a student-facing message when the cooldown blocks
    it -- the caller turns that into a 429.
    """
    membership = (
        db.query(SchoolMembership).filter(SchoolMembership.user_id == user.id).first()
    )
    now = datetime.utcnow()

    if membership is None:
        membership = SchoolMembership(
            user_id=user.id, school_id=school.id, joined_at=now, last_changed_at=now
        )
        db.add(membership)
        return membership

    if membership.school_id == school.id:
        return membership

    elapsed = (now - (membership.last_changed_at or membership.joined_at)).days
    if elapsed < SWITCH_COOLDOWN_DAYS:
        remaining = SWITCH_COOLDOWN_DAYS - elapsed
        raise ValueError(
            f"You can change school again in {remaining} day{'s' if remaining != 1 else ''}."
        )

    membership.school_id = school.id
    membership.last_changed_at = now
    return membership


def _member_points(db: Session, school_id: int, week_start: date) -> dict[int, int]:
    """Points per member for a week, before any exclusions."""
    member_ids = [
        uid for (uid,) in
        db.query(SchoolMembership.user_id).filter(SchoolMembership.school_id == school_id).all()
    ]
    if not member_ids:
        return {}

    rows = (
        db.query(MasteryPointLedger.user_id, func.sum(MasteryPointLedger.amount))
        .filter(
            MasteryPointLedger.user_id.in_(member_ids),
            MasteryPointLedger.week_start == week_start,
        )
        .group_by(MasteryPointLedger.user_id)
        .all()
    )
    return {uid: int(total or 0) for uid, total in rows}


def week_summary(db: Session, school_id: int, week_start: date) -> dict:
    """
    A school's live figures for a week.

    Excluded accounts are dropped from BOTH the total and the member count, so
    removing a flagged student cannot accidentally improve the school's average
    (which it would if only their points were removed).
    """
    points = _member_points(db, school_id, week_start)
    if not points:
        return {"total_points": 0, "active_members": 0, "points_per_member": 0.0}

    excluded = fair_play.excluded_user_ids(db, list(points.keys()))
    counted = {
        uid: amount for uid, amount in points.items()
        if uid not in excluded and amount >= MIN_POINTS_FOR_ACTIVE
    }

    total = sum(counted.values())
    active = len(counted)
    return {
        "total_points": total,
        "active_members": active,
        "points_per_member": round(total / active, 1) if active else 0.0,
    }


def contribution(db: Session, user_id: int, week_start: date) -> int:
    """This student's own points this week. Only ever shown to them."""
    total = (
        db.query(func.coalesce(func.sum(MasteryPointLedger.amount), 0))
        .filter(
            MasteryPointLedger.user_id == user_id,
            MasteryPointLedger.week_start == week_start,
        )
        .scalar()
    )
    return int(total or 0)


def leaderboard(
    db: Session, week_start: date, *, state: str | None = None, limit: int = 50
) -> list[dict]:
    """
    Ranked schools for a week, by points per active member.

    Schools below MIN_ACTIVE_FOR_RANKING are computed but not ranked: a
    two-person school with one keen student would otherwise top the country,
    which is both wrong and demoralising for everyone else.
    """
    query = db.query(School)
    if state:
        query = query.filter(School.state == state)

    rows = []
    for school in query.all():
        summary = week_summary(db, school.id, week_start)
        if summary["active_members"] < MIN_ACTIVE_FOR_RANKING:
            continue
        rows.append({
            "school_id": school.id,
            "slug": school.slug,
            "name": school.name,
            "state": school.state,
            "status": school.status,
            **summary,
        })

    rows.sort(key=lambda r: r["points_per_member"], reverse=True)
    for i, row in enumerate(rows[:limit], start=1):
        row["rank"] = i
    return rows[:limit]


def close_week(db: Session, week_start: date) -> int:
    """
    Freeze every school's week.

    Stored rather than recomputed on read, so a past week's table cannot
    silently change when a student joins, leaves, or is later excluded. A
    leaderboard that rewrites its own history is not a leaderboard.

    Idempotent: re-running for the same week updates in place.
    """
    national = leaderboard(db, week_start, limit=10_000)
    by_state: dict[str, int] = {}

    written = 0
    for entry in national:
        state = entry.get("state")
        if state:
            by_state[state] = by_state.get(state, 0) + 1

        row = (
            db.query(SchoolWeek)
            .filter(
                SchoolWeek.school_id == entry["school_id"],
                SchoolWeek.week_start == week_start,
            )
            .first()
        )
        if row is None:
            row = SchoolWeek(school_id=entry["school_id"], week_start=week_start)
            db.add(row)

        row.total_points = entry["total_points"]
        row.active_members = entry["active_members"]
        row.points_per_member = entry["points_per_member"]
        row.national_rank = entry["rank"]
        row.state_rank = by_state.get(state) if state else None
        row.closed_at = datetime.utcnow()
        written += 1

    db.commit()
    return written
