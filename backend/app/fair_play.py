"""
Fair play.

Invisible infrastructure that the rating economy depends on. It was not needed
while the only thing at stake was a private mastery percentage. It is needed
now, because ratings, matchmaking and school competition give people a reason
to cheat and a thing to win by cheating.

The governing principle, and it is not a soft one:

    **Never accuse a student of cheating on a study app.**

These are minors, the signals here are statistical rather than conclusive, and
a false positive costs a child their trust in the product over something they
did not do. So detection has exactly one consequence: quiet exclusion from
things that RANK them against other people -- leaderboards, school totals,
matchmaking. Every learning feature keeps working exactly as before. A flagged
student who was innocent loses nothing they would notice; a flagged student who
was not stops affecting anyone else.

Nothing here is automatic punishment. Flags are advisory, reviewable, and
reversible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import Question, QuizAttempt, SubjectRating, UserResponse

# Below this, an answer to an unseen multiple-choice question is not reading
# time. Even a student who knows the answer instantly has to read four options.
#
# Set at 1.2s rather than something tighter because the cost of a false
# positive here is much higher than the cost of missing a real one.
MIN_PLAUSIBLE_SECONDS = 1.2

# Share of recent answers under that floor before it stops looking like a few
# lucky guesses and starts looking like a script.
IMPLAUSIBLE_SHARE_PCT = 40

# Sample floor. Everything below returns "no signal" rather than guessing.
MIN_SAMPLE = 30

# A rating gain larger than this in one week, while the rating is already
# settled, is not learning. Glicko-2's own uncertainty term means a legitimate
# fast improver has a HIGH deviation, so this only fires on students whose
# rating had already converged.
IMPLAUSIBLE_WEEKLY_GAIN = 400.0
SETTLED_DEVIATION = 90.0

# Answering the same question set repeatedly before a rated run is how a
# student turns a measurement into a memory test.
REPEAT_ATTEMPT_THRESHOLD = 4


@dataclass(frozen=True)
class Signal:
    key: str
    detail: str


@dataclass(frozen=True)
class Assessment:
    """
    What the system thinks, and what follows from it.

    `excluded` is the ONLY behavioural consequence. There is deliberately no
    "banned" or "warned" state -- see the module docstring.
    """
    signals: list[Signal]

    @property
    def excluded(self) -> bool:
        """Exclude from competitive surfaces only. Learning always continues."""
        return len(self.signals) > 0

    @property
    def reasons(self) -> list[str]:
        return [s.detail for s in self.signals]


def _impossible_speed(db: Session, user_id: int) -> Signal | None:
    rows = (
        db.query(UserResponse)
        .filter(UserResponse.user_id == user_id, UserResponse.answer_seconds.isnot(None))
        .order_by(UserResponse.id.desc())
        .limit(300)
        .all()
    )
    if len(rows) < MIN_SAMPLE:
        return None

    too_fast = [r for r in rows if r.answer_seconds < MIN_PLAUSIBLE_SECONDS]
    share = round(100 * len(too_fast) / len(rows))
    if share < IMPLAUSIBLE_SHARE_PCT:
        return None

    # Fast AND right is the combination that matters. Fast and wrong is a
    # student clicking through something they have given up on, which is not
    # cheating and is fairly common.
    correct_share = round(100 * sum(1 for r in too_fast if r.is_correct) / len(too_fast))
    if correct_share < 60:
        return None

    return Signal(
        key="speed",
        detail=f"{share}% of recent answers under {MIN_PLAUSIBLE_SECONDS}s, {correct_share}% of them correct",
    )


def _repeated_sets(db: Session, user_id: int) -> Signal | None:
    """The same question set, over and over, before a scored run."""
    since = datetime.utcnow() - timedelta(days=7)
    attempts = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.user_id == user_id,
            QuizAttempt.started_at >= since,
            QuizAttempt.finished_at.isnot(None),
        )
        .all()
    )
    if len(attempts) < REPEAT_ATTEMPT_THRESHOLD:
        return None

    seen: dict[tuple, int] = {}
    for a in attempts:
        qids = tuple(sorted(q for q in (a.question_ids or []) if isinstance(q, int)))
        if len(qids) < 5:
            continue
        seen[qids] = seen.get(qids, 0) + 1

    worst = max(seen.values(), default=0)
    if worst < REPEAT_ATTEMPT_THRESHOLD:
        return None

    return Signal(
        key="repeat",
        detail=f"the same question set attempted {worst} times in a week",
    )


def _implausible_gain(db: Session, user_id: int) -> Signal | None:
    """
    A settled rating that jumped further in a week than learning explains.

    Only fires once the deviation is low. A genuinely fast improver has a high
    deviation by construction, which is exactly what Glicko-2's uncertainty
    term is for -- so this cannot fire on a student who is simply new.
    """
    rows = (
        db.query(SubjectRating)
        .filter(
            SubjectRating.user_id == user_id,
            SubjectRating.deviation <= SETTLED_DEVIATION,
        )
        .all()
    )
    for row in rows:
        gain = (row.rating or 0) - (row.week_start_rating or 0)
        if gain >= IMPLAUSIBLE_WEEKLY_GAIN:
            return Signal(
                key="gain",
                detail=f"{row.subject} rating rose {round(gain)} points in one week from a settled base",
            )
    return None


def assess(db: Session, user_id: int) -> Assessment:
    """
    Look at a student. Returns signals, never a verdict.

    Cheap enough to call on a leaderboard render; every check is bounded and
    hits indexed columns.
    """
    signals = [
        s for s in (
            _impossible_speed(db, user_id),
            _repeated_sets(db, user_id),
            _implausible_gain(db, user_id),
        )
        if s is not None
    ]
    return Assessment(signals=signals)


def excluded_user_ids(db: Session, candidate_ids: list[int]) -> set[int]:
    """
    Filter a leaderboard or school total, in a FIXED number of queries.

    The obvious implementation is `{uid for uid in ids if assess(...).excluded}`,
    and it is a trap: assess() costs three queries, so a 100-row leaderboard
    becomes 300 round-trips on every render. That is fine on a laptop against
    SQLite and not fine on a free-tier Postgres with real students on it.

    This does the same work as two aggregate queries over the whole candidate
    set, so cost is flat in the number of users being ranked.

    The repeat-set check from assess() is deliberately NOT included here: it
    needs per-user attempt contents, cannot be expressed as an aggregate, and
    is the weakest of the three signals. It still runs in assess() for
    individual review. Leaderboard filtering uses the two signals that are
    both strong and cheap.
    """
    if not candidate_ids:
        return set()

    excluded: set[int] = set()

    # 1. Impossibly fast correct answers, as one grouped aggregate.
    speed_rows = (
        db.query(
            UserResponse.user_id,
            func.count(UserResponse.id).label("total"),
            func.sum(
                case((UserResponse.answer_seconds < MIN_PLAUSIBLE_SECONDS, 1), else_=0)
            ).label("too_fast"),
            func.sum(
                case(
                    (
                        (UserResponse.answer_seconds < MIN_PLAUSIBLE_SECONDS)
                        & (UserResponse.is_correct.is_(True)),
                        1,
                    ),
                    else_=0,
                )
            ).label("too_fast_correct"),
        )
        .filter(
            UserResponse.user_id.in_(candidate_ids),
            UserResponse.answer_seconds.isnot(None),
        )
        .group_by(UserResponse.user_id)
        .all()
    )

    for user_id, total, too_fast, too_fast_correct in speed_rows:
        total = int(total or 0)
        too_fast = int(too_fast or 0)
        too_fast_correct = int(too_fast_correct or 0)
        if total < MIN_SAMPLE or too_fast == 0:
            continue
        if round(100 * too_fast / total) < IMPLAUSIBLE_SHARE_PCT:
            continue
        # Fast AND right. Fast and wrong is a student clicking through
        # something they gave up on, which is not cheating.
        if round(100 * too_fast_correct / too_fast) >= 60:
            excluded.add(user_id)

    # 2. Settled ratings that leapt, as one filtered query.
    jump_rows = (
        db.query(SubjectRating.user_id)
        .filter(
            SubjectRating.user_id.in_(candidate_ids),
            SubjectRating.deviation <= SETTLED_DEVIATION,
            (SubjectRating.rating - SubjectRating.week_start_rating) >= IMPLAUSIBLE_WEEKLY_GAIN,
        )
        .distinct()
        .all()
    )
    excluded.update(uid for (uid,) in jump_rows)

    return excluded
