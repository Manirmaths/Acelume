"""
Personal bests: make the student's main competitor their previous self.

This matters most for weaker students, who are the ones public leaderboards
discourage. But it only helps if the comparison is honest -- announcing "new
personal best!" because the latest session happened to be shorter or easier
would be worse than saying nothing, because it teaches the student that the
number does not mean anything.

So every result is filed under a COMPARABILITY KEY, and only results sharing
that key are ever compared.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.gamification.idempotency import insert_if_new
from app.models import PersonalBest, User

# Question-count bands. A 10-question quiz and a 12-question quiz are fairly
# compared; a 10-question quiz and a 40-question one are not, because accuracy
# over a short set is far noisier. Bands rather than exact counts keep the
# feature usable without pretending 10 and 40 are the same activity.
COUNT_BANDS: list[tuple[int, int, str]] = [
    (1, 9, "1-9"),
    (10, 19, "10-19"),
    (20, 39, "20-39"),
    (40, 10_000, "40+"),
]


def count_band(n: int) -> str:
    for low, high, label in COUNT_BANDS:
        if low <= n <= high:
            return label
    return "40+"


def activity_key(
    *,
    mode: str,
    subject: str | None,
    topic: str | None,
    total: int,
    difficulty: str | None,
) -> str:
    """Build the comparability key. Anything that changes how hard the activity
    is must appear here, or easier sessions will overwrite harder records."""
    return ":".join([
        mode,
        subject or "*",
        topic or "*",
        count_band(total),
        difficulty or "any",
    ])


class BestResult:
    """What to tell the student after an attempt."""

    def __init__(
        self,
        *,
        is_baseline: bool,
        is_best: bool,
        current_pct: int,
        previous_best_pct: int | None,
        delta_points: int | None,
        attempts: int,
    ):
        self.is_baseline = is_baseline
        self.is_best = is_best
        self.current_pct = current_pct
        self.previous_best_pct = previous_best_pct
        # Deliberately "percentage POINTS", not "percent". Going from 62% to
        # 74% is +12 percentage points, NOT a 12% improvement (that would be
        # ~19%). The spec calls this out and it is an easy thing to get wrong
        # in copy.
        self.delta_points = delta_points
        self.attempts = attempts


def record(
    db: Session,
    *,
    user: User,
    mode: str,
    subject: str | None,
    topic: str | None,
    correct: int,
    total: int,
    attempt_id: int | None = None,
    difficulty: str | None = None,
) -> BestResult | None:
    """
    File an attempt against its comparable personal best.

    Returns None for activities too short to be meaningful -- a 3-question
    quiz says almost nothing, and celebrating a "best" on one would cheapen
    the signal everywhere else.
    """
    if total < 5:
        return None

    pct = round(100 * correct / total)
    key = activity_key(mode=mode, subject=subject, topic=topic, total=total, difficulty=difficulty)

    row = (
        db.query(PersonalBest)
        .filter(PersonalBest.user_id == user.id, PersonalBest.activity_key == key)
        .first()
    )

    if row is None:
        row = PersonalBest(
            user_id=user.id, activity_key=key, mode=mode, subject=subject, topic=topic,
            best_pct=pct, best_correct=correct, best_total=total,
            best_attempt_id=attempt_id, best_at=datetime.utcnow(),
            baseline_pct=pct, attempts=1,
        )
        if not insert_if_new(db, row):
            return None
        # The FIRST attempt is a baseline, never an achievement. Calling it a
        # personal best would make the label meaningless from the outset.
        return BestResult(
            is_baseline=True, is_best=False, current_pct=pct,
            previous_best_pct=None, delta_points=None, attempts=1,
        )

    previous = row.best_pct
    row.attempts += 1
    row.updated_at = datetime.utcnow()

    improved = pct > previous
    if improved:
        row.best_pct = pct
        row.best_correct = correct
        row.best_total = total
        row.best_attempt_id = attempt_id
        row.best_at = datetime.utcnow()

    return BestResult(
        is_baseline=False,
        is_best=improved,
        current_pct=pct,
        previous_best_pct=previous,
        delta_points=pct - previous,
        attempts=row.attempts,
    )


def message_for(result: BestResult, weakest_topic: str | None = None) -> str:
    """
    Phrase the outcome without punishing the student.

    A student who scored lower is told how close they are and what to work on,
    not that they failed -- the whole point of this feature is that it is the
    encouraging alternative to a public leaderboard.
    """
    if result.is_baseline:
        return f"Baseline recorded: {result.current_pct}%. Beat it next time."

    if result.is_best:
        msg = f"New personal best — up {result.delta_points} percentage points."
        if weakest_topic:
            msg += f" {weakest_topic} is still your weakest area."
        return msg

    if result.delta_points == 0:
        return (
            f"You matched your best of {result.previous_best_pct}%. "
            "Correcting a few missed questions should push you past it."
        )

    behind = abs(result.delta_points or 0)
    msg = f"{behind} percentage points off your best of {result.previous_best_pct}%."
    if weakest_topic:
        msg += f" Your main difficulty was {weakest_topic}."
    return msg
