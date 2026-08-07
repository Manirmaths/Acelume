"""
Rush -- three strikes and escalating difficulty.

Blitz already exists and is a timed sprint: 180 seconds, up to 60 questions,
flat random difficulty. Rush is not a variant of that, it is the opposite
design, and the differences are the whole point:

                Blitz            Rush
    ends on     the clock        three wrong answers
    difficulty  flat random      ramps upward from below your level
    behaviour   go faster        be careful, then greedy, then careful
    ends with   a beep           a moment of tension

Both are kept, exactly as chess.com runs Puzzle Rush and Puzzle Storm side by
side. Rush is the one worth leading with, because a strike count produces
better practice than a timer: a timer rewards speed, which for an exam
candidate mostly means guessing.

The difficulty ramp is what makes it work for everyone. It starts about 200
rating points BELOW the student -- easy enough to build a run -- and climbs
past their level. A strong student and a weak one both fail out a few
questions past where they are comfortable, which is exactly where practice
should sit. Neither is bored and neither is buried.
"""

import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Question, QuizAttempt, User
from app import rating as glicko
from app import rating_service
from app.routers.quiz import _attempt_out, _pick_pool
from app.schemas import BlitzStartIn, QuizAttemptOut, RushStateOut
from app.subjects import SUBJECTS

router = APIRouter(prefix="/api/rush", tags=["rush"])

RUSH_MAX_STRIKES = 3
# Long enough that a good run is ended by mistakes, not by running out of
# questions -- the strike count has to be what stops you.
RUSH_MAX_QUESTIONS = 50

# Where the ramp begins, relative to the student's rating. Below their level
# on purpose: opening a scored run with a question they are likely to miss
# makes the whole mode feel unfair.
RAMP_START_OFFSET = -200.0
# Added per question. Over 50 questions this climbs ~600 points, which takes
# even a strong student past their ceiling before the pool runs out.
RAMP_STEP = 12.0


def build_ladder(
    db: Session, user_id: int, subject: str, pool: list[Question], n: int
) -> list[Question]:
    """
    Order `pool` into an increasingly hard ladder.

    Uses the student's own rating when it is settled; otherwise falls back to
    the hand-assigned difficulty, so a brand-new student still gets easy ->
    medium -> hard rather than a random jumble.
    """
    rated = []
    for q in pool:
        q_rating, _ = rating_service.question_rating_for(db, q)
        rated.append((q_rating, q))

    band = rating_service.target_difficulty_band(db, user_id, subject)
    if band is None:
        # No trustworthy rating yet: sort by measured difficulty and take an
        # even spread, which is the same shape without pretending to know the
        # student's level.
        rated.sort(key=lambda pair: pair[0])
        step = max(1, len(rated) // n)
        return [q for _, q in rated[::step]][:n]

    start = band[0] - 50.0 + RAMP_START_OFFSET
    remaining = dict(enumerate(rated))
    ladder: list[Question] = []

    for i in range(min(n, len(rated))):
        target = start + i * RAMP_STEP
        # Nearest unused question to this rung, with a little noise so the same
        # subject twice in a row is not the identical ladder.
        key = min(
            remaining,
            key=lambda k: abs(remaining[k][0] - target) + random.uniform(0, 40),
        )
        ladder.append(remaining.pop(key)[1])

    return ladder


@router.post("/start", response_model=QuizAttemptOut)
def start_rush(payload: BlitzStartIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.subject not in SUBJECTS:
        raise HTTPException(status_code=404, detail="Unknown subject.")

    pool, build = _pick_pool(db, user.id, payload.subject, None, None, None)
    if len(pool) < 10:
        pool = build(with_difficulty=False)
    if len(pool) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough questions in {payload.subject} to start a Rush run.",
        )

    selected = build_ladder(db, user.id, payload.subject, pool, min(len(pool), RUSH_MAX_QUESTIONS))

    attempt = QuizAttempt(
        user_id=user.id,
        mode="rush",
        subject=payload.subject,
        topic=None,
        question_ids=[q.id for q in selected],
        current_index=0,
        score=0,
        strikes=0,
        # No timer. The strike count is the pressure -- adding a clock as well
        # would collapse Rush back into Blitz.
        time_limit_seconds=None,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return _attempt_out(db, attempt)


@router.get("/{attempt_id}/state", response_model=RushStateOut)
def rush_state(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id or attempt.mode != "rush":
        raise HTTPException(status_code=404, detail="Rush run not found.")

    best = (
        db.query(QuizAttempt.score)
        .filter(
            QuizAttempt.user_id == user.id,
            QuizAttempt.mode == "rush",
            QuizAttempt.finished_at.isnot(None),
            QuizAttempt.id != attempt.id,
        )
        .order_by(QuizAttempt.score.desc())
        .first()
    )

    return RushStateOut(
        attempt_id=attempt.id,
        score=attempt.score,
        strikes=attempt.strikes or 0,
        strikes_allowed=RUSH_MAX_STRIKES,
        finished=attempt.finished_at is not None,
        personal_best=best[0] if best else 0,
    )
