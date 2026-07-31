import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.gamification import config, events, missions, personal_best
from app.models import Question, QuizAttempt, UserResponse, ReviewQuestion, User, QuestionMastery
from app.schemas import (
    QuizStartIn, QuizAttemptOut, QuestionPublic, AnswerIn, AnswerOut, ResultsOut, ResultItem,
)
from app.subjects import SUBJECTS

router = APIRouter(prefix="/api/quiz", tags=["quiz"])

RECENT_EXCLUDE_LIMIT = 50

# Modes whose results are allowed to advance topic mastery. A diagnostic
# deliberately samples every subject shallowly, and "marked" replays questions
# the student already flagged, so neither is evidence of understanding a topic.
MASTERY_MODES = {"quiz", "blitz", "test_out"}
# Modes that count as the spec's timed "Master" challenge (no hints, on the
# clock). Only these can take a topic to three stars.
TIMED_MODES = {"blitz"}


def _attempt_subject_topic(db: Session, attempt: QuizAttempt) -> tuple[str | None, str | None]:
    """The subject/topic an attempt is *about*, or (None, None) if mixed."""
    qids = [q for q in attempt.question_ids if isinstance(q, int)]
    if not qids:
        return None, None
    rows = db.query(Question.subject, Question.topic).filter(Question.id.in_(qids)).all()
    subjects = {s for s, _ in rows if s}
    topics = {t for _, t in rows if t}
    return (
        subjects.pop() if len(subjects) == 1 else None,
        topics.pop() if len(topics) == 1 else None,
    )


def _record_personal_best(db: Session, user: User, attempt: QuizAttempt) -> None:
    subject, topic = _attempt_subject_topic(db, attempt)
    personal_best.record(
        db,
        user=user,
        mode=attempt.mode,
        subject=subject,
        topic=topic,
        correct=attempt.score,
        total=len(attempt.question_ids),
        attempt_id=attempt.id,
    )


def _record_topic_progress(db: Session, user: User, attempt: QuizAttempt) -> None:
    """
    On finishing an attempt, fold the result into topic mastery.

    Single-topic attempts only: a mixed-topic quiz is not evidence about any
    one topic, and crediting it would let a student "master" a topic they
    barely touched. The topic is taken from the questions themselves rather
    than attempt.topic, since a subject-wide quiz has no topic set but may
    still happen to be all one topic.
    """
    if attempt.mode not in MASTERY_MODES:
        return
    qids = [q for q in attempt.question_ids if isinstance(q, int)]
    if not qids:
        return

    rows = db.query(Question.subject, Question.topic).filter(Question.id.in_(qids)).all()
    pairs = {(s, t) for s, t in rows if s and t}
    if len(pairs) != 1:
        return

    subject, topic = pairs.pop()
    events.record_practice_result(
        db,
        user=user,
        subject=subject,
        topic=topic,
        correct=attempt.score,
        total=len(qids),
        attempt_id=attempt.id,
        timed=attempt.mode in TIMED_MODES,
    )

# Onboarding diagnostic: a short, broad sample across every subject so a
# brand-new user's Dashboard has real topic_stats *and* a projected score
# immediately, rather than waiting for them to stumble into enough regular
# practice on their own. 11 subjects x 3 = 33 answers, comfortably over
# dashboard.py's SCORE_ESTIMATE_MIN_ANSWERS (30) -- finishing the diagnostic
# unlocks the projected-score card in the same sitting.
DIAGNOSTIC_QUESTIONS_PER_SUBJECT = 3

# Practice-quiz pacing: give the student roughly a minute per question, with
# a floor so short quizzes still get a sane amount of time. (JAMB's own CBT
# is closer to ~40s/question under exam pressure -- this is deliberately
# more generous since it's untimed *practice*, not the real thing.)
SECONDS_PER_QUESTION = 60
MIN_TIME_LIMIT_SECONDS = 180


