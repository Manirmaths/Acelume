from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai import generate_lesson_note, suggest_tags
from app.auth import require_admin
from app.database import get_db
from app.models import LessonNote, Question, Passage, User, UserResponse, ReviewQuestion, QuizAttempt, Payment
from app import analytics
from app.schemas import (
    QuestionIn, QuestionOut, AdminStats, PassageOut, AdminUserOut, SuggestTagsIn, SuggestTagsOut,
    LessonNoteOut, NoteGenerateIn, NoteStatusItem, NoteUpdateIn,
    AnalyticsOut, CohortOut, FunnelOut, DailySignupOut,
)
from app.subjects import SUBJECTS

router = APIRouter(prefix="/api/admin", tags=["admin"])

VALID_DIFFICULTY = {"easy", "medium", "hard"}
VALID_SOURCE = {"original", "past-question", "licensed"}
VALID_STATUS = {"active", "draft"}


def _norm_enum(value: str, valid: set, field: str) -> str:
    v = (value or "").strip().lower()
    if v not in valid:
        raise HTTPException(status_code=400, detail=f"{field} must be one of: {', '.join(sorted(valid))}.")
    return v


def _validate_passage(db: Session, passage_id):
    pid = (passage_id or "").strip() or None
    if pid and not db.query(Passage).filter(Passage.passage_id == pid).first():
        raise HTTPException(status_code=400, detail=f"passage_id '{pid}' does not exist. Create the passage first.")
    return pid


@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return AdminStats(
        total_questions=db.query(Question).count(),
        total_users=db.query(User).count(),
        subjects=SUBJECTS,
    )


