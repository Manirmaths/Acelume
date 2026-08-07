"""
Practice opponents for battles.

The problem
-----------
A battle needs a second human. Invitations expire after 48 hours, a student may
hold at most 5 open ones, and live mode needs both players on their phones at
the same moment. For a student who opens the app at 10pm with nobody else from
their school on the platform, the whole feature does not exist. That is
ordinary multiplayer cold-start, and it is the reason a good feature can look
like a dead one.

What a bot is here
------------------
Not an AI. There is no model call, no latency and no cost. A bot is a rating
plus two probability distributions:

    P(correct) = glicko_expected_score(bot_rating, question_rating)
    time taken = draw from the bot's speed distribution

That is enough to feel human, because the mistakes it makes are PLAUSIBLE
rather than random -- it misses hard questions, occasionally fumbles easy ones
if it is a careless bot, and its answers arrive at a believable pace.

The part actually worth copying from chess.com is not the simulation. It is
that the bots have names, personalities and honestly published ratings, so
playing one feels like playing someone instead of practising against a
machine.

Honesty rules, enforced here and in routers/battles.py
------------------------------------------------------
  - A bot is always visibly a bot. Never inferable-only.
  - It is called a "practice opponent", never an "opponent".
  - **Bot results never touch league points or leaderboards.** They may move a
    subject rating, because a calibrated opponent is a valid measurement, but
    they must not affect anything ranked against real students. A student who
    farms bots must not out-rank one who plays people.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.rating import expected_score


@dataclass(frozen=True)
class Bot:
    key: str
    name: str
    rating: float
    # Multiplies P(correct) on questions rated above the bot. Below 1.0 means
    # it gives up on hard questions; above means it punches up.
    hard_factor: float
    # Chance of fumbling a question it should comfortably get. This is what
    # makes a bot beatable by a weaker but careful student.
    slip_chance: float
    # Seconds per answer, (mean, spread).
    speed: tuple[float, float]
    blurb: str


# Deliberately Nigerian first names: a practice opponent called "Bot_1138"
# is a machine, and one called Amara is someone to beat. Ratings are spaced so
# every student has one just above them.
BOTS: list[Bot] = [
    Bot(
        key="tunde", name="Tunde", rating=700.0,
        hard_factor=0.75, slip_chance=0.12, speed=(7.0, 3.0),
        blurb="Rushes his answers. Beat him by being careful.",
    ),
    Bot(
        key="amara", name="Amara", rating=950.0,
        hard_factor=0.85, slip_chance=0.05, speed=(16.0, 5.0),
        blurb="Never rushes. Very strong on the basics.",
    ),
    Bot(
        key="chidi", name="Chidi", rating=1150.0,
        hard_factor=1.0, slip_chance=0.10, speed=(8.0, 3.0),
        blurb="Very quick, but slips under pressure.",
    ),
    Bot(
        key="ms_bello", name="Ms Bello", rating=1400.0,
        hard_factor=1.1, slip_chance=0.02, speed=(22.0, 6.0),
        blurb="The one to beat. Takes her time and rarely misses.",
    ),
]

BOTS_BY_KEY = {b.key: b for b in BOTS}


def pick_for(student_rating: float | None) -> Bot:
    """
    Choose an opponent slightly above the student.

    Slightly above, not equal: a coin-flip opponent is less motivating than
    one the student can beat with effort. With no rating yet, start at the
    bottom -- an early thrashing is the quickest way to lose a new student.
    """
    if student_rating is None:
        return BOTS_BY_KEY["tunde"]
    stretch = student_rating + 75.0
    return min(BOTS, key=lambda b: abs(b.rating - stretch))


def answer(
    bot: Bot, question_rating: float, correct_option: str, options: list[str], rng: random.Random
) -> tuple[str, int]:
    """
    Produce one plausible answer: (selected_option, seconds_taken).

    `rng` is injected rather than taken from the module so a battle can seed it
    deterministically. That matters: grading is idempotent and may run more
    than once (either player can finish a battle, and the endpoint is safe to
    call repeatedly), so the same bot must give the same answers every time.
    A bot whose score changed between two reads of the same battle would be
    an obvious bug and would look like cheating.
    """
    p = expected_score(bot.rating, question_rating)

    if question_rating > bot.rating:
        p *= bot.hard_factor
    p *= (1.0 - bot.slip_chance)
    p = max(0.02, min(0.97, p))

    seconds = max(2, int(rng.gauss(bot.speed[0], bot.speed[1])))

    if rng.random() < p:
        return correct_option, seconds

    # A wrong answer, chosen from the other options -- never a blank. A bot
    # that skipped questions would be trivially beatable and read as broken.
    wrong = [o for o in options if o != correct_option]
    return (rng.choice(wrong) if wrong else correct_option), seconds


def public(bot: Bot) -> dict:
    return {
        "key": bot.key,
        "name": bot.name,
        "rating": int(bot.rating),
        "blurb": bot.blurb,
        # Never inferable-only. Every surface that renders an opponent must be
        # able to say plainly that this one is not a person.
        "is_bot": True,
    }
