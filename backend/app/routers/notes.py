from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai import ask_note_tutor
from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.gamification import events, missions
from app.models import LessonNote, NoteFeedback, NoteProgress, NoteTutorQuery, Question, TutorQuery, User
from app.schemas import (
    LearnHubOut, LearnSubjectProgress, LessonNoteOut, NoteFeedbackIn, NoteTutorAskIn, NoteTutorAskOut,
)
from app.subjects import SUBJECTS

router = APIRouter(prefix="/api/notes", tags=["notes"])


def _get_active_note(db: Session, subject: str, topic: str) -> LessonNote:
    note = (
        db.query(LessonNote)
        .filter(LessonNote.subject == subject, LessonNote.topic == topic, LessonNote.status == "active")
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="No lesson note published for this topic yet.")
    return note


def _note_out(db: Session, note: LessonNote, user: User) -> LessonNoteOut:
    read = (
        db.query(NoteProgress)
        .filter(NoteProgress.user_id == user.id, NoteProgress.note_id == note.id)
        .first()
    )
    fb = (
        db.query(NoteFeedback)
        .filter(NoteFeedback.user_id == user.id, NoteFeedback.note_id == note.id)
        .first()
    )
    return LessonNoteOut(
        id=note.id, subject=note.subject, topic=note.topic, title=note.title, summary=note.summary,
        glossary=note.glossary, content_md=note.content_md, related_topics=note.related_topics,
        status=note.status, helpful_count=note.helpful_count, unhelpful_count=note.unhelpful_count,
        updated_at=note.updated_at, is_read=bool(read), my_feedback=(fb.is_helpful if fb else None),
    )


@router.get("/learn-hub", response_model=LearnHubOut)
def learn_hub(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Total topics per subject, from the live question bank (same source of
    # truth as /api/subjects/{subject}/topics) -- not the note table, so a
    # subject with zero notes yet still shows "0 / 10 read" rather than
    # vanishing from the hub entirely.
    topic_rows = (
        db.query(Question.subject, Question.topic)
        .filter(Question.subject.in_(SUBJECTS))
        .distinct()
        .all()
    )
    total_by_subject: dict[str, int] = {}
    for subj, _topic in topic_rows:
        total_by_subject[subj] = total_by_subject.get(subj, 0) + 1

    read_note_ids = {
        row[0] for row in db.query(NoteProgress.note_id).filter(NoteProgress.user_id == user.id).all()
    }
    read_by_subject: dict[str, int] = {}
    if read_note_ids:
        read_notes = db.query(LessonNote.subject).filter(LessonNote.id.in_(read_note_ids)).all()
        for (subj,) in read_notes:
            read_by_subject[subj] = read_by_subject.get(subj, 0) + 1

    subjects_out = []
    for s in SUBJECTS:
        total = total_by_subject.get(s, 0)
        read = min(read_by_subject.get(s, 0), total)
        pct = round((read / total) * 100, 1) if total else 0.0
        subjects_out.append(LearnSubjectProgress(subject=s, total_topics=total, read_topics=read, percentage=pct))

    return LearnHubOut(subjects=subjects_out)


@router.get("/{subject}/{topic}", response_model=LessonNoteOut)
def get_note(subject: str, topic: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    note = _get_active_note(db, subject, topic)
    return _note_out(db, note, user)


@router.post("/{subject}/{topic}/read", response_model=LessonNoteOut)
def mark_read(subject: str, topic: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    note = _get_active_note(db, subject, topic)
    existing = (
        db.query(NoteProgress)
        .filter(NoteProgress.user_id == user.id, NoteProgress.note_id == note.id)
        .first()
    )
    if not existing:
        db.add(NoteProgress(user_id=user.id, note_id=note.id))
        # First star on the Quest Map: the Learn stage is complete. Keyed on
        # subject/topic rather than the note id so re-reading, or an admin
        # replacing the note, cannot re-award it.
        row = events.get_or_create_topic(db, user.id, note.subject, note.topic)
        if row.lesson_completed_at is None:
            row.lesson_completed_at = datetime.utcnow()
            row.stars = max(row.stars, 1)
            events.refresh_state(db, row)
        events.record(
            db, user=user, event_type=events.LESSON_COMPLETED,
            event_key=f"{events.LESSON_COMPLETED}:{note.subject}:{note.topic}",
            subject=note.subject, topic=note.topic, source_id=str(note.id),
        )
        # A lesson satisfies either the progress mission or the improvement
        # mission, depending on which the generator issued today.
        missions.advance(db, user, kind=missions.PROGRESS, subject=note.subject)
        missions.advance(db, user, kind=missions.IMPROVEMENT, subject=note.subject)
        missions.try_award_daily_chest(db, user)
        db.commit()
    return _note_out(db, note, user)


@router.post("/{subject}/{topic}/feedback", response_model=LessonNoteOut)
def submit_feedback(
    subject: str, topic: str, payload: NoteFeedbackIn,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    note = _get_active_note(db, subject, topic)
    existing = (
        db.query(NoteFeedback)
        .filter(NoteFeedback.user_id == user.id, NoteFeedback.note_id == note.id)
        .first()
    )
    if existing:
        if existing.is_helpful != payload.is_helpful:
            if existing.is_helpful:
                note.helpful_count = max(0, note.helpful_count - 1)
                note.unhelpful_count += 1
            else:
                note.unhelpful_count = max(0, note.unhelpful_count - 1)
                note.helpful_count += 1
            existing.is_helpful = payload.is_helpful
    else:
        db.add(NoteFeedback(user_id=user.id, note_id=note.id, is_helpful=payload.is_helpful))
        if payload.is_helpful:
            note.helpful_count += 1
        else:
            note.unhelpful_count += 1
    db.commit()
    db.refresh(note)
    return _note_out(db, note, user)


@router.post("/{subject}/{topic}/tutor", response_model=NoteTutorAskOut)
def ask_tutor_about_note(
    subject: str, topic: str, payload: NoteTutorAskIn,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    note = _get_active_note(db, subject, topic)

    # Shared daily cap with the per-question tutor (routers/tutor.py) -- one
    # combined "AI tutor questions per day" budget, so switching between
    # explaining a question vs. explaining a topic can't be used to double
    # a student's real quota.
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    used_today = (
        db.query(TutorQuery).filter(TutorQuery.user_id == user.id, TutorQuery.created_at >= today_start).count()
        + db.query(NoteTutorQuery).filter(NoteTutorQuery.user_id == user.id, NoteTutorQuery.created_at >= today_start).count()
    )
    if used_today >= settings.TUTOR_DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"You've used all {settings.TUTOR_DAILY_LIMIT} AI tutor questions for today -- try again tomorrow.",
        )

    reply = ask_note_tutor(
        subject=subject, topic=topic, note_excerpt=note.content_md, user_message=payload.message,
    )

    db.add(NoteTutorQuery(user_id=user.id, subject=subject, topic=topic))
    db.commit()

    return NoteTutorAskOut(reply=reply, queries_remaining_today=max(0, settings.TUTOR_DAILY_LIMIT - used_today - 1))
