"""
Asynchronous quiz battles.

Design constraints that shaped this, all from the spec:

  - **The server picks and grades the questions.** The client never chooses,
    and never receives correct answers until that participant has submitted.
  - **Correctness outranks speed.** The tiebreak order is most correct, then
    most attempted, then lower average time on CORRECT answers, then a draw.
    Ranking on speed would reward guessing.
  - **One valid attempt each**, enforced by a UNIQUE constraint rather than an
    application check.
  - **Invitations expire**, and an expired code cannot be reused.
  - No chat. Reactions can come later as a fixed preset list.
"""

import random
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.gamification import events
from app.models import Battle, BattleParticipant, Question, User
from app.rate_limit import limiter
from app.schemas import (
    BattleCreateIn, BattleOut, BattleQuestionOut, BattleResultOut,
    BattleSubmitIn, BattleSideOut, BattleLiveOut, BattleLiveAnswerIn,
)
from app.subjects import SUBJECTS

router = APIRouter(prefix="/api/battles", tags=["battles"])

QUESTION_CHOICES = (5, 10)

# Live battles: every deadline is derived from Battle.started_at on the SERVER.
# A short grace period absorbs network latency so a student on a slow
# connection is not punished for an answer that left their phone in time.
LIVE_GRACE_SECONDS = 3
INVITE_TTL_HOURS = 48
MAX_OPEN_BATTLES = 5


def _code() -> str:
    # Unambiguous alphabet: no O/0 or I/1, since these get read aloud and
    # retyped from a WhatsApp message.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))


