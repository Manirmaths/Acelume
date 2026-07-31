from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.achievements import ACHIEVEMENTS
from app.database import get_db
from app.models import User, UserAchievement
from app.schemas import AchievementOut, AchievementsOut

router = APIRouter(prefix="/api/achievements", tags=["achievements"])


@router.get("", response_model=AchievementsOut)
def list_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    earned_rows = db.query(UserAchievement).filter(UserAchievement.user_id == user.id).all()
    earned_at_by_code = {row.code: row.earned_at for row in earned_rows}

    newly_unlocked: list[str] = []
    for a in ACHIEVEMENTS:
        if a.code in earned_at_by_code:
            continue
        if a.is_earned(db, user):
            row = UserAchievement(user_id=user.id, code=a.code, earned_at=datetime.utcnow())
            db.add(row)
            newly_unlocked.append(a.code)
            earned_at_by_code[a.code] = row.earned_at
    if newly_unlocked:
        db.commit()

    items = []
    for a in ACHIEVEMENTS:
        current, target = a.progress(db, user)
        earned = a.code in earned_at_by_code
        items.append(AchievementOut(
            code=a.code,
            title=a.title,
            description=a.description,
            icon=a.icon,
            earned=earned,
            earned_at=earned_at_by_code.get(a.code),
            newly_unlocked=a.code in newly_unlocked,
            # Progress is reported for locked badges so the gallery can show
            # "17/25" rather than a blank padlock -- knowing how close you are
            # is the part that motivates.
            progress=target if earned else current,
            target=target,
        ))
    return AchievementsOut(items=items, newly_unlocked=newly_unlocked)
