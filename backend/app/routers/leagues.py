"""
Weekly league standings.

Privacy notes, which are requirements rather than polish:
  - Only the student's USERNAME is exposed, never their email, school or
    location. Acelume usernames are already self-chosen nicknames.
  - Opting out is a single call and disables nothing else -- a student who
    finds public ranking discouraging keeps every learning feature.
  - There is no messaging of any kind between students.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.gamification import leagues
from app.models import LeagueCohort, LeagueMembership, User
from app.schemas import LeagueOut, LeagueEntryOut, LeagueOptIn

router = APIRouter(prefix="/api/leagues", tags=["leagues"])


@router.put("/opt-out", response_model=LeagueOut)
def set_opt_out(payload: LeagueOptIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.league_opted_out = payload.opted_out
    db.commit()
    return current_league(db=db, user=user)


@router.get("", response_model=LeagueOut)
def current_league(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    week = leagues.current_week_start(user)

    if user.league_opted_out:
        return LeagueOut(
            opted_out=True, tier=user.league_tier or "foundation",
            tier_label=leagues.TIER_LABELS.get(user.league_tier or "foundation", "Foundation"),
            week_start=week.isoformat(), days_remaining=0,
            your_rank=None, your_points=0, entries=[],
            promote_top=leagues.PROMOTE_TOP, demote_bottom=leagues.DEMOTE_BOTTOM,
        )

    membership = (
        db.query(LeagueMembership)
        .filter(LeagueMembership.user_id == user.id, LeagueMembership.week_start == week)
        .first()
    )
    entries: list[LeagueEntryOut] = []
    your_rank = None

    if membership is not None:
        rows = leagues.standings(db, membership.cohort_id)
        for rank, (m, u) in enumerate(rows, start=1):
            is_you = u.id == user.id
            if is_you:
                your_rank = rank
            entries.append(LeagueEntryOut(
                rank=rank,
                # Username only. No email, school or location -- ever.
                username=u.username,
                points=m.points,
                is_you=is_you,
                zone=_zone(rank, len(rows)),
            ))

    days_remaining = max(0, (week + timedelta(days=7) - user.local_today()).days)

    return LeagueOut(
        opted_out=False,
        tier=user.league_tier or "foundation",
        tier_label=leagues.TIER_LABELS.get(user.league_tier or "foundation", "Foundation"),
        week_start=week.isoformat(),
        days_remaining=days_remaining,
        your_rank=your_rank,
        your_points=membership.points if membership else 0,
        entries=entries,
        promote_top=leagues.PROMOTE_TOP,
        demote_bottom=leagues.DEMOTE_BOTTOM,
    )


def _zone(rank: int, total: int) -> str:
    if rank <= leagues.PROMOTE_TOP:
        return "promotion"
    if total > leagues.DEMOTE_BOTTOM and rank > total - leagues.DEMOTE_BOTTOM:
        return "demotion"
    return "safe"
