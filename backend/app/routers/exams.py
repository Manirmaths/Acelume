"""
Exam sessions: the candidate flow and the organiser's controls.

The candidate endpoints are the unusual part of this codebase -- they are the
only ones that serve someone with **no account**. A student arrives with a
link, a registration number and an access code, and that pair IS the
credential. There is no signup, no email, no password.

That is not a shortcut. Fifty students registering inside a fifty-minute exam
slot would eat a quarter of the paper, a third of them have no email address,
and every account created would be personal data collected from a minor for no
reason. A registration number the school already holds is strictly less data
and strictly more usable.

Everything under /manage requires an admin. For now the organiser IS Acelume:
you create the session, upload their questions and hand the school a sheet of
codes. Concierge on purpose -- five exams run by hand will teach more about
what schools need than any guessed-at self-serve dashboard.
"""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import exam_import, exams
from app.auth import require_admin
from app.database import get_db
from app.models import ExamCandidate, ExamQuestion, ExamSession, User
from app.schemas import (
    ExamCandidateOut, ExamCreateIn, ExamPaperOut, ExamQuestionOut,
    ExamResultsOut, ExamSessionOut, ExamStartIn, ExamSubmitAnswerIn,
    ImportReportOut, CandidateResultOut, QuestionStatOut,
)

