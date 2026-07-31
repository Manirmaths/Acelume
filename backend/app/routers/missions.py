"""Daily missions endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.gamification import config, missions as missions_service
from app.models import DailyReward, User
from app.schemas import DailyMissionOut, DailyMissionsOut

router = APIRouter(prefix="/api/missions", tags=["missions"])


@router.get("", response_model=DailyMissionsOut)
def get_missions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = user.local_today()
    rows = missions_service.generate_for_day(db, user, today)
    db.commit()

    claimed = (
        db.query(DailyReward)
        .filter(DailyReward.user_id == user.id, DailyReward.local_date == today)
        .first()
    )

    items = [
        DailyMissionOut(
            kind=m.kind,
            title=m.title,
            subject=m.subject,
            topic=m.topic,
            target=m.target,
            progress=m.progress,
            completed=m.completed_at is not None,
            estimated_minutes=m.estimated_minutes,
            action_path=m.action_path,
        )
        for m in rows
    ]

    return DailyMissionsOut(
        local_date=today.isoformat(),
        items=items,
        all_complete=bool(items) and all(i.completed for i in items),
        # Disclosed BEFORE completion, never randomised. The spec rules out
        # gambling-style mechanics, so the student always knows what the
        # chest holds.
        reward_xp=config.get(db, "xp_all_missions"),
        reward_claimed=claimed is not None,
        total_minutes=sum(i.estimated_minutes for i in items),
    )
