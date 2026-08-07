"""
Running a school's exam.

The service layer under routers/exams.py. Everything that is a rule rather
than an endpoint lives here.

Three invariants hold the feature together:

  - **One sitting per candidate.** Enforced by `submitted_at` and by the
    unique constraint on (session, registration_number). A student cannot
    restart to get a better score, and cannot sit under someone else's number
    without that person's access code.

  - **The clock belongs to the server.** `started_at` is set once, on the
    server, and remaining time is always computed from it. A phone with a
    wrong clock, a refreshed page, or a closed browser cannot buy more time.

  - **Correct answers never leave the server until the candidate submits.**
    Same rule as every other question surface in Acelume, and it matters more
    here because this is a real exam.
"""

from __future__ import annotations

import random
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ExamCandidate, ExamQuestion, ExamSession, Question

# Unambiguous alphabet: no O/0 or I/1. These get printed on a slip, read in a
# hurry by a fourteen-year-old, and typed into a phone.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

SESSION_CODE_LENGTH = 6
ACCESS_CODE_LENGTH = 6

# Grace beyond the stored duration, absorbing the gap between a slow phone
# submitting and the server receiving it. A student who answered in time
# should not lose the paper to their network.
SUBMIT_GRACE_SECONDS = 30


def _code(length: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def unique_session_code(db: Session) -> str:
    for _ in range(20):
        code = _code(SESSION_CODE_LENGTH)
        if not db.query(ExamSession).filter(ExamSession.code == code).first():
            return code
    raise RuntimeError("could not allocate an exam session code")


def create_candidates(
    db: Session, session: ExamSession, registrations: list[dict]
) -> list[ExamCandidate]:
    """
    Add candidates and issue their access codes.

    `registrations` is [{"registration_number": "001", "full_name": "..."}].
    The name is optional throughout -- a school that prefers to keep its pupils
    pseudonymous can hand out numbers only, and nothing downstream requires it.

    Question order is shuffled per candidate. Same paper, different sequence,
    which makes reading off the next screen along much harder without needing
    any invigilation software.
    """
    existing = {
        c.registration_number for c in
        db.query(ExamCandidate).filter(ExamCandidate.session_id == session.id).all()
    }
    used_codes = {
        c.access_code for c in
        db.query(ExamCandidate).filter(ExamCandidate.session_id == session.id).all()
    }

    made: list[ExamCandidate] = []
    for entry in registrations:
        reg = str(entry.get("registration_number", "")).strip()
        if not reg or reg in existing:
            continue

        for _ in range(20):
            code = _code(ACCESS_CODE_LENGTH)
            if code not in used_codes:
                break
        used_codes.add(code)
        existing.add(reg)

        order = list(session.question_ids or [])
        random.shuffle(order)

        candidate = ExamCandidate(
            session_id=session.id,
            registration_number=reg,
            access_code=code,
            full_name=(entry.get("full_name") or "").strip() or None,
            question_order=order,
        )
        db.add(candidate)
        made.append(candidate)

    db.flush()
    return made


def build_paper(db: Session, session: ExamSession) -> list[int]:
    """
    Assemble the question set from the blueprint.

    For an uploaded paper the order is the teacher's own, because they wrote it
    that way on purpose. For a bank paper the questions are sampled per subject
    to the requested counts.
    """
    if session.source == "upload":
        rows = (
            db.query(ExamQuestion)
            .filter(ExamQuestion.session_id == session.id)
            .order_by(ExamQuestion.position, ExamQuestion.id)
            .all()
        )
        return [r.id for r in rows]

    picked: list[int] = []
    for entry in session.blueprint or []:
        subject = entry.get("subject")
        count = int(entry.get("count") or 0)
        if not subject or count <= 0:
            continue
        pool = (
            db.query(Question)
            .filter(Question.status == "active", Question.subject == subject)
            .all()
        )
        if not pool:
            continue
        picked.extend(q.id for q in random.sample(pool, min(count, len(pool))))
    return picked


def blueprint_shortfall(db: Session, blueprint: list[dict]) -> list[str]:
    """
    Warn BEFORE the exam that a subject cannot fill its quota.

    Discovering on exam day that Commerce only had 12 of the 40 questions asked
    for is the kind of thing that ends a school relationship. Better to say so
    while the session is still a draft.
    """
    problems = []
    for entry in blueprint or []:
        subject = entry.get("subject")
        count = int(entry.get("count") or 0)
        if not subject or count <= 0:
            continue
        have = (
            db.query(Question)
            .filter(Question.status == "active", Question.subject == subject)
            .count()
        )
        if have < count:
            problems.append(f"{subject}: asked for {count}, only {have} available")
    return problems


def question_payload(db: Session, session: ExamSession, question_id: int) -> dict | None:
    """
    One question as the candidate sees it. Never includes the correct answer.
    """
    if session.source == "upload":
        q = db.get(ExamQuestion, question_id)
        if q is None or q.session_id != session.id:
            return None
        return {
            "id": q.id, "subject": q.subject, "topic": q.topic,
            "question_text": q.question_text, "image_url": q.image_url,
            "option_a": q.option_a, "option_b": q.option_b,
            "option_c": q.option_c, "option_d": q.option_d,
        }

    q = db.get(Question, question_id)
    if q is None:
        return None
    return {
        "id": q.id, "subject": q.subject, "topic": q.topic,
        "question_text": q.question_text, "image_url": q.image_url,
        "option_a": q.option_a, "option_b": q.option_b,
        "option_c": q.option_c, "option_d": q.option_d,
    }


def correct_answers(db: Session, session: ExamSession) -> dict[int, str]:
    if session.source == "upload":
        rows = db.query(ExamQuestion).filter(ExamQuestion.session_id == session.id).all()
        return {r.id: r.correct_option for r in rows}
    ids = list(session.question_ids or [])
    if not ids:
        return {}
    rows = db.query(Question).filter(Question.id.in_(ids)).all()
    return {r.id: r.correct_option for r in rows}


def seconds_remaining(session: ExamSession, candidate: ExamCandidate) -> int:
    """
    Time left, computed from the SERVER's record of when they started.

    Never trusted to the client. Refreshing the page, closing the browser or
    changing the phone clock cannot buy a single extra second.
    """
    if candidate.started_at is None:
        return session.duration_minutes * 60
    elapsed = (datetime.utcnow() - candidate.started_at).total_seconds()
    return max(0, int(session.duration_minutes * 60 - elapsed))


def is_open(session: ExamSession, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return session.status == "ready" and session.opens_at <= now <= session.closes_at


def grade(db: Session, session: ExamSession, candidate: ExamCandidate) -> int:
    """
    Score a candidate from their stored answers. Idempotent.

    Unanswered questions score zero rather than being excluded -- this is an
    exam, and a blank is a wrong answer.
    """
    key = correct_answers(db, session)
    score = 0
    for qid_str, chosen in (candidate.answers or {}).items():
        try:
            qid = int(qid_str)
        except (TypeError, ValueError):
            continue
        if chosen and key.get(qid) == chosen:
            score += 1
    return score


def submit(db: Session, session: ExamSession, candidate: ExamCandidate) -> int:
    """
    Finalise a paper. Safe to call twice -- the first submission stands.

    A repeated call cannot re-grade, which matters when a flaky connection
    makes a student tap Submit three times.
    """
    if candidate.submitted_at is not None:
        return candidate.score
    candidate.score = grade(db, session, candidate)
    candidate.submitted_at = datetime.utcnow()
    return candidate.score


def auto_submit_expired(db: Session, session: ExamSession) -> int:
    """
    Close papers whose time ran out while nobody was looking.

    A student whose phone died mid-exam must still be scored on what they
    answered, and a session cannot be reported as finished while candidates
    sit in limbo. Called whenever results are read.
    """
    closed = 0
    limit = timedelta(minutes=session.duration_minutes, seconds=SUBMIT_GRACE_SECONDS)
    now = datetime.utcnow()

    rows = (
        db.query(ExamCandidate)
        .filter(
            ExamCandidate.session_id == session.id,
            ExamCandidate.started_at.isnot(None),
            ExamCandidate.submitted_at.is_(None),
        )
        .all()
    )
    for candidate in rows:
        if now - candidate.started_at >= limit:
            submit(db, session, candidate)
            closed += 1
    return closed
