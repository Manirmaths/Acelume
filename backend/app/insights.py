"""
Insights: say the thing, do not draw the chart.

The reason chess.com's Insights works is not the analysis, it is that it makes
flat statements -- "you lose most of your games in the endgame". Not a chart, a
sentence you can act on.

Acelume already computes plenty of percentages and renders them as bars. A bar
tells a student what is true; a sentence tells them what to do about it. Every
insight below therefore has to pass three tests before it is worth emitting:

  1. **Surprising.** "You are weak at your weakest topic" is not an insight.
  2. **Actionable.** It names a change the student can make this week.
  3. **Earned.** It has enough data behind it to be true. Each rule below
     carries its own minimum sample, and returns nothing rather than
     speculating -- a confidently-worded wrong insight costs more trust than
     silence saves.

All of this runs off data already collected. Nothing here needs new tracking.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Question, QuizAttempt, TopicMastery, UserResponse

# Sample floors. Deliberately conservative: a student who has answered forty
# questions should be told almost nothing, because almost nothing is yet true.
MIN_RESPONSES = 40
MIN_PER_BUCKET = 12
MIN_TOPIC_ATTEMPTS = 8

# A drop this large between the first and last third of long attempts is
# stamina rather than knowledge -- the questions were not getting harder.
STAMINA_DROP_PCT = 10
# Only attempts long enough for fatigue to be a plausible explanation.
STAMINA_MIN_LENGTH = 20

# Gap between overall accuracy and accuracy on one question shape, above which
# the shape itself is the problem rather than the subject.
ARCHETYPE_GAP_PCT = 15

# Times a topic has come back around and been failed again.
RELEARN_THRESHOLD = 3

# How much slower than the student's own average counts as a real time sink.
SLOW_TOPIC_MULTIPLE = 1.8


@dataclass(frozen=True)
class Insight:
    key: str
    icon: str
    text: str
    # Where to send them. None when the honest action is not a practice link.
    action_label: str | None = None
    action_href: str | None = None


# Question archetypes -- the shape of a question, independent of its topic.
#
# Borrowed from chess.com telling you which OPENINGS you are weak in. It is
# often more actionable than topic weakness, because it is a technique fix
# rather than a knowledge fix: a student who misses 'which of the following is
# NOT' questions does not have a maths problem, they have a reading problem,
# and that is a fifteen-minute fix worth several marks.
#
# Detected from the question text rather than stored, so this works on the
# whole existing bank with no re-tagging pass.
ARCHETYPES: dict[str, tuple[str, tuple[str, ...]]] = {
    "negation": ("questions that ask which option is NOT true", (
        " not ", " except", "cannot", "is false", "incorrect",
    )),
    "data_read": ("questions that read from a table or graph", (
        "table", "graph", "chart", "diagram shows", "figure shows",
    )),
    "multi_step": ("questions with several steps chained together", (
        "then find", "hence", "and hence", "calculate the value of",
    )),
}


def _archetype_of(question: Question) -> str | None:
    text = f" {(question.question_text or '').lower()} "
    for key, (_, markers) in ARCHETYPES.items():
        if any(m in text for m in markers):
            return key
    return None


def _pct(correct: int, total: int) -> int:
    return round(100 * correct / total) if total else 0


def _stamina(db: Session, user_id: int) -> Insight | None:
    """
    Does accuracy fall off late in long sessions?

    Compared within the SAME attempts rather than across the day, so it
    measures fatigue rather than "they revise harder topics in the evening".
    """
    attempts = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.user_id == user_id,
            QuizAttempt.finished_at.isnot(None),
            QuizAttempt.mode.in_(["quiz", "mock", "cbt"]),
        )
        .order_by(QuizAttempt.id.desc())
        .limit(20)
        .all()
    )
    long_attempts = [a for a in attempts if len(a.question_ids or []) >= STAMINA_MIN_LENGTH]
    if len(long_attempts) < 2:
        return None

    early_c = early_t = late_c = late_t = 0
    for attempt in long_attempts:
        qids = [q for q in attempt.question_ids if isinstance(q, int)]
        responses = {
            r.question_id: r
            for r in db.query(UserResponse).filter(UserResponse.attempt_id == attempt.id).all()
        }
        third = max(1, len(qids) // 3)
        for qid in qids[:third]:
            r = responses.get(qid)
            if r:
                early_t += 1
                early_c += 1 if r.is_correct else 0
        for qid in qids[-third:]:
            r = responses.get(qid)
            if r:
                late_t += 1
                late_c += 1 if r.is_correct else 0

    if early_t < MIN_PER_BUCKET or late_t < MIN_PER_BUCKET:
        return None

    drop = _pct(early_c, early_t) - _pct(late_c, late_t)
    if drop < STAMINA_DROP_PCT:
        return None

    return Insight(
        key="stamina",
        icon="fa-solid fa-battery-quarter",
        text=(
            f"Your accuracy drops {drop}% in the last third of long sessions. "
            "That is stamina, not knowledge — try two shorter sets instead of one long one."
        ),
    )


def _archetype(db: Session, user_id: int) -> Insight | None:
    """Which question SHAPE beats them, independent of topic."""
    rows = (
        db.query(UserResponse, Question)
        .join(Question, Question.id == UserResponse.question_id)
        .filter(UserResponse.user_id == user_id)
        .order_by(UserResponse.id.desc())
        .limit(600)
        .all()
    )
    if len(rows) < MIN_RESPONSES:
        return None

    overall_c = sum(1 for r, _ in rows if r.is_correct)
    overall = _pct(overall_c, len(rows))

    worst = None
    for key, (label, _) in ARCHETYPES.items():
        bucket = [(r, q) for r, q in rows if _archetype_of(q) == key]
        if len(bucket) < MIN_PER_BUCKET:
            continue
        pct = _pct(sum(1 for r, _ in bucket if r.is_correct), len(bucket))
        gap = overall - pct
        if gap >= ARCHETYPE_GAP_PCT and (worst is None or gap > worst[0]):
            worst = (gap, label, pct)

    if worst is None:
        return None

    _, label, pct = worst
    return Insight(
        key="archetype",
        icon="fa-solid fa-bullseye",
        text=(
            f"You get {overall}% right overall, but only {pct}% on {label}. "
            "The subject is not the problem — the way the question is worded is."
        ),
    )


def _not_sticking(db: Session, user_id: int) -> Insight | None:
    """
    A topic learned, forgotten and relearned repeatedly.

    Worth surfacing because the student's own instinct will be to practise it
    harder, when the useful move is usually to learn it a different way.
    """
    rows = (
        db.query(TopicMastery)
        .filter(
            TopicMastery.user_id == user_id,
            TopicMastery.review_stage >= RELEARN_THRESHOLD,
            TopicMastery.mastery_score < 60,
        )
        .order_by(TopicMastery.practice_attempts.desc())
        .all()
    )
    row = next((r for r in rows if (r.practice_attempts or 0) >= MIN_TOPIC_ATTEMPTS), None)
    if row is None:
        return None

    return Insight(
        key="not_sticking",
        icon="fa-solid fa-arrows-rotate",
        text=(
            f'"{row.topic}" keeps slipping back after you learn it. '
            "More questions on their own are not fixing it — try the lesson again first."
        ),
        action_label=f"Re-read {row.topic}",
        action_href=f"/subjects/{row.subject}/topics/{row.topic}",
    )


def _slow_topic(db: Session, user_id: int) -> Insight | None:
    """
    Where the student's exam time actually goes.

    Requires answer_seconds, so it stays silent for anyone whose answers all
    predate that column rather than inventing a number.
    """
    rows = (
        db.query(UserResponse, Question)
        .join(Question, Question.id == UserResponse.question_id)
        .filter(
            UserResponse.user_id == user_id,
            UserResponse.answer_seconds.isnot(None),
        )
        .order_by(UserResponse.id.desc())
        .limit(600)
        .all()
    )
    if len(rows) < MIN_RESPONSES:
        return None

    overall_avg = sum(r.answer_seconds for r, _ in rows) / len(rows)
    if overall_avg <= 0:
        return None

    by_topic: dict[tuple[str, str], list[int]] = {}
    accuracy: dict[tuple[str, str], list[bool]] = {}
    for r, q in rows:
        if not q.subject or not q.topic:
            continue
        key = (q.subject, q.topic)
        by_topic.setdefault(key, []).append(r.answer_seconds)
        accuracy.setdefault(key, []).append(bool(r.is_correct))

    worst = None
    for key, seconds in by_topic.items():
        if len(seconds) < MIN_PER_BUCKET:
            continue
        avg = sum(seconds) / len(seconds)
        ratio = avg / overall_avg
        if ratio >= SLOW_TOPIC_MULTIPLE and (worst is None or ratio > worst[0]):
            worst = (ratio, key, avg, _pct(sum(accuracy[key]), len(accuracy[key])))

    if worst is None:
        return None

    ratio, (subject, topic), avg, pct = worst
    return Insight(
        key="slow_topic",
        icon="fa-solid fa-stopwatch",
        text=(
            f"{topic} takes you {ratio:.1f}× longer than your average question "
            f"({round(avg)}s), for {pct}% accuracy. In a real paper that is where "
            "your time goes."
        ),
        action_label=f"Drill {topic}",
        action_href=f"/quiz?subject={subject}&topic={topic}&n=10",
    )


def _guessing(db: Session, user_id: int) -> Insight | None:
    """
    Answers too fast to have been read.

    Framed as pace rather than character. The student is not accused of
    guessing; they are shown a number and left to draw the conclusion.
    """
    rows = (
        db.query(UserResponse)
        .filter(UserResponse.user_id == user_id, UserResponse.answer_seconds.isnot(None))
        .order_by(UserResponse.id.desc())
        .limit(400)
        .all()
    )
    if len(rows) < MIN_RESPONSES:
        return None

    rushed = [r for r in rows if r.answer_seconds <= 5]
    if len(rushed) < MIN_PER_BUCKET:
        return None

    rushed_pct = _pct(sum(1 for r in rushed if r.is_correct), len(rushed))
    considered = [r for r in rows if r.answer_seconds > 5]
    if len(considered) < MIN_PER_BUCKET:
        return None
    considered_pct = _pct(sum(1 for r in considered if r.is_correct), len(considered))

    if considered_pct - rushed_pct < ARCHETYPE_GAP_PCT:
        return None

    share = _pct(len(rushed), len(rows))
    return Insight(
        key="pace",
        icon="fa-solid fa-gauge-high",
        text=(
            f"{share}% of your answers come in under five seconds, and you get "
            f"{rushed_pct}% of those right against {considered_pct}% of the rest. "
            "Slowing down on those alone would move your score."
        ),
    )


def for_user(db: Session, user_id: int, limit: int = 4) -> list[Insight]:
    """
    Everything true and worth saying, best first.

    Ordered by how actionable each finding is rather than how bad it looks.
    Returns an empty list freely: a student with nothing surprising in their
    data should be told nothing, not given filler.
    """
    total = db.query(UserResponse).filter(UserResponse.user_id == user_id).count()
    if total < MIN_RESPONSES:
        return []

    candidates = [
        _not_sticking(db, user_id),
        _archetype(db, user_id),
        _stamina(db, user_id),
        _guessing(db, user_id),
        _slow_topic(db, user_id),
    ]
    return [c for c in candidates if c is not None][:limit]