def _time_limit_for(n: int) -> int:
    return max(MIN_TIME_LIMIT_SECONDS, n * SECONDS_PER_QUESTION)


def _pick_pool(db: Session, user_id: int, subject: str | None, topic: str | None, difficulty: str | None, year: str | None = None):
    recent_ids = [
        qid for (qid,) in (
            db.query(UserResponse.question_id)
            .filter(UserResponse.user_id == user_id)
            .order_by(UserResponse.id.desc())
            .limit(RECENT_EXCLUDE_LIMIT)
            .all()
        )
    ]

    def build(with_difficulty: bool):
        q = db.query(Question).filter(Question.status == "active")
        if topic:
            q = q.filter(Question.topic == topic)
        elif subject:
            q = q.filter(Question.subject == subject)
        if year:
            q = q.filter(Question.year == year)
        if with_difficulty and difficulty is not None:
            q = q.filter(Question.difficulty == difficulty)
        if recent_ids:
            q = q.filter(~Question.id.in_(recent_ids))
        return q.all()

    pool = build(with_difficulty=True)
    return pool, build


def _question_public(q: Question) -> QuestionPublic:
    from app.schemas import PassageOut
    return QuestionPublic(
        id=q.id, question_id=q.question_id, subject=q.subject, topic=q.topic,
        subtopic=q.subtopic, difficulty=q.difficulty,
        question_text=q.question_text, image_url=q.image_url,
        option_a=q.option_a, option_b=q.option_b,
        option_c=q.option_c, option_d=q.option_d, year=q.year,
        passage=PassageOut.model_validate(q.passage) if q.passage else None,
    )


def _attempt_out(db: Session, attempt: QuizAttempt) -> QuizAttemptOut:
    finished = attempt.finished_at is not None or attempt.current_index >= len(attempt.question_ids)
    current_q = None
    if not finished:
        qid = attempt.question_ids[attempt.current_index]
        q = db.get(Question, qid)
        current_q = _question_public(q) if q else None
    return QuizAttemptOut(
        attempt_id=attempt.id,
        mode=attempt.mode,
        total=len(attempt.question_ids),
        current_index=attempt.current_index,
        time_limit_seconds=attempt.time_limit_seconds,
        per_question_seconds=attempt.per_question_seconds,
        current_question=current_q,
        finished=finished,
        score=attempt.score,
    )