@router.post("", response_model=BattleOut)
@limiter.limit("20/hour")
def create_battle(
    # slowapi resolves the client from this; it must be present and typed.
    request: Request,
    payload: BattleCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.subject not in SUBJECTS:
        raise HTTPException(status_code=404, detail="Unknown subject.")
    if payload.questions not in QUESTION_CHOICES:
        raise HTTPException(status_code=400, detail="Choose 5 or 10 questions.")
    if payload.mode not in ("async", "live"):
        raise HTTPException(status_code=400, detail="Unknown battle mode.")

    # Cap open invitations so challenge codes cannot be used to spam.
    open_count = (
        db.query(Battle)
        .filter(
            Battle.created_by == user.id,
            Battle.status == "open",
            Battle.expires_at > datetime.utcnow(),
        )
        .count()
    )
    if open_count >= MAX_OPEN_BATTLES:
        raise HTTPException(
            status_code=429,
            detail="You already have several open challenges. Finish or let them expire first.",
        )

    q = db.query(Question).filter(Question.status == "active", Question.subject == payload.subject)
    if payload.topic:
        q = q.filter(Question.topic == payload.topic)
    pool = q.all()
    if len(pool) < payload.questions:
        raise HTTPException(status_code=400, detail="Not enough questions for a battle here yet.")

    selected = random.sample(pool, payload.questions)
    battle = Battle(
        code=_code(),
        created_by=user.id,
        subject=payload.subject,
        topic=payload.topic,
        # Chosen once, server-side, and stored -- this is what guarantees both
        # participants face an identical set.
        question_ids=[x.id for x in selected],
        seconds_per_question=30,
        mode=payload.mode,
        expires_at=datetime.utcnow() + timedelta(hours=INVITE_TTL_HOURS),
    )
    db.add(battle)
    db.flush()
    db.add(BattleParticipant(battle_id=battle.id, user_id=user.id))
    db.commit()
    db.refresh(battle)
    return _battle_out(db, battle, user)


@router.post("/{code}/join", response_model=BattleOut)
def join_battle(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    battle = db.query(Battle).filter(Battle.code == code.upper()).first()
    if battle is None:
        raise HTTPException(status_code=404, detail="Challenge not found.")
    if battle.expires_at <= datetime.utcnow():
        # An expired invitation cannot be reused, even by someone holding the code.
        raise HTTPException(status_code=410, detail="This challenge has expired.")

    participants = db.query(BattleParticipant).filter(BattleParticipant.battle_id == battle.id).all()
    if any(p.user_id == user.id for p in participants):
        return _battle_out(db, battle, user)
    if len(participants) >= 2:
        raise HTTPException(status_code=400, detail="This challenge already has two players.")

    db.add(BattleParticipant(battle_id=battle.id, user_id=user.id))
    if battle.mode == "live" and battle.started_at is None:
        # The clock starts on the SERVER when the second player arrives, and
        # every subsequent deadline is derived from this single timestamp.
        battle.started_at = datetime.utcnow()
    db.commit()
    db.refresh(battle)
    return _battle_out(db, battle, user)


@router.get("/{code}/questions", response_model=list[BattleQuestionOut])
def battle_questions(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    battle, me = _require_participant(db, code, user)
    if me.submitted_at is not None:
        raise HTTPException(status_code=400, detail="You have already submitted this battle.")

    out = []
    for qid in battle.question_ids:
        q = db.get(Question, qid)
        if not q:
            continue
        # No correct_option, no explanation. They are withheld until this
        # participant submits, so they cannot be read from the network tab.
        out.append(BattleQuestionOut(
            id=q.id, question_text=q.question_text, image_url=q.image_url,
            option_a=q.option_a, option_b=q.option_b,
            option_c=q.option_c, option_d=q.option_d,
        ))
    return out


@router.post("/{code}/submit", response_model=BattleResultOut)
def submit_battle(
    code: str,
    payload: BattleSubmitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    battle, me = _require_participant(db, code, user)
    if me.submitted_at is not None:
        # One valid attempt each. Re-submitting returns the existing result
        # rather than re-grading, so a retry cannot improve a score.
        return _result_out(db, battle, user)

    correct = 0
    attempted = 0
    correct_seconds = 0
    for qid in battle.question_ids:
        answer = payload.answers.get(str(qid)) or payload.answers.get(qid)  # type: ignore[arg-type]
        if not answer:
            continue
        attempted += 1
        q = db.get(Question, qid)
        if q and (answer.selected or "").upper()[:1] == q.correct_option:
            correct += 1
            correct_seconds += max(0, min(answer.seconds or 0, battle.seconds_per_question))

    me.answers = {str(k): (v.selected or "") for k, v in payload.answers.items()}
    me.score = correct
    me.attempted = attempted
    me.correct_seconds = correct_seconds
    me.submitted_at = datetime.utcnow()

    others = (
        db.query(BattleParticipant)
        .filter(BattleParticipant.battle_id == battle.id, BattleParticipant.user_id != user.id)
        .all()
    )
    if others and all(o.submitted_at is not None for o in others):
        battle.status = "complete"

    events.record(
        db, user=user, event_type=events.BATTLE_COMPLETED,
        event_key=f"{events.BATTLE_COMPLETED}:battle={battle.id}:user={user.id}",
        subject=battle.subject, topic=battle.topic, source_id=str(battle.id),
        payload={"score": correct, "total": len(battle.question_ids)},
        award_xp=False,  # battle XP is deliberately not awarded twice over practice
    )
    db.commit()
    return _result_out(db, battle, user)



@router.get("/{code}/live", response_model=BattleLiveOut)
def live_state(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Server-authoritative state for a live battle.

    WHY POLLING RATHER THAN WEBSOCKETS
    ----------------------------------
    The obvious way to build "live" is a websocket. This deliberately does not.

    Acelume's Android app is a WebView shell, and its users are largely on
    Nigerian mobile networks where connections drop, stall and change IP
    routinely. A websocket turns every one of those events into a broken
    session that has to be detected, torn down and re-established with state
    reconciliation -- and getting that wrong ruins a match a student cared
    about, which is exactly the failure the spec warns about.

    Polling a stateless endpoint has none of that. Every response is complete
    and self-describing, so a client that vanishes for twenty seconds simply
    asks again and is told exactly where the battle is. A dropped connection
    is indistinguishable from a slow one, which is the correct behaviour.

    The trade is a few seconds of latency on the opponent's progress
    indicator. For a 30-second-per-question quiz that is imperceptible; the
    QUESTION timing itself is exact because it is derived from
    `Battle.started_at` on the server, not from message arrival.
    """
    battle, me = _require_participant(db, code, user)
    if battle.mode != "live":
        raise HTTPException(status_code=400, detail="This is not a live battle.")

    me.last_seen_at = datetime.utcnow()

    total = len(battle.question_ids)
    if battle.started_at is None:
        db.commit()
        return BattleLiveOut(
            code=battle.code, started=False, current_index=None,
            current_question_id=None,
            seconds_remaining=None, total=total, finished=False,
            you_answered=0, opponent_answered=0, opponent_present=False,
        )

    # The current question is a pure function of elapsed server time, so both
    # players are always shown the same one without any message passing.
    elapsed = (datetime.utcnow() - battle.started_at).total_seconds()
    per_q = battle.seconds_per_question
    index = int(elapsed // per_q)
    finished = index >= total

    seconds_remaining = None
    if not finished:
        seconds_remaining = max(0, int(per_q - (elapsed % per_q)))

    opponent = (
        db.query(BattleParticipant)
        .filter(BattleParticipant.battle_id == battle.id, BattleParticipant.user_id != user.id)
        .first()
    )
    # "Present" is presentational only. A student who loses signal must never
    # forfeit -- their answers already submitted still stand, and they rejoin
    # at whatever question the clock has reached.
    opponent_present = bool(
        opponent and opponent.last_seen_at
        and (datetime.utcnow() - opponent.last_seen_at).total_seconds() < 30
    )

    db.commit()
    return BattleLiveOut(
        code=battle.code,
        started=True,
        current_index=None if finished else index,
        current_question_id=None if finished else battle.question_ids[index],
        seconds_remaining=seconds_remaining,
        total=total,
        finished=finished,
        you_answered=len(me.answers or {}),
        opponent_answered=len(opponent.answers or {}) if opponent else 0,
        opponent_present=opponent_present,
    )


@router.post("/{code}/live/answer", response_model=BattleLiveOut)
def live_answer(
    code: str,
    payload: BattleLiveAnswerIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Answer the CURRENT live question.

    The server decides which question is current, so a client cannot answer
    ahead, go back, or replay a question whose window has closed. A short
    grace period absorbs latency -- a student on a slow connection should not
    lose an answer that left their phone in time.
    """
    battle, me = _require_participant(db, code, user)
    if battle.mode != "live":
        raise HTTPException(status_code=400, detail="This is not a live battle.")
    if battle.started_at is None:
        raise HTTPException(status_code=400, detail="This battle has not started yet.")

    total = len(battle.question_ids)
    elapsed = (datetime.utcnow() - battle.started_at).total_seconds()
    per_q = battle.seconds_per_question
    index = int(elapsed // per_q)

    if payload.index != index:
        # Allow the immediately-previous question within the grace window,
        # which is the realistic case: the student tapped in time, the request
        # arrived late.
        within_grace = (
            payload.index == index - 1 and (elapsed % per_q) <= LIVE_GRACE_SECONDS
        )
        if not within_grace:
            raise HTTPException(status_code=409, detail="That question has closed.")

    if payload.index < 0 or payload.index >= total:
        raise HTTPException(status_code=400, detail="No such question in this battle.")

    qid = battle.question_ids[payload.index]
    answers = dict(me.answers or {})
    if str(qid) in answers:
        # One answer per question. Changing it after the fact would let a
        # player revise once they had seen the opponent's progress.
        raise HTTPException(status_code=409, detail="You have already answered this question.")

    answers[str(qid)] = (payload.selected or "").upper()[:1]
    me.answers = answers
    db.commit()
    return live_state(code=code, db=db, user=user)


@router.post("/{code}/live/finish", response_model=BattleResultOut)
def live_finish(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Grade a finished live battle.

    Safe to call repeatedly and from either player: grading is idempotent per
    participant, and a student whose connection died mid-battle still gets
    their submitted answers scored rather than forfeiting.
    """
    battle, me = _require_participant(db, code, user)
    if battle.mode != "live":
        raise HTTPException(status_code=400, detail="This is not a live battle.")
    if me.submitted_at is not None:
        return _result_out(db, battle, user)
    if battle.started_at is None:
        raise HTTPException(status_code=400, detail="This battle has not started yet.")

    elapsed = (datetime.utcnow() - battle.started_at).total_seconds()
    if elapsed < len(battle.question_ids) * battle.seconds_per_question:
        raise HTTPException(status_code=400, detail="This battle is still running.")

    _grade_live(db, battle, me)

    others = (
        db.query(BattleParticipant)
        .filter(BattleParticipant.battle_id == battle.id, BattleParticipant.user_id != user.id)
        .all()
    )

    # Resolve the opponent too, once their grace window has also closed.
    #
    # Without this, a battle where the other phone died never settles: their
    # submitted_at stays null, status never reaches "complete", and the student
    # who did finish sits on "waiting for your opponent" forever. The clock is
    # SHARED, so once it has run out their answers are final whether or not
    # their phone is still alive -- grading them from what they already sent is
    # exactly as valid as grading yourself, and it is the only outcome that
    # honours "losing signal never forfeits".
    if elapsed >= len(battle.question_ids) * battle.seconds_per_question + LIVE_GRACE_SECONDS:
        for o in others:
            if o.submitted_at is None:
                _grade_live(db, battle, o)

    if others and all(o.submitted_at is not None for o in others):
        battle.status = "complete"

    events.record(
        db, user=user, event_type=events.BATTLE_COMPLETED,
        event_key=f"{events.BATTLE_COMPLETED}:battle={battle.id}:user={user.id}",
        subject=battle.subject, topic=battle.topic, source_id=str(battle.id),
        payload={"score": me.score, "total": len(battle.question_ids), "mode": "live"},
        award_xp=False,
    )
    db.commit()
    return _result_out(db, battle, user)


@router.get("/{code}", response_model=BattleResultOut)
def battle_result(code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    battle, _ = _require_participant(db, code, user)
    return _result_out(db, battle, user)


# ---------------------------------------------------------------------------


def _grade_live(db: Session, battle: Battle, p: BattleParticipant) -> None:
    """Score one participant of a finished live battle from their stored answers."""
    correct = 0
    attempted = 0
    for qid in battle.question_ids:
        selected = (p.answers or {}).get(str(qid))
        if not selected:
            continue
        attempted += 1
        q = db.get(Question, qid)
        if q and selected == q.correct_option:
            correct += 1

    p.score = correct
    p.attempted = attempted
    # Live battles are paced by a shared clock, so per-question timing carries
    # no information -- everyone had exactly the same window. Ties therefore
    # fall through to attempted, then to a draw.
    p.correct_seconds = 0
    p.submitted_at = datetime.utcnow()


def _require_participant(db: Session, code: str, user: User) -> tuple[Battle, BattleParticipant]:
    battle = db.query(Battle).filter(Battle.code == code.upper()).first()
    if battle is None:
        raise HTTPException(status_code=404, detail="Challenge not found.")
    me = (
        db.query(BattleParticipant)
        .filter(BattleParticipant.battle_id == battle.id, BattleParticipant.user_id == user.id)
        .first()
    )
    if me is None:
        raise HTTPException(status_code=403, detail="You are not in this challenge.")
    return battle, me


def _battle_out(db: Session, battle: Battle, user: User) -> BattleOut:
    participants = db.query(BattleParticipant).filter(BattleParticipant.battle_id == battle.id).all()
    return BattleOut(
        code=battle.code,
        subject=battle.subject,
        topic=battle.topic,
        questions=len(battle.question_ids),
        seconds_per_question=battle.seconds_per_question,
        status=battle.status,
        expires_at=battle.expires_at.isoformat(),
        players=len(participants),
        you_submitted=any(p.user_id == user.id and p.submitted_at for p in participants),
        mode=battle.mode,
        started_at=battle.started_at.isoformat() if battle.started_at else None,
    )


def _side(db: Session, p: BattleParticipant) -> BattleSideOut:
    u = db.get(User, p.user_id)
    return BattleSideOut(
        username=u.username if u else "Unknown",
        score=p.score,
        attempted=p.attempted,
        submitted=p.submitted_at is not None,
        # Average seconds on CORRECT answers only -- a tiebreak, never a
        # primary ranking, so rushing wrong answers gains nothing.
        avg_correct_seconds=round(p.correct_seconds / p.score) if p.score else None,
    )


def _result_out(db: Session, battle: Battle, user: User) -> BattleResultOut:
    parts = db.query(BattleParticipant).filter(BattleParticipant.battle_id == battle.id).all()
    me = next(p for p in parts if p.user_id == user.id)
    them = next((p for p in parts if p.user_id != user.id), None)

    outcome = "waiting"
    if them is not None and me.submitted_at and them.submitted_at:
        outcome = _decide(me, them)
    elif me.submitted_at and them is None:
        outcome = "waiting"

    # Answers and explanations only once THIS participant has submitted.
    review = []
    if me.submitted_at:
        for qid in battle.question_ids:
            q = db.get(Question, qid)
            if not q:
                continue
            review.append({
                "question_id": q.id,
                "question_text": q.question_text,
                "correct_option": q.correct_option,
                "your_answer": (me.answers or {}).get(str(qid), ""),
                "explanation": q.explanation,
            })

    return BattleResultOut(
        code=battle.code,
        subject=battle.subject,
        status=battle.status,
        mode=battle.mode,
        outcome=outcome,
        you=_side(db, me),
        opponent=_side(db, them) if them else None,
        review=review,
    )


def _decide(me: BattleParticipant, them: BattleParticipant) -> str:
    """
    Correctness first, always.

    Order: most correct -> most attempted -> lower average time on correct
    answers -> draw. Speed is the LAST tiebreak on purpose; ranking on it
    would reward fast guessing over careful work.
    """
    if me.score != them.score:
        return "won" if me.score > them.score else "lost"
    if me.attempted != them.attempted:
        return "won" if me.attempted > them.attempted else "lost"

    mine = (me.correct_seconds / me.score) if me.score else float("inf")
    theirs = (them.correct_seconds / them.score) if them.score else float("inf")
    if mine == theirs:
        return "draw"
    return "won" if mine < theirs else "lost"
