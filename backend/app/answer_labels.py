"""
Named mistake types for a finished attempt.

The idea is borrowed from chess.com's Game Review, and the borrowed part is
not the analysis -- it is the VOCABULARY. Calling a move a "blunder" gives
players a shared word for a category of error, which makes the error
thinkable and therefore fixable. Players say "I blundered" the way an Acelume
student should be able to say "I slipped on a topic I'd already mastered".

"You got 9/12" is a grade. "You slipped on a topic you'd mastered, here are
five questions on it" is a next action.

The distinction that carries most of the value is SLIP versus GAP. To a
student they feel identical -- both are a red cross -- but they demand
opposite responses: a slip needs attention, a gap needs teaching. Nothing in
the app could tell them apart before this.
"""

from __future__ import annotations

from dataclasses import dataclass

# Mastery states in which the student has demonstrably learned the topic. A
# wrong answer here is a lapse, not ignorance.
KNOWN_STATES = {"proficient", "mastered", "review_due"}

# Rating points above the student's own level at which a correct answer stops
# being routine and starts being genuinely impressive.
SHARP_MARGIN = 150.0

# A correct answer taking more than this multiple of the student's own average
# suggests working it out the long way, or a lucky guess after deliberation --
# either way, not secure knowledge.
LUCKY_SLOWNESS = 2.0

# Below this, on an easy question, the student did not read it.
BLUNDER_SECONDS = 8
BLUNDER_MAX_RATING = 1100.0


@dataclass(frozen=True)
class Label:
    key: str
    title: str
    message: str | None
    tone: str  # success | neutral | warning | danger


LABELS = {
    "sharp": Label("sharp", "Sharp", "Well above your level.", "success"),
    "solid": Label("solid", "Solid", None, "success"),
    "lucky": Label("lucky", "Lucky", "Right answer — check you'd get it again.", "warning"),
    "slip": Label("slip", "Slip", "You know this one. Read it again.", "warning"),
    "gap": Label("gap", "Gap", "Not covered yet — here's the lesson.", "neutral"),
    "blunder": Label("blunder", "Blunder", "Too quick. This one was there for you.", "danger"),
}


def classify(
    *,
    is_correct: bool,
    answered: bool,
    question_rating: float,
    student_rating: float | None,
    topic_state: str | None,
    answer_seconds: int | None,
    average_seconds: float | None,
) -> Label | None:
    """
    Label one answer.

    Returns None for a question that was never attempted -- an unanswered
    question is not a mistake, and calling it one would punish a student for
    running out of time.

    Every input is optional in practice, and the function degrades rather than
    guesses: without timing it will never say Lucky or Blunder, and without a
    rating it will never say Sharp. A label that might be wrong is worse than
    no label, because the whole point is to give the student a word they can
    trust.
    """
    if not answered:
        return None

    known_topic = topic_state in KNOWN_STATES

    if is_correct:
        # Sharp: beat a question meaningfully above their level.
        if student_rating is not None and question_rating >= student_rating + SHARP_MARGIN:
            return LABELS["sharp"]

        # Lucky: right, but slowly, or on a topic they have not learned yet.
        # Both mean "do not bank this one".
        slow = (
            answer_seconds is not None
            and average_seconds
            and answer_seconds > average_seconds * LUCKY_SLOWNESS
        )
        if slow or (topic_state is not None and not known_topic):
            return LABELS["lucky"]

        return LABELS["solid"]

    # Blunder: wrong, fast, on something easy. Not a knowledge problem.
    if (
        answer_seconds is not None
        and answer_seconds <= BLUNDER_SECONDS
        and question_rating <= BLUNDER_MAX_RATING
    ):
        return LABELS["blunder"]

    # Slip vs Gap -- the distinction that matters.
    if known_topic:
        return LABELS["slip"]
    return LABELS["gap"]


def accuracy(counts: dict[str, int], answered: int) -> int | None:
    """
    A single headline number, weighted by how good each answer actually was.

    Deliberately NOT the same as percent correct. A student who scrapes 9/12
    with three lucky guesses has not performed as well as one who gets 9/12
    cleanly, and a score that cannot tell them apart is the reason "9/12"
    stops being informative after the first week.
    """
    if answered <= 0:
        return None
    weights = {
        "sharp": 1.15,   # above par
        "solid": 1.0,
        "lucky": 0.7,    # counted, but not banked
        "gap": 0.0,      # not taught yet -- not held against them beyond the zero
        "slip": 0.0,
        "blunder": 0.0,
    }
    earned = sum(weights.get(k, 0.0) * v for k, v in counts.items())
    return int(max(0, min(100, round(100 * earned / answered))))


def headline(counts: dict[str, int]) -> str | None:
    """
    The one sentence worth saying about this attempt.

    Ordered by how actionable the finding is, not by severity. A slip on a
    mastered topic is the most useful thing the app can tell a student,
    because it is both surprising and fixable in ten minutes.
    """
    if counts.get("slip"):
        n = counts["slip"]
        return (
            f"{n} slip{'s' if n > 1 else ''} on {'topics' if n > 1 else 'a topic'} "
            f"you've already mastered."
        )
    if counts.get("blunder"):
        n = counts["blunder"]
        return f"{n} answer{'s' if n > 1 else ''} too fast to have been read properly."
    if counts.get("lucky"):
        n = counts["lucky"]
        return f"{n} right answer{'s' if n > 1 else ''} that might not hold up next time."
    if counts.get("gap"):
        n = counts["gap"]
        return f"{n} topic{'s' if n > 1 else ''} here you haven't been taught yet."
    if counts.get("sharp"):
        return "You beat questions above your level."
    return None