@router.post("/start", response_model=QuizAttemptOut)
def start_quiz(payload: QuizStartIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = max(3, min(payload.n, 50))
    pool, build = _pick_pool(db, user.id, payload.subject, payload.topic, payload.difficulty, payload.year)

    if len(pool) < n and payload.difficulty is not None:
        pool = build(with_difficulty=False)

    if len(pool) < n:
        label = f"topic '{payload.topic}'" if payload.topic else (
            f"subject '{payload.subject}'" if payload.subject else "all subjects"
        )
        if payload.year:
            label += f" for {payload.year}"
        raise HTTPException(status_code=400, detail=f"Not enough questions in {label} for your selection.")

    selected = random.sample(pool, n)
    per_q = None
    if payload.per_q:
        per_q = max(15, min(payload.per_q, 180))

    attempt = QuizAttempt(
        user_id=user.id,
        mode="quiz",
        subject=payload.subject,
        topic=payload.topic,
        question_ids=[q.id for q in selected],
        current_index=0,
        score=0,
        time_limit_seconds=_time_limit_for(n),
        per_question_seconds=per_q,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return _attempt_out(db, attempt)


@router.post("/start-diagnostic", response_model=QuizAttemptOut)
def start_diagnostic(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.has_taken_diagnostic:
        raise HTTPException(status_code=400, detail="You've already taken the diagnostic.")

    question_ids: list[int] = []
    for subject in SUBJECTS:
        pool = (
            db.query(Question.id)
            .filter(Question.status == "active", Question.subject == subject)
            .all()
        )
        pool = [qid for (qid,) in pool]
        if not pool:
            continue
        n = min(DIAGNOSTIC_QUESTIONS_PER_SUBJECT, len(pool))
        question_ids.extend(random.sample(pool, n))

    if len(question_ids) < 10:
        # Should only happen on a near-empty dev DB -- a real deployed
        # question bank always clears this easily.
        raise HTTPException(status_code=400, detail="Not enough questions available yet for a diagnostic.")

    random.shuffle(question_ids)
    attempt = QuizAttempt(
        user_id=user.id,
        mode="diagnostic",
        subject=None,
        topic=None,
        question_ids=question_ids,
        current_index=0,
        score=0,
        time_limit_seconds=_time_limit_for(len(question_ids)),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return _attempt_out(db, attempt)


@router.get("/{attempt_id}", response_model=QuizAttemptOut)
def get_attempt(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")
    return _attempt_out(db, attempt)


@router.post("/{attempt_id}/answer", response_model=AnswerOut)
def answer_quiz(attempt_id: int, payload: AnswerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")
    if attempt.finished_at or attempt.current_index >= len(attempt.question_ids):
        raise HTTPException(status_code=400, detail="This quiz attempt is already finished.")

    expected_qid = attempt.question_ids[attempt.current_index]
    if payload.question_id != expected_qid:
        raise HTTPException(status_code=400, detail="This isn't the current question for this attempt.")

    question = db.get(Question, expected_qid)
    selected = (payload.selected_option or "").upper()[:1]
    is_correct = bool(selected) and selected == question.correct_option

    db.add(UserResponse(
        user_id=user.id,
        question_id=question.id,
        attempt_id=attempt.id,
        selected_option=selected,
        is_correct=is_correct,
    ))
    if is_correct:
        attempt.score += 1
    user.record_practice()

    mastery = (
        db.query(QuestionMastery)
        .filter(QuestionMastery.user_id == user.id, QuestionMastery.question_id == question.id)
        .first()
    )
    # Read this BEFORE record_answer() updates the counters: a question the
    # student has seen and got wrong at least once is what makes a later
    # correct answer a "mistake corrected".
    previously_missed = bool(
        mastery and mastery.times_seen > 0 and mastery.times_correct < mastery.times_seen
    )
    if mastery is None:
        mastery = QuestionMastery(user_id=user.id, question_id=question.id)
        db.add(mastery)
    mastery.record_answer(is_correct)

    # XP now flows through the ledger rather than a bare `user.points += 10`,
    # so it is auditable and cannot be double-awarded on a retry. The event
    # key is derived from the attempt and question, which is exactly the
    # granularity at which a repeat submission must be ignored.
    if is_correct:
        events.record(
            db, user=user, event_type=events.QUESTION_ANSWERED,
            event_key=f"{events.QUESTION_ANSWERED}:attempt={attempt.id}:q={question.id}",
            subject=question.subject, topic=question.topic, source_id=str(attempt.id),
        )
        missions.advance(db, user, kind=missions.PRACTICE, subject=question.subject)
        if previously_missed:
            # Awarded once per question for life, not once per attempt --
            # otherwise a student could farm it by deliberately missing.
            events.record(
                db, user=user, event_type=events.MISTAKE_CORRECTED,
                event_key=f"{events.MISTAKE_CORRECTED}:q={question.id}",
                subject=question.subject, topic=question.topic, source_id=str(attempt.id),
            )
            missions.advance(db, user, kind=missions.IMPROVEMENT)

    attempt.current_index += 1
    if attempt.current_index >= len(attempt.question_ids):
        attempt.finished_at = datetime.utcnow()
        if attempt.mode == "diagnostic":
            user.has_taken_diagnostic = True
        _record_topic_progress(db, user, attempt)

        # Mastery streak: a session of real length answered accurately. The
        # Learning streak (record_practice, above) already counted the day for
        # simply turning up; this one only counts if the work was good.
        total_qs = len(attempt.question_ids)
        if total_qs >= config.get(db, "streak_min_questions"):
            pct = round(100 * attempt.score / total_qs)
            user.record_mastery_day(pct >= config.get(db, "mastery_streak_pct"))

        # Checked after every finish rather than on a schedule, so the chest
        # appears the moment the third mission completes.
        missions.try_award_daily_chest(db, user)

        # Personal best. Recorded here (not in quiz_results) so it happens
        # exactly once per attempt -- results can be re-fetched freely.
        _record_personal_best(db, user, attempt)

        # A Smart Review session is the spec's "due review". It only counts as
        # passed at the practice threshold -- clicking through a review while
        # getting most of it wrong is not evidence of retention.
        if attempt.mode == "smart_review" and attempt.question_ids:
            pct = round(100 * attempt.score / len(attempt.question_ids))
            if pct >= config.get(db, "practice_pass_pct"):
                events.record(
                    db, user=user, event_type=events.REVIEW_COMPLETED,
                    event_key=f"{events.REVIEW_COMPLETED}:attempt={attempt.id}",
                    source_id=str(attempt.id),
                    payload={"pct": pct, "questions": len(attempt.question_ids)},
                )

    db.commit()
    db.refresh(attempt)

    return AnswerOut(
        is_correct=is_correct,
        correct_option=question.correct_option,
        explanation=question.explanation,
        next=_attempt_out(db, attempt),
    )


@router.post("/{attempt_id}/skip", response_model=QuizAttemptOut)
def skip_quiz_question(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    No-penalty skip: advances past the current question without recording a
    UserResponse, so no points/mastery/streak effects -- the student never
    actually attempted it. quiz_results() already treats a question with no
    response row as unanswered (blank, not wrong), so this needs no special
    handling on the results side. Deliberately doesn't reveal correct_option/
    explanation the way answer_quiz's AnswerOut does -- you skipped it, you
    don't get to see the answer.
    """
    attempt = db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")
    if attempt.finished_at or attempt.current_index >= len(attempt.question_ids):
        raise HTTPException(status_code=400, detail="This quiz attempt is already finished.")

    attempt.current_index += 1
    if attempt.current_index >= len(attempt.question_ids):
        attempt.finished_at = datetime.utcnow()
        if attempt.mode == "diagnostic":
            user.has_taken_diagnostic = True

    db.commit()
    db.refresh(attempt)
    return _attempt_out(db, attempt)


@router.post("/{attempt_id}/finish", response_model=QuizAttemptOut)
def finish_quiz(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Explicit finalize for the client-side countdown timer (Quiz.tsx): when
    time runs out, the session ends even if questions remain unanswered, but
    unlike answer_quiz/skip_quiz_question (which auto-set finished_at once
    current_index reaches the end), nothing else marks an early, incomplete
    attempt as finished. Without this, a timed-out attempt with unanswered
    questions left finished_at null forever even though the student was
    already bounced to the results page.

    A timed-out diagnostic still counts as "taken" -- has_taken_diagnostic
    gates whether the onboarding prompt is shown again, and forcing a student
    to redo the whole diagnostic just because the clock ran out would be
    punitive, not protective.

    Idempotent: safe to call even if the attempt already finished normally
    (e.g. the last answer request and the timeout firing in a near-tie) --
    just returns the current state rather than erroring.
    """
    attempt = db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")

    if not attempt.finished_at:
        attempt.finished_at = datetime.utcnow()
        if attempt.mode == "diagnostic":
            user.has_taken_diagnostic = True
        db.commit()
        db.refresh(attempt)

    return _attempt_out(db, attempt)


@router.get("/{attempt_id}/results", response_model=ResultsOut)
def quiz_results(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")

    # Iterate attempt.question_ids (the true set of questions in this
    # attempt), not just logged UserResponse rows -- a question left
    # unanswered (timeout, or skipped in the Mock exam's free-navigation
    # flow) has no response row at all, and computing total from responses
    # alone would silently shrink the denominator (e.g. "178/179" instead of
    # the correct "178/180"). Unanswered questions are reported with an
    # empty selected_option and is_correct=False, same semantics as an
    # explicit blank answer elsewhere in this file.
    responses_by_qid = {
        r.question_id: r
        for r in db.query(UserResponse).filter(UserResponse.attempt_id == attempt_id).all()
    }
    marked_ids = {
        rq.question_id for rq in db.query(ReviewQuestion).filter(ReviewQuestion.user_id == user.id).all()
    }

    items = []
    correct_count = 0
    for qid in attempt.question_ids:
        q = db.get(Question, qid)
        if not q:
            continue
        r = responses_by_qid.get(qid)
        is_correct = bool(r and r.is_correct)
        if is_correct:
            correct_count += 1
        items.append(ResultItem(
            question_id=q.id,
            question_text=q.question_text,
            image_url=q.image_url,
            selected_option=r.selected_option if r else "",
            correct_option=q.correct_option,
            is_correct=is_correct,
            is_marked=q.id in marked_ids,
            explanation=q.explanation,
        ))

    # Read the stored personal best rather than recomputing: recording happens
    # once when the attempt finishes, so re-opening results can never
    # accidentally re-file the same attempt or announce a best twice.
    pb_out = None
    subject, topic = _attempt_subject_topic(db, attempt)
    key = personal_best.activity_key(
        mode=attempt.mode, subject=subject, topic=topic,
        total=len(attempt.question_ids), difficulty=None,
    )
    stored = (
        db.query(PersonalBest)
        .filter(PersonalBest.user_id == user.id, PersonalBest.activity_key == key)
        .first()
    )
    if stored is not None and len(items):
        pct = round(100 * correct_count / len(items))
        is_baseline = stored.attempts <= 1
        is_best = (not is_baseline) and pct >= stored.best_pct
        result = personal_best.BestResult(
            is_baseline=is_baseline,
            is_best=is_best and pct > stored.baseline_pct,
            current_pct=pct,
            previous_best_pct=None if is_baseline else stored.best_pct,
            delta_points=None if is_baseline else pct - stored.best_pct,
            attempts=stored.attempts,
        )
        # Name the weakest topic so the advice points somewhere real rather
        # than telling the student vaguely to "try harder".
        weakest = None
        wrong = [i for i in items if not i.is_correct]
        if wrong:
            by_topic: dict[str, int] = {}
            for it in wrong:
                q = db.get(Question, it.question_id)
                if q and q.topic:
                    by_topic[q.topic] = by_topic.get(q.topic, 0) + 1
            if by_topic:
                weakest = max(by_topic, key=by_topic.get)
        pb_out = PersonalBestOut(
            is_baseline=result.is_baseline,
            is_best=result.is_best,
            current_pct=result.current_pct,
            previous_best_pct=result.previous_best_pct,
            delta_points=result.delta_points,
            attempts=result.attempts,
            message=personal_best.message_for(result, weakest),
        )

    return ResultsOut(score=correct_count, total=len(items), items=items, personal_best=pb_out)


@router.post("/{attempt_id}/retake-wrong", response_model=QuizAttemptOut)
def retake_wrong(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz attempt not found.")

    responses = db.query(UserResponse).filter(UserResponse.attempt_id == attempt_id).all()
    wrong_ids = [r.question_id for r in responses if not r.is_correct]
    if len(wrong_ids) < 3:
        raise HTTPException(status_code=400, detail="Not enough wrong questions to retake (need at least 3).")

    random.shuffle(wrong_ids)
    new_attempt = QuizAttempt(
        user_id=user.id, mode="quiz", subject=attempt.subject, topic=attempt.topic,
        question_ids=wrong_ids, current_index=0, score=0,
        time_limit_seconds=_time_limit_for(len(wrong_ids)),
    )
    db.add(new_attempt)
    db.commit()
    db.refresh(new_attempt)
    return _attempt_out(db, new_attempt)
