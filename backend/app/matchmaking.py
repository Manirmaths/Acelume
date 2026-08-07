"""
Finding someone to play, without a social graph.

The reason chess.com works for a person with no friends on it is that pressing
"Play" produces an opponent immediately. No search, no friend requests, no
waiting for someone you know to sign up. Acelume now has ratings, so the same
thing is possible here — and it is a much better answer to "challenges are hard
to start" than a friends list would be.

Two deliberate constraints shape this, and both come from the users being
minors:

  - **No discovery of specific people.** You cannot search for a student, and
    you cannot choose your opponent. The system pairs you. That removes the
    channel where an adult finds and contacts a particular child, which is the
    thing a username search would create.

  - **A pairing exposes a username and a score. Nothing else.** Battles have
    no chat by design, so there is no message surface at all.

The third rule is a product one: **nobody ever waits.** If there is no
comparable human waiting, the student gets a calibrated bot rather than an
empty queue. A matchmaking screen that spins is worse than no matchmaking
screen, because it converts a working feature into a broken-looking one.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import rating as glicko
from app.models import Battle, BattleParticipant, SubjectRating, User

# Rating window for a fair pairing. Widened in steps rather than searched at
# one fixed width: a tight match is better, but no match at all is worst.
MATCH_BANDS = (100.0, 250.0, 600.0)

# An open challenge older than this is stale -- whoever created it has moved
# on, and joining it produces a battle nobody is waiting for.
OPEN_BATTLE_FRESHNESS_MINUTES = 45

# Don't re-pair the same two students immediately. Matchmaking should widen a
# student's world, not lock them into a duel with one person.
REMATCH_COOLDOWN_HOURS = 6


def rating_for(db: Session, user_id: int, subject: str) -> float:
    row = (
        db.query(SubjectRating)
        .filter(SubjectRating.user_id == user_id, SubjectRating.subject == subject)
        .first()
    )
    return row.rating if row else glicko.DEFAULT_RATING


def _recent_opponent_ids(db: Session, user_id: int, hours: int) -> set[int]:
    since = datetime.utcnow() - timedelta(hours=hours)
    my_battles = [
        bid for (bid,) in
        db.query(BattleParticipant.battle_id)
        .join(Battle, Battle.id == BattleParticipant.battle_id)
        .filter(BattleParticipant.user_id == user_id, Battle.created_at >= since)
        .all()
    ]
    if not my_battles:
        return set()
    return {
        uid for (uid,) in
        db.query(BattleParticipant.user_id)
        .filter(
            BattleParticipant.battle_id.in_(my_battles),
            BattleParticipant.user_id != user_id,
        )
        .all()
    }


def find_open_battle(db: Session, user: User, subject: str, questions: int, mode: str) -> Battle | None:
    """
    An open challenge from a student of comparable strength.

    Searches outward through MATCH_BANDS: a close match first, then looser,
    rather than either insisting on a perfect pairing or accepting any warm
    body straight away.

    Returns None when nothing suitable is waiting. The caller then gives the
    student a bot -- see the module docstring on why nobody waits.
    """
    fresh_since = datetime.utcnow() - timedelta(minutes=OPEN_BATTLE_FRESHNESS_MINUTES)

    candidates = (
        db.query(Battle)
        .filter(
            Battle.status == "open",
            Battle.subject == subject,
            Battle.mode == mode,
            Battle.bot_key.is_(None),          # never "match" someone into a bot game
            Battle.created_by != user.id,      # nor into your own
            Battle.expires_at > datetime.utcnow(),
            Battle.created_at >= fresh_since,
        )
        .order_by(Battle.created_at.desc())
        .limit(60)
        .all()
    )
    if not candidates:
        return None

    # A battle someone else already joined is full.
    open_only = []
    for b in candidates:
        if len(b.question_ids or []) != questions:
            continue
        players = db.query(BattleParticipant).filter(BattleParticipant.battle_id == b.id).count()
        if players < 2:
            open_only.append(b)
    if not open_only:
        return None

    avoid = _recent_opponent_ids(db, user.id, REMATCH_COOLDOWN_HOURS)
    open_only = [b for b in open_only if b.created_by not in avoid] or open_only

    mine = rating_for(db, user.id, subject)
    scored = [(abs(rating_for(db, b.created_by, subject) - mine), b) for b in open_only]
    scored.sort(key=lambda pair: pair[0])

    for band in MATCH_BANDS:
        for gap, battle in scored:
            if gap <= band:
                return battle
    return None


def recent_opponents(db: Session, user_id: int, limit: int = 8) -> list[dict]:
    """
    People this student has already played, most recent first.

    This is the safe half of a friends list. There is no search and no
    friend request -- the connection exists because both students already
    agreed to a battle, so it creates no channel for unsolicited contact
    between an adult and a child.

    Bot battles are excluded: a bot is not someone you played, and offering a
    rematch with one under "recent opponents" would blur the honesty line the
    whole bot design rests on.
    """
    my_rows = (
        db.query(BattleParticipant.battle_id)
        .join(Battle, Battle.id == BattleParticipant.battle_id)
        .filter(BattleParticipant.user_id == user_id, Battle.bot_key.is_(None))
        .order_by(BattleParticipant.battle_id.desc())
        .limit(120)
        .all()
    )
    battle_ids = [bid for (bid,) in my_rows]
    if not battle_ids:
        return []

    rows = (
        db.query(BattleParticipant, Battle)
        .join(Battle, Battle.id == BattleParticipant.battle_id)
        .filter(
            BattleParticipant.battle_id.in_(battle_ids),
            BattleParticipant.user_id != user_id,
        )
        .order_by(Battle.created_at.desc())
        .all()
    )

    seen: dict[int, dict] = {}
    for part, battle in rows:
        if part.user_id in seen:
            seen[part.user_id]["played"] += 1
            continue
        opponent = db.get(User, part.user_id)
        if opponent is None:
            continue
        seen[part.user_id] = {
            "user_id": opponent.id,
            "username": opponent.username,
            "subject": battle.subject,
            "last_played": battle.created_at.isoformat() if battle.created_at else None,
            "played": 1,
        }
        if len(seen) >= limit:
            break

    return list(seen.values())
