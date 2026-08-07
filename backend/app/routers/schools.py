"""
School clubs API.

Safety note that governs every response shape in this file: no endpoint here
ever returns another student's name, username or score. A student sees their
own contribution and their school's aggregate; everyone else is a number in a
total. These are minors, and a public per-child ranking attached to a named
school is a safeguarding problem rather than a feature.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import schools as schools_lib
from app.auth import get_current_user
from app.database import get_db
from app.models import School, SchoolMembership, SchoolWeek, User
from app.schemas import (
    SchoolJoinIn, SchoolLeaderboardEntry, SchoolOut, MySchoolOut,
)

router = APIRouter(prefix="/api/schools", tags=["schools"])


def _current_week(user: User):
    return schools_lib.week_start_for(user.local_today())


@router.get("/search", response_model=list[SchoolOut])
def search_schools(q: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Type-ahead over school names. Empty query returns the busiest schools."""
    query = db.query(School)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.filter(School.name.ilike(like))
    rows = query.limit(20).all()
    return [
        SchoolOut(id=s.id, slug=s.slug, name=s.name, state=s.state, status=s.status)
        for s in rows
    ]


@router.post("/join", response_model=MySchoolOut)
def join_school(payload: SchoolJoinIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Join a school by id, or create one by name.

    A newly created school is always community status -- a student typing a
    name is a claim, not verification.
    """
    if payload.school_id is not None:
        school = db.get(School, payload.school_id)
        if school is None:
            raise HTTPException(status_code=404, detail="School not found.")
    elif payload.name and payload.name.strip():
        school = schools_lib.get_or_create_school(
            db, name=payload.name, state=payload.state, created_by=user.id
        )
    else:
        raise HTTPException(status_code=400, detail="Choose a school or type its name.")

    try:
        schools_lib.join(db, user, school)
    except ValueError as e:
        # Cooldown. 429 rather than 400: it is a rate limit, not bad input.
        raise HTTPException(status_code=429, detail=str(e))

    db.commit()
    return _my_school(db, user)


@router.post("/leave", status_code=204)
def leave_school(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Leaving is always allowed and never rate-limited.

    The cooldown exists to stop farming by hopping between schools, not to trap
    a student in one. Re-JOINING is what the cooldown governs.
    """
    membership = db.query(SchoolMembership).filter(SchoolMembership.user_id == user.id).first()
    if membership:
        db.delete(membership)
        db.commit()


@router.get("/me", response_model=MySchoolOut | None)
def my_school(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _my_school(db, user)


@router.get("/leaderboard", response_model=list[SchoolLeaderboardEntry])
def school_leaderboard(
    state: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    week = _current_week(user)
    rows = schools_lib.leaderboard(db, week, state=state)
    return [SchoolLeaderboardEntry(**row) for row in rows]


def _my_school(db: Session, user: User) -> MySchoolOut | None:
    membership = db.query(SchoolMembership).filter(SchoolMembership.user_id == user.id).first()
    if membership is None:
        return None

    school = db.get(School, membership.school_id)
    if school is None:
        return None

    week = _current_week(user)
    summary = schools_lib.week_summary(db, school.id, week)

    # Rank is looked up from the live table rather than stored, since the week
    # is still running.
    national = schools_lib.leaderboard(db, week, limit=10_000)
    state_rows = [r for r in national if r["state"] == school.state] if school.state else []

    def rank_in(rows: list[dict]) -> int | None:
        for i, row in enumerate(rows, start=1):
            if row["school_id"] == school.id:
                return i
        return None

    last_week = (
        db.query(SchoolWeek)
        .filter(SchoolWeek.school_id == school.id, SchoolWeek.week_start < week)
        .order_by(SchoolWeek.week_start.desc())
        .first()
    )

    return MySchoolOut(
        school=SchoolOut(
            id=school.id, slug=school.slug, name=school.name,
            state=school.state, status=school.status,
        ),
        total_points=summary["total_points"],
        active_members=summary["active_members"],
        points_per_member=summary["points_per_member"],
        # The student's own number, and the only individual figure anywhere in
        # this API. Never another student's.
        your_contribution=schools_lib.contribution(db, user.id, week),
        state_rank=rank_in(state_rows),
        national_rank=rank_in(national),
        last_week_national_rank=last_week.national_rank if last_week else None,
        can_change_after=(
            membership.last_changed_at + timedelta(days=schools_lib.SWITCH_COOLDOWN_DAYS)
        ).date().isoformat() if membership.last_changed_at else None,
    )
