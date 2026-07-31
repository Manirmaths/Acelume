"""
Weekly leagues.

Ranked on **Mastery Points**, which reset every Monday and are deliberately
NOT XP. Ranking on lifetime XP would mean the longest-standing user tops every
league forever, which makes the competition meaningless for everyone else and
actively discouraging for a new student.

Points reward the *quality* of a week's learning -- correcting mistakes,
passing reviews, mastering topics -- rather than raw question volume, so
grinding easy questions is a poor strategy by design.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.gamification import config
from app.gamification.idempotency import insert_if_new
from app.models import LeagueCohort, LeagueMembership, MasteryPointLedger, User

# Lowest to highest.
TIERS = ["foundation", "bronze", "silver", "gold", "diamond", "scholar"]
TIER_LABELS = {
    "foundation": "Foundation",
    "bronze": "Bronze",
    "silver": "Silver",
    "gold": "Gold",
    "diamond": "Diamond",
    "scholar": "Scholar",
}

COHORT_SIZE = 20
PROMOTE_TOP = 5
DEMOTE_BOTTOM = 3

# Below this many active students, NOBODY is demoted.
#
# With a small field the promotion and demotion zones overlap: in a group of
# three, everyone is simultaneously in the top 5 and the bottom 3. The original
# code checked promotion first, so the top of a tiny cohort was safe -- but at
# the highest tier, where promotion is impossible, the winner fell straight
# through into the demotion branch and was relegated for coming first.
#
# This is not a hypothetical. Cohorts fill to COHORT_SIZE, so the very first
# students on the app are all in undersized groups.
MIN_ACTIVE_FOR_DEMOTION = PROMOTE_TOP + DEMOTE_BOTTOM + 1

# event_type -> (settings key, human reason)
POINT_RULES: dict[str, tuple[str, str]] = {
    "QUESTION_ANSWERED": ("mp_correct_answer", "Correct answer"),
    "MISTAKE_CORRECTED": ("mp_mistake_corrected", "Mistake corrected"),
    "REVIEW_COMPLETED": ("mp_review_passed", "Review passed"),
    "TOPIC_PROFICIENT": ("mp_topic_proficient", "Topic proficiency"),
    "TOPIC_MASTERED": ("mp_topic_mastered", "Topic mastered"),
    "MOCK_COMPLETED": ("mp_mock_completed", "Mock exam completed"),
}


def week_start_for(day: date) -> date:
    """Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def current_week_start(user: User) -> date:
    """
    The student's current competition week.

    Uses their local date, so a Sunday-night session in Lagos counts toward the
    week they are actually in rather than the one the server is in.
    """
    return week_start_for(user.local_today())


def _weekly_total(db: Session, user_id: int, week_start: date) -> int:
    return int(
        db.query(func.coalesce(func.sum(MasteryPointLedger.amount), 0))
        .filter(
            MasteryPointLedger.user_id == user_id,
            MasteryPointLedger.week_start == week_start,
        )
        .scalar()
        or 0
    )


def award(db: Session, user: User, *, event_type: str, event_key: str, hard: bool = False) -> int:
    """
    Award Mastery Points for a validated learning event.

    Idempotent on the event key, exactly like XP: the same action can never
    score twice, including on an offline re-sync.

    Returns the points awarded (0 if none, capped, or opted out).
    """
    if user.league_opted_out:
        return 0
    rule = POINT_RULES.get(event_type)
    if rule is None:
        return 0

    key, reason = rule
    amount = config.get(db, key)
    if hard:
        amount += config.get(db, "mp_hard_bonus")
    if amount <= 0:
        return 0

    week = current_week_start(user)

    # Daily cap on the farmable end. Without it a student can out-rank a
    # thoughtful learner purely by volume, which is what the whole points
    # design exists to prevent.
    cap = config.get(db, "mp_daily_cap")
    today_start = user.local_day_start_utc()
    today_total = int(
        db.query(func.coalesce(func.sum(MasteryPointLedger.amount), 0))
        .filter(
            MasteryPointLedger.user_id == user.id,
            MasteryPointLedger.created_at >= today_start,
        )
        .scalar()
        or 0
    )
    if today_total >= cap:
        return 0
    amount = min(amount, cap - today_total)

    row = MasteryPointLedger(
        user_id=user.id, week_start=week, amount=amount, reason=reason,
        ledger_key=f"mp:{event_key}",
    )
    if not insert_if_new(db, row):
        return 0

    membership = ensure_membership(db, user, week)
    if membership is not None:
        membership.points = _weekly_total(db, user.id, week)
    return amount


