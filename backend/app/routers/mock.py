import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.gamification import events
from app.models import Question, QuestionMastery, QuizAttempt, User, UserResponse
from app.routers.payments import free_mock_exams_used
from app.schemas import (
    MockAnswerIn, MockNavItem, MockNavOut, MockQuestionOut, MockStartIn, QuizAttemptOut, ResultsOut,
)
from app.subjects import SUBJECTS
from app.routers.quiz import _pick_pool, _attempt_out, _question_public, quiz_results, clamp_answer_seconds

router = APIRouter(prefix="/api/mock", tags=["mock"])

# Full JAMB UTME mock exam: English is compulsory + 3 subjects the candidate
# picks (their combination). Real UTME format, confirmed via web search:
# 60 English questions + 40 questions per other subject = 180 total,
# single 120-minute timer for the whole exam. Reuses the same QuizAttempt
# model and the existing /api/quiz/{id}/answer + /results endpoints --
# only /start is mode-specific, same pattern as blitz.py.
ENGLISH_QUESTIONS = 60
OTHER_SUBJECT_QUESTIONS = 40
MOCK_DURATION_SECONDS = 120 * 60


@router.post("/start", response_model=QuizAttemptOut)
def start_mock(payload: MockStartIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Freemium gate, first cut: everyone gets FREE_MOCK_EXAMS full mocks
    # (default 1) to evaluate the real UTME-format exam, then needs premium.
    # This is a genuine product/pricing decision -- picked "gate the full
    # mock, not regular practice" as the least disruptive freemium pattern
    # (matches how most Nigerian exam-prep competitors do it), but which
    # feature(s) are actually premium is the user's call to revisit, not a
    # settled decision baked in here.
    if not user.is_premium and free_mock_exams_used(db, user.id) >= settings.FREE_MOCK_EXAMS:
        raise HTTPException(
            status_code=402,
            detail=(
                f"You've used your {settings.FREE_MOCK_EXAMS} free full mock exam"
                f"{'s' if settings.FREE_MOCK_EXAMS != 1 else ''}. "
                "Upgrade to Premium for unlimited full mocks."
            ),
        )

    chosen = payload.subjects or []
    if len(chosen) != 3:
        raise HTTPException(status_code=400, detail="Choose exactly 3 subjects to sit alongside English.")
    if len(set(chosen)) != 3:
        raise HTTPException(status_code=400, detail="Choose 3 different subjects.")
    if "English" in chosen:
        raise HTTPException(status_code=400, detail="English is already compulsory -- choose 3 other subjects.")
    for s in chosen:
        if s not in SUBJECTS:
            raise HTTPException(status_code=404, detail=f"Unknown subject: {s}")

    question_ids: list[int] = []
    for subject, count in [("English", ENGLISH_QUESTIONS)] + [(s, OTHER_SUBJECT_QUESTIONS) for s in chosen]:
        pool, _build = _pick_pool(db, user.id, subject, None, None, None)
        if len(pool) < count:
            raise HTTPException(status_code=400, detail=f"Not enough questions in {subject} for a full mock exam.")
        question_ids.extend(q.id for q in random.sample(pool, count))

    attempt = QuizAttempt(
        user_id=user.id,
        mode="mock",
        subject=", ".join(["English"] + chosen),
        topic=None,
        question_ids=question_ids,
        current_index=0,
        score=0,
        time_limit_seconds=MOCK_DURATION_SECONDS,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return _attempt_out(db, attempt)


# ---------------------------------------------------------------------------
# Free-navigation exam flow: unlike quiz/blitz/smart_review's linear
# one-question-at-a-time endpoints (routers/quiz.py), a real JAMB CBT lets
# candidates jump between any question, mark ones for review, and only finds
# out their score after submitting the whole exam -- no instant per-question
# feedback. These endpoints are Mock-only (checked via _get_mock_attempt)
# and address questions by their position in the attempt (0-indexed) rather
# than requiring strict in-order answering.
# ---------------------------------------------------------------------------

def _get_mock_attempt(db: Session, attempt_id: int, user: User) -> QuizAttempt:
    attempt = db.get(QuizAttempt, attempt_id)
    if not attempt or attempt.user_id != user.id:
        raise HTTPException(status_code=404, detail="Mock exam attempt not found.")
    if attempt.mode != "mock":
        raise HTTPException(status_code=400, detail="This isn't a mock exam attempt.")
    return attempt


@router.get("/{attempt_id}/nav", response_model=MockNavOut)
def mock_nav(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = _get_mock_attempt(db, attempt_id, user)
    answered_ids = {
        qid for (qid,) in db.query(UserResponse.question_id).filter(UserResponse.attempt_id == attempt_id).all()
    }
    marked = set(attempt.marked_question_ids or [])
    items = [
        MockNavItem(index=i, question_id=qid, answered=qid in answered_ids, marked=qid in marked)
        for i, qid in enumerate(attempt.question_ids)
    ]
    return MockNavOut(
        items=items, finished=attempt.finished_at is not None,
        time_limit_seconds=attempt.time_limit_seconds, started_at=attempt.started_at,
    )


@router.get("/{attempt_id}/question/{index}", response_model=MockQuestionOut)
def mock_question(attempt_id: int, index: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = _get_mock_attempt(db, attempt_id, user)
    if index < 0 or index >= len(attempt.question_ids):
        raise HTTPException(status_code=404, detail="No such question in this attempt.")
    qid = attempt.question_ids[index]
    question = db.get(Question, qid)
    response = (
        db.query(UserResponse)
        .filter(UserResponse.attempt_id == attempt_id, UserResponse.question_id == qid)
        .first()
    )
    return MockQuestionOut(
        index=index, total=len(attempt.question_ids), question=_question_public(question),
        selected_option=response.selected_option if response else None,
        marked=qid in (attempt.marked_question_ids or []),
    )


@router.put("/{attempt_id}/answer/{index}", status_code=204)
def mock_save_answer(
    attempt_id: int, index: int, payload: MockAnswerIn,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    attempt = _get_mock_attempt(db, attempt_id, user)
    if attempt.finished_at:
        raise HTTPException(status_code=400, detail="This exam has already been submitted.")
    if index < 0 or index >= len(attempt.question_ids):
        raise HTTPException(status_code=404, detail="No such question in this attempt.")

    qid = attempt.question_ids[index]
    question = db.get(Question, qid)
    selected = (payload.selected_option or "").strip().upper()[:1]

    response = (
        db.query(UserResponse)
        .filter(UserResponse.attempt_id == attempt_id, UserResponse.question_id == qid)
        .first()
    )
    if not selected:
        # Clearing a previously-saved answer.
        if response:
            db.delete(response)
            db.commit()
        return

    is_correct = selected == question.correct_option
    seconds = clamp_answer_seconds(payload.answer_seconds)
    if response:
        response.selected_option = selected
        response.is_correct = is_correct
        # Accumulate rather than overwrite. Mock exams allow free navigation,
        # so a student can return to a question several times; the honest
        # total is all the time they spent on it, not just the final visit.
        if seconds is not None:
            response.answer_seconds = (response.answer_seconds or 0) + seconds
    else:
        db.add(UserResponse(
            user_id=user.id, question_id=qid, attempt_id=attempt_id,
            selected_option=selected, is_correct=is_correct,
            answer_seconds=seconds,
        ))
    # No points/streak/mastery credit here -- deliberately deferred to
    # mock_submit() so re-answering the same question before submitting
    # doesn't double-count, matching how a real exam only scores your final
    # answer once you submit.
    db.commit()


@router.put("/{attempt_id}/mark/{index}", status_code=204)
def mock_toggle_mark(attempt_id: int, index: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = _get_mock_attempt(db, attempt_id, user)
    if attempt.finished_at:
        raise HTTPException(status_code=400, detail="This exam has already been submitted.")
    if index < 0 or index >= len(attempt.question_ids):
        raise HTTPException(status_code=404, detail="No such question in this attempt.")

    qid = attempt.question_ids[index]
    marked = set(attempt.marked_question_ids or [])
    if qid in marked:
        marked.discard(qid)
    else:
        marked.add(qid)
    attempt.marked_question_ids = list(marked)
    db.commit()


@router.post("/{attempt_id}/submit", response_model=ResultsOut)
def mock_submit(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = _get_mock_attempt(db, attempt_id, user)
    if attempt.finished_at:
        raise HTTPException(status_code=400, detail="This exam has already been submitted.")

    responses = {
        r.question_id: r
        for r in db.query(UserResponse).filter(UserResponse.attempt_id == attempt_id).all()
    }
    correct_count = 0
    for qid in attempt.question_ids:
        r = responses.get(qid)
        is_correct = bool(r and r.is_correct)
        if is_correct:
            correct_count += 1
            # Ledger-backed so a resubmitted mock cannot re-award. Keyed on
            # attempt + question, matching the quiz flow.
            events.record(
                db, user=user, event_type=events.QUESTION_ANSWERED,
                event_key=f"{events.QUESTION_ANSWERED}:attempt={attempt.id}:q={qid}",
                source_id=str(attempt.id),
            )

        mastery = (
            db.query(QuestionMastery)
            .filter(QuestionMastery.user_id == user.id, QuestionMastery.question_id == qid)
            .first()
        )
        if mastery is None:
            mastery = QuestionMastery(user_id=user.id, question_id=qid)
            db.add(mastery)
        mastery.record_answer(is_correct)

    attempt.score = correct_count
    attempt.finished_at = datetime.utcnow()
    user.record_practice()

    # Completion bonus for the exam as a whole, separate from the per-question
    # XP above. Guarded by the attempt id so it can only ever fire once.
    events.record(
        db, user=user, event_type=events.MOCK_COMPLETED,
        event_key=f"{events.MOCK_COMPLETED}:attempt={attempt.id}",
        source_id=str(attempt.id),
        payload={"score": correct_count, "total": len(attempt.question_ids)},
    )
    db.commit()

    return quiz_results(attempt_id, db, user)
