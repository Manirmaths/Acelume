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


# Registration number format: one letter, seven digits, two letters.
# e.g. A1234567BC -- ten characters, unique across every exam ever run.
#
# I and O are excluded from the letter positions. The format itself already
# disambiguates (position 1 is always a letter, so it cannot be a zero), but a
# number gets transcribed by hand from a printed slip by a fourteen-year-old,
# and removing the two characters people actually misread costs nothing.
_REG_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_REG_DIGITS = "0123456789"

REGISTRATION_LENGTH = 10


def _code(length: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def _registration_candidate() -> str:
    return (
        secrets.choice(_REG_LETTERS)
        + "".join(secrets.choice(_REG_DIGITS) for _ in range(7))
        + "".join(secrets.choice(_REG_LETTERS) for _ in range(2))
    )


def issue_registration_number(db: Session) -> str:
    """
    Allocate a registration number that has never been issued before.

    Reserved in IssuedRegistration immediately, and that row is never deleted.
    Deleting a candidate or an entire session does not free the number back
    into circulation -- a registration number appearing on two different papers
    years apart would discredit the whole system.

    The space is 24 x 10^7 x 24^2 = about 13.8 billion, so collisions are
    vanishingly rare; the retry loop exists for correctness, not because it is
    expected to run.
    """
    from app.models import IssuedRegistration

    for _ in range(50):
        number = _registration_candidate()
        exists = (
            db.query(IssuedRegistration)
            .filter(IssuedRegistration.number == number)
            .first()
        )
        if exists:
            continue
        db.add(IssuedRegistration(number=number))
        db.flush()
        return number
    raise RuntimeError("could not allocate a unique registration number")


def unique_session_code(db: Session) -> str:
    for _ in range(20):
        code = _code(SESSION_CODE_LENGTH)
        if not db.query(ExamSession).filter(ExamSession.code == code).first():
            return code
    raise RuntimeError("could not allocate an exam session code")


def subject_blocks(db: Session, session: ExamSession) -> list[tuple[str, list[int]]]:
    """
    The paper split into subject sections, in the examiner's own order.

    A multi-subject paper is a sequence of papers: English 1-20, then
    Mathematics 21-40. Interleaving them is not a harder exam, it is a worse
    one -- the candidate pays a context-switch cost twenty times over that has
    nothing to do with what is being measured, and cannot budget time per
    subject because they cannot see where a subject ends.

    Order comes from `session.question_ids`, which `build_paper` already emits
    blueprint-first, so this preserves whatever the examiner set up. Questions
    with no subject recorded are grouped under "" and kept last.
    """
    ids = list(session.question_ids or [])
    if not ids:
        return []

    subjects = _subject_lookup(db, session, ids)

    blocks: list[tuple[str, list[int]]] = []
    index: dict[str, list[int]] = {}
    for qid in ids:
        name = subjects.get(qid) or ""
        if name not in index:
            index[name] = []
            blocks.append((name, index[name]))
        index[name].append(qid)

    # Unlabelled questions trail the named ones rather than opening the paper.
    return sorted(blocks, key=lambda b: b[0] == "")


def _subject_lookup(db: Session, session: ExamSession, ids: list[int]) -> dict[int, str]:
    model = ExamQuestion if session.source == "upload" else Question
    rows = db.query(model.id, model.subject).filter(model.id.in_(ids)).all()
    return {row[0]: row[1] for row in rows}


def candidate_order(db: Session, session: ExamSession) -> list[int]:
    """
    A per-candidate question order: shuffled WITHIN each subject, never across.

    The shuffle exists so the screen next along shows a different question at
    the same moment, which is most of what invigilation software buys without
    installing anything. Confining it to the subject block keeps that property
    while leaving the paper's structure intact.
    """
    order: list[int] = []
    for _subject, block in subject_blocks(db, session):
        shuffled = list(block)
        random.shuffle(shuffled)
        order.extend(shuffled)
    return order


def reissue_orders(db: Session, session: ExamSession) -> int:
    """
    Re-draw the question order for candidates who have not started yet.

    Re-uploading a corrected question file replaces the paper, which would
    otherwise leave already-registered candidates holding an order that points
    at deleted rows -- they would open the exam and find it half empty.
    Candidates who are mid-paper keep their order untouched; changing the exam
    under someone already sitting it is worse than a stale one.
    """
    stale = (
        db.query(ExamCandidate)
        .filter(
            ExamCandidate.session_id == session.id,
            ExamCandidate.started_at.is_(None),
        )
        .all()
    )
    for candidate in stale:
        candidate.question_order = candidate_order(db, session)
    return len(stale)


def create_candidates(
    db: Session, session: ExamSession, entries: list[dict]
) -> list[ExamCandidate]:
    """
    Add candidates, generating a registration number and access code for each.

    `entries` is [{"full_name": "...", "school_reference": "..."}] -- both
    optional. A school that wants to keep its pupils pseudonymous can add
    candidates with neither, and simply hand out the slips in order.

    The registration number is ALWAYS generated here, never taken from input.
    Accepting the school's own numbering would mean two schools both starting
    at 001, and would let a student guess a classmate's identity from the
    pattern. Their own identifier goes in `school_reference` instead, purely so
    results can be matched back to a class list.

    Question order is shuffled per candidate, but only within each subject --
    see `candidate_order`. Same paper, different sequence, same structure.
    """
    used_codes = {
        c.access_code for c in
        db.query(ExamCandidate).filter(ExamCandidate.session_id == session.id).all()
    }

    made: list[ExamCandidate] = []
    for entry in entries:
        for _ in range(20):
            code = _code(ACCESS_CODE_LENGTH)
            if code not in used_codes:
                break
        used_codes.add(code)

        candidate = ExamCandidate(
            session_id=session.id,
            registration_number=issue_registration_number(db),
            access_code=code,
            full_name=(entry.get("full_name") or "").strip() or None,
            school_reference=(entry.get("school_reference") or "").strip() or None,
            question_order=candidate_order(db, session),
        )
        db.add(candidate)
        made.append(candidate)

    db.flush()
    return made


def subject_availability(db: Session) -> list[dict]:
    """
    How many active bank questions exist per subject.

    Shown while the paper is being planned, so "40 Commerce questions" is
    caught as impossible at the point of typing it rather than on exam day.
    """
    from app.subjects import SUBJECTS

    rows = []
    for subject in SUBJECTS:
        rows.append({
            "subject": subject,
            "available": (
                db.query(Question)
                .filter(Question.status == "active", Question.subject == subject)
                .count()
            ),
        })
    return rows


def readiness(db: Session, session: ExamSession) -> dict:
    """
    Everything that must be true before an exam can be published.

    Returns problems rather than raising, so the review screen can show a
    checklist and the organiser can see exactly what is still missing. Nothing
    is generated -- no link, no codes -- until every one of these passes.
    """
    from app.models import ExamQuestion

    problems: list[str] = []

    if not session.title.strip():
        problems.append("The exam has no title.")
    if not session.organisation.strip():
        problems.append("No school or organisation is set.")
    if session.duration_minutes < 5:
        problems.append("The duration is too short.")
    if session.closes_at <= session.opens_at:
        problems.append("The exam closes before it opens.")

    total_requested = sum(int(e.get("count") or 0) for e in (session.blueprint or []))

    if session.source == "upload":
        uploaded = (
            db.query(ExamQuestion).filter(ExamQuestion.session_id == session.id).count()
        )
        if uploaded == 0:
            problems.append("No questions have been uploaded yet.")
    else:
        if not session.blueprint:
            problems.append("No subjects have been added.")
        if total_requested == 0:
            problems.append("No questions have been requested.")
        for shortfall in blueprint_shortfall(db, session.blueprint or []):
            problems.append(shortfall)

    candidates = (
        db.query(ExamCandidate).filter(ExamCandidate.session_id == session.id).count()
    )
    if candidates == 0:
        problems.append("No candidates have been added yet.")

    questions_ready = (
        db.query(ExamQuestion).filter(ExamQuestion.session_id == session.id).count()
        if session.source == "upload" else total_requested
    )

    return {
        "ready": not problems,
        "problems": problems,
        "candidates": candidates,
        "questions": questions_ready,
        "subjects": len(session.blueprint or []),
        "duration_minutes": session.duration_minutes,
    }


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


def paper_payload(db: Session, session: ExamSession, question_ids: list[int]) -> list[dict]:
    """
    The whole paper in ONE query, in the candidate's own order.

    Was one query per question. Sixty questions times fifty candidates all
    starting within a couple of minutes is three thousand round trips at
    exactly the moment the exam must not be slow, and every one of them holds
    a pooled connection while it waits.

    Correct answers are not selected at all -- not fetched and then dropped,
    simply never read out of the database.
    """
    if not question_ids:
        return []

    model = ExamQuestion if session.source == "upload" else Question
    rows = (
        db.query(
            model.id, model.subject, model.topic, model.question_text,
            model.image_url, model.option_a, model.option_b,
            model.option_c, model.option_d,
        )
        .filter(model.id.in_(question_ids))
        # Uploaded questions belong to one session. Scoping the query means a
        # crafted question_order can never pull another school's paper.
        .filter(ExamQuestion.session_id == session.id if session.source == "upload" else True)
        .all()
    )

    by_id = {
        row[0]: {
            "id": row[0], "subject": row[1], "topic": row[2],
            "question_text": row[3], "image_url": row[4],
            "option_a": row[5], "option_b": row[6],
            "option_c": row[7], "option_d": row[8],
        }
        for row in rows
    }
    # The candidate's order is authoritative, and a question that has since
    # been deleted is skipped rather than rendered as a hole.
    return [by_id[qid] for qid in question_ids if qid in by_id]


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
