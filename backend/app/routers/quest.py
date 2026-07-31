"""
Quest Map: the per-subject learning journey.

Returns every topic in a subject with its state, stars and mastery, so the
client can render the map without computing anything itself. All state is
decided here -- the spec is explicit that the app must not be able to award
stars locally.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.gamification import config, events
from app.models import SyllabusTopic, TopicMastery, User
from app.schemas import QuestMapOut, QuestTopicOut
from app.subjects import SUBJECTS

router = APIRouter(prefix="/api/quest", tags=["quest"])


@router.get("/{subject}", response_model=QuestMapOut)
def quest_map(subject: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if subject not in SUBJECTS:
        raise HTTPException(status_code=404, detail="Unknown subject.")

    topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.subject == subject, SyllabusTopic.active.is_(True))
        .order_by(SyllabusTopic.order_index.asc(), SyllabusTopic.topic.asc())
        .all()
    )
    if not topics:
        raise HTTPException(
            status_code=404,
            detail="No syllabus is configured for this subject yet.",
        )

    mastery = {
        (m.subject, m.topic): m
        for m in db.query(TopicMastery).filter(
            TopicMastery.user_id == user.id, TopicMastery.subject == subject
        )
    }

    now = datetime.utcnow()
    by_id = {t.id: t for t in topics}
    settings = config.get_all(db)

    # First pass: resolve each topic's own state from stored evidence.
    states: dict[int, str] = {}
    rows: dict[int, TopicMastery | None] = {}
    for t in topics:
        row = mastery.get((subject, t.topic))
        rows[t.id] = row
        if row is None:
            states[t.id] = "available"
        else:
            states[t.id] = events.refresh_state(db, row, now)

    # Second pass: apply locking. A topic is locked when its prerequisite has
    # not yet reached proficiency. Done after the first pass so a prerequisite's
    # own state is already known.
    out: list[QuestTopicOut] = []
    for t in topics:
        state = states[t.id]
        prereq = by_id.get(t.prerequisite_id) if t.prerequisite_id else None
        prereq_met = True
        if prereq is not None:
            prereq_state = states.get(prereq.id, "available")
            prereq_met = prereq_state in ("proficient", "mastered", "review_due")

        # Never re-lock a topic the student has already engaged with: losing
        # access to work already begun would be punitive, and "review_due"
        # must stay reachable.
        if not prereq_met and state == "available":
            state = "locked"

        row = rows[t.id]
        out.append(
            QuestTopicOut(
                topic=t.topic,
                description=t.description,
                estimated_minutes=t.estimated_minutes,
                state=state,
                stars=row.stars if row else 0,
                mastery_score=row.mastery_score if row else 0,
                prerequisite=prereq.topic if prereq else None,
                # Test Out: offered on a locked topic so an experienced student
                # is never permanently blocked (spec section 1, step 5).
                can_test_out=(state == "locked"),
                next_review_at=row.next_review_at.isoformat() if row and row.next_review_at else None,
            )
        )

    mastered = sum(1 for t in out if t.state == "mastered")
    review_due = sum(1 for t in out if t.state == "review_due")

    # Recommend the first thing that actually needs attention: overdue review
    # first (retention decays), then work already started, then the next
    # unlocked topic.
    recommended = None
    for wanted in ("review_due", "practising", "learning", "proficient", "available"):
        match = next((t for t in out if t.state == wanted), None)
        if match:
            recommended = match.topic
            break

    return QuestMapOut(
        subject=subject,
        total_topics=len(out),
        mastered_topics=mastered,
        review_due_topics=review_due,
        percent_complete=round(100 * mastered / len(out)) if out else 0,
        recommended_topic=recommended,
        practice_pass_pct=settings["practice_pass_pct"],
        challenge_pass_pct=settings["challenge_pass_pct"],
        topics=out,
    )