@router.get("/analytics", response_model=AnalyticsOut)
def analytics_view(
    weeks: int = 8,
    days: int = 30,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Cohort retention and the signup funnel.

    Exists to answer one question: after a teacher introduces the app and then
    stops mentioning it, do those students come back on their own? Totals
    cannot answer that -- they only ever go up. See app/analytics.py.
    """
    weeks = max(1, min(weeks, 52))
    days = max(1, min(days, 180))

    rows = analytics.cohorts(db, weeks=weeks)
    head = analytics.headline(db)
    f = analytics.funnel(db, days=days)

    return AnalyticsOut(
        week_two_return_pct=head["week_two_return_pct"],
        cohorts_measured=head["cohorts_measured"],
        students_measured=head["students_measured"],
        time_to_value_target_seconds=analytics.TIME_TO_VALUE_TARGET_SECONDS,
        cohorts=[
            CohortOut(
                week_start=c.week_start, signups=c.signups, activated=c.activated,
                d1=c.retention.get(1), d7=c.retention.get(7), d14=c.retention.get(14),
            )
            for c in rows
        ],
        funnel=FunnelOut(**vars(f)),
        daily=[DailySignupOut(**d) for d in analytics.daily_signups(db, days=days)],
    )


@router.get("/questions", response_model=list[QuestionOut])
def list_questions(
    subject: str = None, page: int = 1, per_page: int = 25,
    db: Session = Depends(get_db), _admin: User = Depends(require_admin),
):
    q = db.query(Question)
    if subject and subject in SUBJECTS:
        q = q.filter(Question.subject == subject)
    return (
        q.order_by(Question.id.desc())
        .offset((max(page, 1) - 1) * per_page)
        .limit(per_page)
        .all()
    )


def _normalize_correct(value: str) -> str:
    v = (value or "A").strip().upper()[:1]
    return v if v in ("A", "B", "C", "D") else "A"


@router.post("/questions", response_model=QuestionOut, status_code=201)
def create_question(payload: QuestionIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    qid = payload.question_id.strip()
    if db.query(Question).filter(Question.question_id == qid).first():
        raise HTTPException(status_code=400, detail=f"question_id '{qid}' is already in use.")

    q = Question(
        question_id=qid,
        subject=payload.subject.strip(),
        topic=payload.topic.strip(),
        subtopic=(payload.subtopic or "").strip() or None,
        difficulty=_norm_enum(payload.difficulty, VALID_DIFFICULTY, "difficulty"),
        exam_type=(payload.exam_type or "").strip() or None,
        year=(payload.year or "").strip() or None,
        passage_id=_validate_passage(db, payload.passage_id),
        question_text=payload.question_text.strip(),
        image_url=(payload.image_url or "").strip() or None,
        option_a=payload.option_a.strip(),
        option_b=payload.option_b.strip(),
        option_c=payload.option_c.strip(),
        option_d=payload.option_d.strip(),
        correct_option=_normalize_correct(payload.correct_option),
        explanation=(payload.explanation or "").strip(),
        tags=(payload.tags or "").strip() or None,
        source=_norm_enum(payload.source, VALID_SOURCE, "source"),
        status=_norm_enum(payload.status, VALID_STATUS, "status"),
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.put("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, payload: QuestionIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")

    qid = payload.question_id.strip()
    dupe = db.query(Question).filter(Question.question_id == qid, Question.id != question_id).first()
    if dupe:
        raise HTTPException(status_code=400, detail=f"question_id '{qid}' is already in use.")

    q.question_id = qid
    q.subject = payload.subject.strip()
    q.topic = payload.topic.strip()
    q.subtopic = (payload.subtopic or "").strip() or None
    q.difficulty = _norm_enum(payload.difficulty, VALID_DIFFICULTY, "difficulty")
    q.exam_type = (payload.exam_type or "").strip() or None
    q.year = (payload.year or "").strip() or None
    q.passage_id = _validate_passage(db, payload.passage_id)
    q.question_text = payload.question_text.strip()
    q.image_url = (payload.image_url or "").strip() or None
    q.option_a = payload.option_a.strip()
    q.option_b = payload.option_b.strip()
    q.option_c = payload.option_c.strip()
    q.option_d = payload.option_d.strip()
    q.correct_option = _normalize_correct(payload.correct_option)
    q.explanation = (payload.explanation or "").strip()
    q.tags = (payload.tags or "").strip() or None
    q.source = _norm_enum(payload.source, VALID_SOURCE, "source")
    q.status = _norm_enum(payload.status, VALID_STATUS, "status")
    db.commit()
    db.refresh(q)
    return q


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found.")
    db.delete(q)
    db.commit()
    return {"status": "deleted"}


@router.post("/suggest-tags", response_model=SuggestTagsOut)
def suggest_tags_endpoint(payload: SuggestTagsIn, _admin: User = Depends(require_admin)):
    """
    AI-assisted tagging: suggests subject/topic/subtopic/difficulty for a new
    question via OpenAI (see app/ai.py). Suggestions only -- the admin form
    fills them in as editable fields, nothing is saved until the admin
    reviews and submits normally. Falls back to nulls + an explanatory note
    if OPENAI_API_KEY isn't configured.
    """
    result = suggest_tags(
        question_text=payload.question_text,
        options={
            "A": payload.option_a, "B": payload.option_b,
            "C": payload.option_c, "D": payload.option_d,
        },
        correct_option=payload.correct_option,
        subjects=SUBJECTS,
    )
    return SuggestTagsOut(**result)


@router.get("/passages", response_model=list[PassageOut])
def list_passages(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return db.query(Passage).order_by(Passage.id.desc()).all()


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return db.query(User).order_by(User.points.desc(), User.id.asc()).all()


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You can't delete your own account from here.")

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    # Clear dependent rows first -- Postgres enforces the FK constraints,
    # so a bare delete on "user" would fail while these still reference it.
    db.query(UserResponse).filter(UserResponse.user_id == user_id).delete()
    db.query(ReviewQuestion).filter(ReviewQuestion.user_id == user_id).delete()
    db.query(QuizAttempt).filter(QuizAttempt.user_id == user_id).delete()
    db.query(Payment).filter(Payment.user_id == user_id).delete()
    db.delete(target)
    db.commit()
    return {"status": "deleted"}


@router.post("/users/{user_id}/toggle-admin", response_model=AdminUserOut)
def toggle_admin(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You can't change your own admin status from here.")

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    target.is_admin = not target.is_admin
    db.commit()
    db.refresh(target)
    return target


# ---------- Lesson notes ----------
SAMPLE_QUESTIONS_PER_NOTE = 5


def _admin_note_out(note: LessonNote) -> LessonNoteOut:
    return LessonNoteOut(
        id=note.id, subject=note.subject, topic=note.topic, title=note.title, summary=note.summary,
        glossary=note.glossary, content_md=note.content_md, related_topics=note.related_topics,
        status=note.status, helpful_count=note.helpful_count, unhelpful_count=note.unhelpful_count,
        updated_at=note.updated_at, is_read=False, my_feedback=None,
    )


@router.get("/notes/status", response_model=list[NoteStatusItem])
def notes_status(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    topic_rows = (
        db.query(Question.subject, Question.topic, func.count(Question.id))
        .filter(Question.subject.in_(SUBJECTS))
        .group_by(Question.subject, Question.topic)
        .all()
    )
    notes_by_key = {(n.subject, n.topic): n for n in db.query(LessonNote).all()}

    items = []
    for subj, topic, count in topic_rows:
        note = notes_by_key.get((subj, topic))
        items.append(NoteStatusItem(
            subject=subj, topic=topic, note_id=note.id if note else None,
            status=note.status if note else "missing", question_count=count,
        ))
    items.sort(key=lambda i: (SUBJECTS.index(i.subject) if i.subject in SUBJECTS else 99, i.topic))
    return items


@router.post("/notes/publish-all")
def publish_all_notes(subject: str | None = None, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    if subject and subject not in SUBJECTS:
        raise HTTPException(status_code=404, detail="Unknown subject.")

    q = db.query(LessonNote).filter(LessonNote.status == "draft")
    if subject:
        q = q.filter(LessonNote.subject == subject)
    drafts = q.all()
    for note in drafts:
        note.status = "active"
    db.commit()
    return {"published": len(drafts)}


@router.get("/notes/{subject}/{topic}", response_model=LessonNoteOut)
def admin_get_note(subject: str, topic: str, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    note = db.query(LessonNote).filter(LessonNote.subject == subject, LessonNote.topic == topic).first()
    if not note:
        raise HTTPException(status_code=404, detail="No note exists yet for this topic -- generate one first.")
    return _admin_note_out(note)


@router.post("/notes/generate", response_model=LessonNoteOut)
def generate_note(payload: NoteGenerateIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    if payload.subject not in SUBJECTS:
        raise HTTPException(status_code=404, detail="Unknown subject.")

    existing = (
        db.query(LessonNote)
        .filter(LessonNote.subject == payload.subject, LessonNote.topic == payload.topic)
        .first()
    )
    if existing and existing.status == "active" and not payload.force:
        raise HTTPException(
            status_code=400,
            detail="This note is already published. Pass force=true to regenerate and overwrite it.",
        )

    # Ground generation in a handful of real questions from this topic --
    # prefer ones with an explanation already written, since those tend to
    # be the most complete/reviewed rows in the bank.
    pool = (
        db.query(Question)
        .filter(Question.subject == payload.subject, Question.topic == payload.topic)
        .order_by(Question.explanation.isnot(None).desc(), func.random())
        .limit(SAMPLE_QUESTIONS_PER_NOTE)
        .all()
    )
    sample_questions = [{"question_text": q.question_text, "subtopic": q.subtopic} for q in pool]

    result = generate_lesson_note(subject=payload.subject, topic=payload.topic, sample_questions=sample_questions)

    if existing:
        existing.title = result["title"]
        existing.summary = result["summary"]
        existing.glossary = result["glossary"]
        existing.content_md = result["content_md"]
        existing.related_topics = result["related_topics"]
        existing.status = "draft"
        note = existing
    else:
        note = LessonNote(
            subject=payload.subject, topic=payload.topic, title=result["title"], summary=result["summary"],
            glossary=result["glossary"], content_md=result["content_md"], related_topics=result["related_topics"],
            status="draft",
        )
        db.add(note)
    db.commit()
    db.refresh(note)
    return _admin_note_out(note)


@router.put("/notes/{note_id}", response_model=LessonNoteOut)
def update_note(note_id: int, payload: NoteUpdateIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    note = db.get(LessonNote, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found.")

    if payload.title is not None:
        note.title = payload.title.strip() or note.title
    if payload.summary is not None:
        note.summary = payload.summary.strip() or None
    if payload.glossary is not None:
        note.glossary = [g.model_dump() for g in payload.glossary]
    if payload.content_md is not None:
        note.content_md = payload.content_md
    if payload.related_topics is not None:
        note.related_topics = payload.related_topics
    if payload.status is not None:
        if payload.status not in ("draft", "active"):
            raise HTTPException(status_code=400, detail="status must be 'draft' or 'active'.")
        note.status = payload.status

    db.commit()
    db.refresh(note)
    return _admin_note_out(note)
