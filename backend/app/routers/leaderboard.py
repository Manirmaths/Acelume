from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import fair_play
from app.auth import get_current_user
from app.database import get_db
from app.models import QuizAttempt, User, UserResponse, Question
from app.schemas import LeaderboardOut, LeaderboardEntry
from app.subjects import SUBJECTS

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

TOP_N = 50

# Boards the client may request. "points" is lifetime cumulative points (or
# per-subject correct answers); "blitz" is a high-score board over the 3-minute
# Blitz sprint. They are deliberately separate: cumulative points reward
# sustained practice and are effectively impossible for a new user to top,
# whereas a Blitz personal best is winnable on day one. Same schema for both --
# `points` carries whichever metric the board is about, and the client labels
# it accordingly.
BOARDS = ("points", "blitz")

# Points-per-correct-answer, kept in sync with the +10 awarded in
# routers/quiz.py -- used here to derive a subject-scoped "points" figure
# from UserResponse history, since User.points itself is a single global
# cumulative counter with no per-subject breakdown.
POINTS_PER_CORRECT = 10


@router.get("", response_model=LeaderboardOut)
def get_leaderboard(
    subject: str | None = Query(default=None),
    board: str = Query(default="points"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if subject is not None and subject not in SUBJECTS:
        raise HTTPException(status_code=404, detail="Unknown subject.")
    if board not in BOARDS:
        raise HTTPException(status_code=404, detail="Unknown leaderboard.")

    if board == "blitz":
        return _blitz_leaderboard(db, user, subject)
    if subject is None:
        return _overall_leaderboard(db, user)
    return _subject_leaderboard(db, user, subject)


def _exclude_flagged(db: Session, users: list[User], viewer: User) -> list[User]:
    """
    Drop fair-play-flagged accounts from a public board.

    Silent, and never applied to the viewer's own row -- a student must always
    be able to see themselves. Nobody is told anything about anybody: a
    flagged account simply stops appearing, keeps every learning feature, and
    is never accused of anything. See app/fair_play.py.
    """
    candidates = [u.id for u in users if u.id != viewer.id]
    if not candidates:
        return users
    flagged = fair_play.excluded_user_ids(db, candidates)
    return [u for u in users if u.id == viewer.id or u.id not in flagged]


def _overall_leaderboard(db: Session, user: User) -> LeaderboardOut:
    top_users = (
        db.query(User)
        .order_by(User.points.desc(), User.id.asc())
        # Over-fetch so removing flagged accounts still fills the board.
        .limit(TOP_N * 2)
        .all()
    )
    top_users = _exclude_flagged(db, top_users, user)[:TOP_N]

    entries = [
        LeaderboardEntry(
            rank=i + 1,
            username=u.username,
            points=u.points,
            current_streak=u.current_streak,
            is_you=(u.id == user.id),
        )
        for i, u in enumerate(top_users)
    ]

    if any(e.is_you for e in entries):
        your_rank = next(e.rank for e in entries if e.is_you)
    else:
        # User isn't in the visible top N -- compute their real rank so the
        # UI can still show "You're #123" below the cut-off list.
        higher_count = db.query(User).filter(User.points > user.points).count()
        your_rank = higher_count + 1

    return LeaderboardOut(entries=entries, your_rank=your_rank, your_points=user.points)


def _blitz_best_query(db: Session, subject: str | None):
    """Each user's best single Blitz round, optionally scoped to one subject.

    Ranked on best score rather than total or average deliberately: Blitz is a
    fixed 3-minute sprint, so a personal best is directly comparable between
    users, while a total would just re-rank by who has played most (which the
    points board already does) and an average would punish experimenting.

    Only finished attempts count -- an abandoned round sits at whatever score
    it reached when the student walked away, and counting those would let
    someone farm a high score by restarting until they got easy questions.
    """
    q = (
        db.query(
            QuizAttempt.user_id.label("user_id"),
            func.max(QuizAttempt.score).label("best_score"),
        )
        .filter(QuizAttempt.mode == "blitz", QuizAttempt.finished_at.isnot(None))
    )
    if subject is not None:
        q = q.filter(QuizAttempt.subject == subject)
    return q.group_by(QuizAttempt.user_id)


def _blitz_leaderboard(db: Session, user: User, subject: str | None) -> LeaderboardOut:
    ranked = (
        _blitz_best_query(db, subject)
        .order_by(func.max(QuizAttempt.score).desc(), QuizAttempt.user_id.asc())
        .limit(TOP_N)
        .all()
    )

    user_ids = [row.user_id for row in ranked]
    users_by_id = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    entries = []
    for i, row in enumerate(ranked):
        u = users_by_id.get(row.user_id)
        if not u:
            continue
        entries.append(LeaderboardEntry(
            rank=i + 1,
            username=u.username,
            points=row.best_score,
            current_streak=u.current_streak,
            is_you=(u.id == user.id),
        ))

    your_row = _blitz_best_query(db, subject).filter(QuizAttempt.user_id == user.id).first()
    your_best = your_row.best_score if your_row else 0

    if any(e.is_you for e in entries):
        your_rank = next(e.rank for e in entries if e.is_you)
    else:
        sub = _blitz_best_query(db, subject).subquery()
        your_rank = db.query(sub.c.user_id).filter(sub.c.best_score > your_best).count() + 1

    return LeaderboardOut(entries=entries, your_rank=your_rank, your_points=your_best)


def _subject_points_query(db: Session, subject: str):
    return (
        db.query(
            UserResponse.user_id.label("user_id"),
            (func.count(UserResponse.id) * POINTS_PER_CORRECT).label("subject_points"),
        )
        .join(Question, Question.id == UserResponse.question_id)
        .filter(Question.subject == subject, UserResponse.is_correct.is_(True))
        .group_by(UserResponse.user_id)
    )


def _subject_leaderboard(db: Session, user: User, subject: str) -> LeaderboardOut:
    ranked = (
        _subject_points_query(db, subject)
        .order_by(func.count(UserResponse.id).desc(), UserResponse.user_id.asc())
        .limit(TOP_N)
        .all()
    )

    user_ids = [row.user_id for row in ranked]
    users_by_id = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    entries = []
    for i, row in enumerate(ranked):
        u = users_by_id.get(row.user_id)
        if not u:
            continue
        entries.append(LeaderboardEntry(
            rank=i + 1,
            username=u.username,
            points=row.subject_points,
            current_streak=u.current_streak,
            is_you=(u.id == user.id),
        ))

    your_points_row = (
        _subject_points_query(db, subject).filter(UserResponse.user_id == user.id).first()
    )
    your_points = your_points_row.subject_points if your_points_row else 0

    if any(e.is_you for e in entries):
        your_rank = next(e.rank for e in entries if e.is_you)
    else:
        higher = _subject_points_query(db, subject).subquery()
        higher_count = (
            db.query(higher.c.user_id)
            .filter(higher.c.subject_points > your_points)
            .count()
        )
        your_rank = higher_count + 1

    return LeaderboardOut(entries=entries, your_rank=your_rank, your_points=your_points)
