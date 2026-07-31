"""
Admin-configurable gamification thresholds and reward values.

Every number the spec calls "suggested" lives here, not scattered through the
feature code. Values are read from the `gamification_setting` table when
present and fall back to the defaults below, so an empty table behaves exactly
like hard-coded constants -- there is no migration step needed to start using
this, and no way for a missing row to zero out a reward.

Why this matters more than usual for Acelume: the Android app is a WebView
shell around the live site, so a student may be running an old release for
weeks. Tuning a threshold must never require an app update.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import GamificationSetting

# ---------------------------------------------------------------------------
# XP awards (spec section 3). XP measures participation and NEVER decreases.
# ---------------------------------------------------------------------------
DEFAULTS: dict[str, int] = {
    "xp_lesson_completed": 20,
    # The spec suggests 2, but this app already awarded 10 points per correct
    # answer before the ledger existed, and User.daily_goal (default 50), the
    # dashboard XP ring and the points leaderboard are all calibrated to that.
    # Keeping 10 means introducing the ledger changes nothing for existing
    # students; retuning to the spec's economy is a settings change plus a
    # matching daily_goal migration, not a code change.
    "xp_correct_answer": 10,
    "xp_mistake_corrected": 5,
    "xp_review_passed": 25,
    "xp_topic_proficient": 30,
    "xp_topic_mastered": 50,
    "xp_mock_completed": 100,
    "xp_all_missions": 40,

    # Anti-farming: a ceiling on XP from repetitive answer-level activity in a
    # single day. Lesson/mastery/mock XP is deliberately exempt -- those are
    # inherently rate-limited by the work involved.
    "xp_daily_answer_cap": 300,

    # ---- Mastery thresholds (spec sections 1 and 3) ----
    # Practice stage: at least this many unique questions, at this accuracy,
    # earns the second star (proficient).
    "practice_min_questions": 10,
    "practice_pass_pct": 70,
    # Mastery challenge: timed, no hints, at least this many questions.
    "challenge_min_questions": 15,
    "challenge_pass_pct": 85,

    # ---- Topic-level spaced review (spec section 1, step 6) ----
    "review_interval_1_days": 3,
    "review_interval_2_days": 7,
    "review_interval_3_days": 21,
    "review_interval_4_days": 45,

    # ---- Mastery Points for weekly leagues (spec section 4) ----
    # Deliberately separate from XP so league position reflects the week's
    # learning quality rather than lifetime accumulation.
    "mp_correct_answer": 1,
    "mp_hard_bonus": 1,
    "mp_mistake_corrected": 3,
    "mp_review_passed": 8,
    "mp_topic_proficient": 15,
    "mp_topic_mastered": 25,
    "mp_personal_best": 15,
    "mp_mock_completed": 20,
    "mp_daily_cap": 200,

    # ---- Levels (spec section 3): xp_for_next = base + step * (level - 1) ----
    "level_base_xp": 100,
    "level_step_xp": 25,

    # ---- Streaks (spec section 6) ----
    "streak_min_questions": 10,
    "mastery_streak_pct": 70,
    "streak_shields_per_week": 1,

    # ---- Daily missions (spec section 2) ----
    "missions_per_day": 3,
}


def get(db: Session, key: str) -> int:
    """Read one setting, falling back to the documented default."""
    if key not in DEFAULTS:
        raise KeyError(f"Unknown gamification setting: {key}")
    row = db.query(GamificationSetting).filter(GamificationSetting.key == key).first()
    return row.value if row is not None else DEFAULTS[key]


def get_all(db: Session) -> dict[str, int]:
    """All settings, defaults merged with any admin overrides."""
    values = dict(DEFAULTS)
    for row in db.query(GamificationSetting).all():
        if row.key in values:
            values[row.key] = row.value
    return values


def set_value(db: Session, key: str, value: int, description: str | None = None) -> None:
    """Upsert an override. Rejects unknown keys so a typo can't silently
    create a setting nothing reads."""
    if key not in DEFAULTS:
        raise KeyError(f"Unknown gamification setting: {key}")
    row = db.query(GamificationSetting).filter(GamificationSetting.key == key).first()
    if row is None:
        row = GamificationSetting(key=key, value=value, description=description)
        db.add(row)
    else:
        row.value = value
        if description:
            row.description = description


def xp_for_level(level: int, base: int, step: int) -> int:
    """XP needed to advance FROM `level` to the next one."""
    return base + step * (max(1, level) - 1)


def level_for_xp(total_xp: int, base: int, step: int) -> tuple[int, int, int]:
    """
    Resolve a lifetime XP total into (level, xp_into_level, xp_needed_for_next).

    Walks the levels rather than solving the quadratic so that changing the
    curve in settings cannot silently disagree with the progress bar.
    """
    level = 1
    remaining = max(0, total_xp)
    while True:
        needed = xp_for_level(level, base, step)
        if remaining < needed:
            return level, remaining, needed
        remaining -= needed
        level += 1
        if level > 500:  # guard against a misconfigured (zero/negative) curve
            return level, remaining, needed


LEVEL_TITLES: list[tuple[int, str]] = [
    (1, "Explorer"),
    (5, "Learner"),
    (10, "Problem Solver"),
    (15, "Scholar"),
    (20, "Knowledge Builder"),
    (30, "Master Learner"),
]


def title_for_level(level: int) -> str:
    title = LEVEL_TITLES[0][1]
    for min_level, name in LEVEL_TITLES:
        if level >= min_level:
            title = name
    return title
