from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from sqlalchemy import func

from app.models import UserResponse, ReviewQuestion, Question, QuizAttempt, User, QuestionMastery
from app.progress import compute_progress
from app.schemas import DashboardOut, DailyGoalIn, UnfinishedAttempt, UserOut, PracticeDay

DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"]

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

POINTS_PER_CORRECT = 10
# Duolingo-style daily goal presets (in points, +10 per correct answer).
DAILY_GOAL_PRESETS = [20, 50, 100, 150]


@router.get("", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    responses = db.query(UserResponse).filter(UserResponse.user_id == user.id).all()
    topic_stats, recommended_topics, score_estimate, total_answered = compute_progress(db, user.id)

    review_count = db.query(ReviewQuestion).filter(ReviewQuestion.user_id == user.id).count()
    exam_years = [
        y for (y,) in db.query(Question.year).filter(Question.year.isnot(None)).distinct().all()
    ]

    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    correct_today = sum(
        1 for r in responses if r.is_correct and r.timestamp and r.timestamp >= today_start
    )
    points_today = correct_today * POINTS_PER_CORRECT

    due_for_review_count = (
        db.query(QuestionMastery)
        .join(Question, Question.id == QuestionMastery.question_id)
        .filter(
            QuestionMastery.user_id == user.id,
            QuestionMastery.next_review_at <= datetime.utcnow(),
            Question.status == "active",
        )
        .count()
    )

    # Weekly streak calendar: fixed Monday-Sunday of the *current* week
    # (not a rolling 7-day window), matching a normal calendar-week view.
    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    practiced_dates = {r.timestamp.date() for r in responses if r.timestamp}
    practice_days = [
        PracticeDay(
            date=(monday + timedelta(days=i)).isoformat(),
            label=DAY_LABELS[i],
            practiced=(monday + timedelta(days=i)) in practiced_dates,
            is_today=(monday + timedelta(days=i)) == today,
            is_future=(monday + timedelta(days=i)) > today,
        )
        for i in range(7)
    ]

    # Best Blitz round, matching the metric on the Blitz leaderboard so the
    # number a student sees here is the one they're ranked on.
    blitz_best = (
        db.query(func.max(QuizAttempt.score))
        .filter(
            QuizAttempt.user_id == user.id,
            QuizAttempt.mode == "blitz",
            QuizAttempt.finished_at.isnot(None),
        )
        .scalar()
    ) or 0

    # Most recent unfinished attempt, so closing a tab mid-quiz doesn't
    # silently discard the progress. Deliberately excludes:
    #   - blitz: a 3-minute sprint resumed hours later is meaningless
    #   - anything older than 7 days: resurfacing a long-abandoned attempt is
    #     noise, not a helpful nudge
    cutoff = datetime.utcnow() - timedelta(days=7)
    stale_free = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.user_id == user.id,
            QuizAttempt.finished_at.is_(None),
            QuizAttempt.mode != "blitz",
            QuizAttempt.started_at >= cutoff,
        )
        .order_by(QuizAttempt.started_at.desc())
        .first()
    )
    unfinished = None
    if stale_free is not None:
        total = len(stale_free.question_ids or [])
        # Only worth resuming if there's actually something left to answer.
        if total and stale_free.current_index < total:
            unfinished = UnfinishedAttempt(
                id=stale_free.id,
                mode=stale_free.mode,
                subject=stale_free.subject,
                answered=stale_free.current_index,
                total=total,
            )

    return DashboardOut(
        points=user.points,
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        streak_freezes=user.streak_freezes,
        daily_goal=user.daily_goal,
        points_today=points_today,
        goal_met=points_today >= user.daily_goal,
        has_taken_diagnostic=user.has_taken_diagnostic,
        topic_stats=topic_stats,
        review_count=review_count,
        exam_years=exam_years,
        recommended_topics=recommended_topics,
        due_for_review_count=due_for_review_count,
        score_estimate=score_estimate,
        practice_days=practice_days,
        blitz_best=blitz_best,
        unfinished_attempt=unfinished,
    )


@router.put("/daily-goal", response_model=UserOut)
def set_daily_goal(payload: DailyGoalIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.daily_goal = payload.daily_goal
    db.commit()
    db.refresh(user)
    return user