router = APIRouter(prefix="/api/exams", tags=["exams"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


# ------------------------------------------------------------------------
# Candidate flow -- no account required
# ------------------------------------------------------------------------

def _authenticate(db: Session, code: str, registration: str, access_code: str):
    """
    The credential is (session code, registration number, access code).

    Errors are deliberately vague about WHICH part was wrong: telling someone
    "that registration number exists but the code is wrong" hands them half a
    login.
    """
    session = db.query(ExamSession).filter(ExamSession.code == code.upper().strip()).first()
    if session is None:
        raise HTTPException(status_code=404, detail="No exam found with that code.")

    candidate = (
        db.query(ExamCandidate)
        .filter(
            ExamCandidate.session_id == session.id,
            ExamCandidate.registration_number == registration.strip(),
            ExamCandidate.access_code == access_code.upper().strip(),
        )
        .first()
    )
    if candidate is None:
        raise HTTPException(
            status_code=403,
            detail="That registration number and access code do not match. Check your slip.",
        )
    return session, candidate


@router.get("/{code}", response_model=ExamSessionOut)
def exam_details(code: str, db: Session = Depends(get_db)):
    """
    Public front page for an exam, so a candidate can confirm they are in the
    right place before typing anything. Deliberately reveals nothing but the
    title, organisation and timing.
    """
    session = db.query(ExamSession).filter(ExamSession.code == code.upper().strip()).first()
    if session is None or session.status == "draft":
        raise HTTPException(status_code=404, detail="No exam found with that code.")
    return _session_out(db, session, include_counts=False)


@router.post("/{code}/start", response_model=ExamPaperOut)
def start_exam(code: str, payload: ExamStartIn, db: Session = Depends(get_db)):
    """
    Begin, or resume, a paper.

    Resuming matters more than it sounds: phones die, browsers crash, and a
    student who loses their session must get back into the SAME paper with the
    clock still running -- not a fresh one, and not a locked door.
    """
    session, candidate = _authenticate(db, code, payload.registration_number, payload.access_code)

    if candidate.submitted_at is not None:
        raise HTTPException(status_code=409, detail="You have already submitted this exam.")
    if not exams.is_open(session):
        raise HTTPException(
            status_code=403,
            detail="This exam is not open right now. Check the time with your teacher.",
        )

    if candidate.started_at is None:
        candidate.started_at = datetime.utcnow()
        db.commit()

    if exams.seconds_remaining(session, candidate) <= 0:
        exams.submit(db, session, candidate)
        db.commit()
        raise HTTPException(status_code=409, detail="Your time for this exam has run out.")

    return _paper(db, session, candidate)


@router.post("/{code}/answer", status_code=204)
def save_answer(code: str, payload: ExamSubmitAnswerIn, db: Session = Depends(get_db)):
    """
    Record one answer.

    Saved individually rather than all at the end, so a phone that dies at
    question 48 does not lose the first 47. Answers can be changed freely until
    submission -- this is a real exam paper, not a quiz.
    """
    session, candidate = _authenticate(db, code, payload.registration_number, payload.access_code)

    if candidate.submitted_at is not None:
        raise HTTPException(status_code=409, detail="You have already submitted this exam.")
    if exams.seconds_remaining(session, candidate) <= 0:
        exams.submit(db, session, candidate)
        db.commit()
        raise HTTPException(status_code=409, detail="Your time for this exam has run out.")
    if payload.question_id not in (candidate.question_order or []):
        raise HTTPException(status_code=400, detail="That question is not in your paper.")

    chosen = (payload.selected_option or "").upper()[:1]
    answers = dict(candidate.answers or {})
    if chosen in ("A", "B", "C", "D"):
        answers[str(payload.question_id)] = chosen
    else:
        answers.pop(str(payload.question_id), None)   # clearing an answer
    candidate.answers = answers
    db.commit()


@router.post("/{code}/submit", response_model=CandidateResultOut)
def submit_exam(code: str, payload: ExamStartIn, db: Session = Depends(get_db)):
    session, candidate = _authenticate(db, code, payload.registration_number, payload.access_code)
    score = exams.submit(db, session, candidate)
    db.commit()

    total = len(candidate.question_order or [])
    return CandidateResultOut(
        registration_number=candidate.registration_number,
        full_name=candidate.full_name,
        score=score,
        total=total,
        percent=round(100 * score / total) if total else 0,
        submitted_at=candidate.submitted_at.isoformat() if candidate.submitted_at else None,
        # Withheld unless the school allows it -- a school running the same
        # paper across two days does not want group one briefing group two.
        answers_shown=session.show_answers,
    )


# ------------------------------------------------------------------------
# Organiser -- admin only
# ------------------------------------------------------------------------

@router.post("/manage/sessions", response_model=ExamSessionOut, status_code=201)
def create_session(
    payload: ExamCreateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if payload.closes_at <= payload.opens_at:
        raise HTTPException(status_code=400, detail="The exam must close after it opens.")

    session = ExamSession(
        code=exams.unique_session_code(db),
        title=payload.title.strip(),
        organisation=payload.organisation.strip(),
        created_by=admin.id,
        blueprint=[b.model_dump() for b in payload.blueprint],
        duration_minutes=payload.duration_minutes,
        source=payload.source,
        opens_at=payload.opens_at,
        closes_at=payload.closes_at,
        show_answers=payload.show_answers,
        status="draft",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_out(db, session)


@router.post("/manage/sessions/{session_id}/questions", response_model=ImportReportOut)
async def upload_questions(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Import a school's spreadsheet.

    Reports EVERY bad row rather than stopping at the first. A teacher who gets
    "upload failed" gives up; one who gets three fixable row numbers fixes them.
    Good rows are imported regardless -- 57 usable questions out of 60 is a
    usable paper.
    """
    session = _require_session(db, session_id)
    if session.status == "closed":
        raise HTTPException(status_code=400, detail="This exam is closed.")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="That file is too large (limit 5MB).")

    default_subject = session.blueprint[0]["subject"] if session.blueprint else None
    report = exam_import.parse_workbook(data, default_subject=default_subject)

    if report.fatal:
        return ImportReportOut(imported=0, errors=[], fatal=report.fatal)

    # Replace rather than append: re-uploading a corrected file is the normal
    # way a teacher fixes mistakes, and appending would silently double the paper.
    db.query(ExamQuestion).filter(ExamQuestion.session_id == session.id).delete()

    for position, row in enumerate(report.questions):
        db.add(ExamQuestion(session_id=session.id, position=position, **row))
    db.flush()

    session.source = "upload"
    session.question_ids = exams.build_paper(db, session)
    db.commit()

    return ImportReportOut(
        imported=len(report.questions),
        errors=[{"row": e.row, "problem": e.problem} for e in report.errors],
        fatal=None,
    )


@router.post("/manage/sessions/{session_id}/candidates", response_model=list[ExamCandidateOut])
def add_candidates(
    session_id: int,
    registrations: list[dict],
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Register candidates and issue access codes.

    This is the ONLY time an access code is returned in full. Print the sheet.
    """
    session = _require_session(db, session_id)

    if not session.question_ids:
        session.question_ids = exams.build_paper(db, session)
        if not session.question_ids:
            raise HTTPException(
                status_code=400,
                detail="Add questions before registering candidates.",
            )

    made = exams.create_candidates(db, session, registrations)
    if session.status == "draft":
        session.status = "ready"
    db.commit()

    return [
        ExamCandidateOut(
            registration_number=c.registration_number,
            full_name=c.full_name,
            access_code=c.access_code,
            started=False, submitted=False, score=None,
        )
        for c in made
    ]


@router.get("/manage/sessions", response_model=list[ExamSessionOut])
def list_sessions(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.query(ExamSession).order_by(ExamSession.id.desc()).limit(100).all()
    return [_session_out(db, s) for s in rows]


@router.get("/manage/sessions/{session_id}/results", response_model=ExamResultsOut)
def results(session_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    session = _require_session(db, session_id)
    exams.auto_submit_expired(db, session)
    db.commit()
    return _results(db, session)


@router.get("/manage/sessions/{session_id}/results.csv")
def results_csv(session_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """
    The deliverable the school actually keeps.

    A spreadsheet is what makes this feel like a product rather than a demo --
    it goes into their records, gets emailed to parents, and is the thing that
    justifies paying for it next term.
    """
    session = _require_session(db, session_id)
    exams.auto_submit_expired(db, session)
    db.commit()

    data = _results(db, session)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Registration number", "Name", "Score", "Total", "Percent", "Status", "Submitted at"])
    for row in data.candidates:
        writer.writerow([
            row.registration_number, row.full_name or "", row.score, row.total,
            f"{row.percent}%", row.status, row.submitted_at or "",
        ])

    buffer.seek(0)
    filename = f"{session.code}-results.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/manage/template.csv")
def question_template(admin: User = Depends(require_admin)):
    """A ready-made template so a school does not have to guess the columns."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in exam_import.template_rows():
        writer.writerow(row)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="acelume-question-template.csv"'},
    )


# ------------------------------------------------------------------------

def _require_session(db: Session, session_id: int) -> ExamSession:
    session = db.get(ExamSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Exam session not found.")
    return session


def _session_out(db: Session, session: ExamSession, include_counts: bool = True) -> ExamSessionOut:
    registered = started = submitted = 0
    if include_counts:
        rows = db.query(ExamCandidate).filter(ExamCandidate.session_id == session.id).all()
        registered = len(rows)
        started = sum(1 for c in rows if c.started_at)
        submitted = sum(1 for c in rows if c.submitted_at)

    return ExamSessionOut(
        id=session.id, code=session.code, title=session.title,
        organisation=session.organisation, duration_minutes=session.duration_minutes,
        source=session.source, status=session.status,
        question_count=len(session.question_ids or []),
        opens_at=session.opens_at.isoformat(), closes_at=session.closes_at.isoformat(),
        show_answers=session.show_answers,
        registered=registered, started=started, submitted=submitted,
        is_open=exams.is_open(session),
    )


def _paper(db: Session, session: ExamSession, candidate: ExamCandidate) -> ExamPaperOut:
    questions = []
    for qid in candidate.question_order or []:
        payload = exams.question_payload(db, session, qid)
        if payload:
            questions.append(ExamQuestionOut(**payload))

    return ExamPaperOut(
        title=session.title,
        organisation=session.organisation,
        registration_number=candidate.registration_number,
        full_name=candidate.full_name,
        seconds_remaining=exams.seconds_remaining(session, candidate),
        questions=questions,
        answers=dict(candidate.answers or {}),
    )


def _results(db: Session, session: ExamSession) -> ExamResultsOut:
    candidates = (
        db.query(ExamCandidate)
        .filter(ExamCandidate.session_id == session.id)
        .order_by(ExamCandidate.registration_number)
        .all()
    )
    key = exams.correct_answers(db, session)
    total_questions = len(session.question_ids or [])

    rows = []
    scores = []
    per_question: dict[int, dict] = {qid: {"correct": 0, "attempted": 0} for qid in key}

    for c in candidates:
        status = "submitted" if c.submitted_at else ("in progress" if c.started_at else "not started")
        if c.submitted_at:
            scores.append(c.score)
        for qid_str, chosen in (c.answers or {}).items():
            try:
                qid = int(qid_str)
            except (TypeError, ValueError):
                continue
            if qid in per_question and chosen:
                per_question[qid]["attempted"] += 1
                if key.get(qid) == chosen:
                    per_question[qid]["correct"] += 1

        rows.append(CandidateResultOut(
            registration_number=c.registration_number,
            full_name=c.full_name,
            score=c.score if c.submitted_at else 0,
            total=total_questions,
            percent=round(100 * c.score / total_questions) if (c.submitted_at and total_questions) else 0,
            submitted_at=c.submitted_at.isoformat() if c.submitted_at else None,
            status=status,
            answers_shown=session.show_answers,
        ))

    # Per-question difficulty is what turns a mark sheet into something a
    # teacher can teach from: it names the questions the class as a whole
    # failed, which is where next week's lesson should go.
    stats = []
    for qid, counts in per_question.items():
        payload = exams.question_payload(db, session, qid)
        if not payload or counts["attempted"] == 0:
            continue
        stats.append(QuestionStatOut(
            question_id=qid,
            question_text=payload["question_text"][:160],
            topic=payload.get("topic"),
            attempted=counts["attempted"],
            correct=counts["correct"],
            percent_correct=round(100 * counts["correct"] / counts["attempted"]),
        ))
    stats.sort(key=lambda s: s.percent_correct)

    return ExamResultsOut(
        session=_session_out(db, session),
        candidates=rows,
        average_percent=(
            round(sum(scores) / len(scores) / total_questions * 100)
            if scores and total_questions else None
        ),
        highest=max(scores) if scores else None,
        lowest=min(scores) if scores else None,
        hardest_questions=stats[:10],
    )