def ensure_membership(db: Session, user: User, week_start: date) -> LeagueMembership | None:
    """
    Place the student in a cohort on their first qualifying activity of the week.

    Cohorts are filled to COHORT_SIZE before a new one opens, and are scoped to
    the student's TIER -- so a brand-new student is never dropped into a group
    of long-term heavy users, which the spec explicitly warns against.
    """
    if user.league_opted_out:
        return None

    existing = (
        db.query(LeagueMembership)
        .filter(LeagueMembership.user_id == user.id, LeagueMembership.week_start == week_start)
        .first()
    )
    if existing:
        return existing

    tier = user.league_tier or "foundation"
    cohort = (
        db.query(LeagueCohort, func.count(LeagueMembership.id).label("n"))
        .outerjoin(LeagueMembership, LeagueMembership.cohort_id == LeagueCohort.id)
        .filter(
            LeagueCohort.tier == tier,
            LeagueCohort.week_start == week_start,
            LeagueCohort.closed_at.is_(None),
        )
        .group_by(LeagueCohort.id)
        .having(func.count(LeagueMembership.id) < COHORT_SIZE)
        .order_by(func.count(LeagueMembership.id).desc())
        .first()
    )
    cohort_row = cohort[0] if cohort else None
    if cohort_row is None:
        cohort_row = LeagueCohort(tier=tier, week_start=week_start)
        db.add(cohort_row)
        db.flush()

    membership = LeagueMembership(
        user_id=user.id, cohort_id=cohort_row.id, week_start=week_start, points=0,
    )
    if not insert_if_new(db, membership):
        # Concurrent first activity -- the other request's membership is fine.
        return (
            db.query(LeagueMembership)
            .filter(LeagueMembership.user_id == user.id, LeagueMembership.week_start == week_start)
            .first()
        )
    return membership


def standings(db: Session, cohort_id: int) -> list[tuple[LeagueMembership, User]]:
    return (
        db.query(LeagueMembership, User)
        .join(User, User.id == LeagueMembership.user_id)
        .filter(LeagueMembership.cohort_id == cohort_id)
        .order_by(LeagueMembership.points.desc(), LeagueMembership.joined_at.asc())
        .all()
    )


def close_week(db: Session, week_start: date) -> dict[str, int]:
    """
    Settle every open cohort for a finished week.

    Promotion/demotion rules:
      - top 5 move up a tier
      - bottom 3 move down, but ONLY among students who actually scored. An
        inactive account sitting at zero is excluded rather than demoted and
        displayed at the bottom week after week, which the spec calls out as
        humiliating and pointless.
    """
    cohorts = (
        db.query(LeagueCohort)
        .filter(LeagueCohort.week_start == week_start, LeagueCohort.closed_at.is_(None))
        .all()
    )
    stats = {"cohorts": 0, "promoted": 0, "demoted": 0, "stayed": 0}

    for cohort in cohorts:
        rows = standings(db, cohort.id)
        active = [(m, u) for m, u in rows if m.points > 0]
        tier_index = TIERS.index(cohort.tier) if cohort.tier in TIERS else 0

        for rank, (membership, user) in enumerate(rows, start=1):
            membership.final_rank = rank
            if membership.points <= 0:
                # Never demoted for absence -- they simply did not compete.
                membership.outcome = "stayed"
                stats["stayed"] += 1
                continue

            active_rank = next(
                (i for i, (m, _) in enumerate(active, start=1) if m.id == membership.id), rank
            )
            in_demotion_zone = (
                len(active) >= MIN_ACTIVE_FOR_DEMOTION
                and active_rank > len(active) - DEMOTE_BOTTOM
            )
            if active_rank <= PROMOTE_TOP and tier_index < len(TIERS) - 1:
                user.league_tier = TIERS[tier_index + 1]
                membership.outcome = "promoted"
                stats["promoted"] += 1
            elif in_demotion_zone and tier_index > 0:
                user.league_tier = TIERS[tier_index - 1]
                membership.outcome = "demoted"
                stats["demoted"] += 1
            else:
                membership.outcome = "stayed"
                stats["stayed"] += 1

        cohort.closed_at = datetime.utcnow()
        stats["cohorts"] += 1

    return stats
