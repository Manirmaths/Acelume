"""
Glicko-2 rating, adapted so that the OPPONENT is a question.

Why a rating at all
-------------------
A student can already see four numbers, and none of them answers the question
they actually have, which is "if JAMB were tomorrow, what would I score?":

    XP           only ever rises -- measures attendance, not ability
    Level        derived from XP, same problem
    Mastery %    per-topic and absolute -- "did I pass this topic", not
                 "am I good at Mathematics"
    League tier  this week's effort against 19 arbitrary strangers, then reset

A rating is the one primitive that moves in both directions, is calibrated
against the difficulty of what was actually attempted, and is comparable
between two people. Adaptive question selection, honest battle matchmaking,
league seeding and calibrated bot opponents all reduce to having one.

Why Glicko-2 and not Elo
------------------------
Elo assumes regular play. Students do not play regularly -- they disappear for
three weeks during term and then answer four hundred questions in a weekend.
Glicko-2 carries an explicit uncertainty term (RD), which grows while a
student is away and shrinks as they answer, so:

  - a new or returning student's rating moves quickly to where it belongs
    instead of creeping there over hundreds of questions, and
  - the app can honestly say "still getting a read on you" instead of showing
    a confident-looking number it has no right to be confident about.

Implementation notes
--------------------
This is the standard Glicko-2 algorithm (Glickman), with two deliberate
departures, both documented at their site:

  1. The opponent is a question, whose rating has its own uncertainty. Question
     RD is passed in rather than assumed zero.
  2. A rating floor (see RATING_FLOOR). Mathematically unnecessary; product-
     necessary. A number that can fall without limit teaches a struggling
     student to avoid hard questions, which is the exact opposite of what
     practice is for.

The functions here are pure and take no database session on purpose -- the
maths is the part that must be testable in isolation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Glicko-2 works internally on a transformed scale; 173.7178 converts to and
# from the familiar ~1500-centred one.
SCALE = 173.7178

DEFAULT_RATING = 1200.0
DEFAULT_DEVIATION = 350.0
DEFAULT_VOLATILITY = 0.06

# System constant: how much volatility itself is allowed to move. Glickman
# suggests 0.3-1.2; smaller is more conservative. 0.5 suits a domain where a
# genuine step change in ability (a student finally understanding quadratics)
# is real but not common.
TAU = 0.5

CONVERGENCE_TOLERANCE = 1e-6
MAX_ITERATIONS = 100

# A student who cannot fall any further stops being afraid of the number.
# See the module docstring.
RATING_FLOOR = 400.0
RATING_CEILING = 3000.0

# Above this RD the rating has not settled and must never be shown as a firm
# number. Chess.com calls the same idea a provisional rating.
PROVISIONAL_RD = 110.0

# Seed ratings for questions with no response history yet, taken from the
# existing hand-assigned difficulty. These are a starting guess only -- real
# responses replace them (see app.rating_service.question_rating_for).
DIFFICULTY_SEED_RATING = {
    "easy": 1000.0,
    "medium": 1200.0,
    "hard": 1450.0,
}
# An unrated question is treated as uncertain, so it moves a student's rating
# less than a question whose difficulty is well established.
SEED_QUESTION_RD = 200.0


@dataclass(frozen=True)
class Rating:
    rating: float = DEFAULT_RATING
    deviation: float = DEFAULT_DEVIATION
    volatility: float = DEFAULT_VOLATILITY

    @property
    def is_provisional(self) -> bool:
        return self.deviation > PROVISIONAL_RD


@dataclass(frozen=True)
class Outcome:
    """One answered question: how hard it was, and whether they got it right."""
    question_rating: float
    question_deviation: float
    score: float  # 1.0 correct, 0.0 wrong


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def expected_score(rating: float, opponent_rating: float, opponent_deviation: float = 0.0) -> float:
    """
    Probability of answering correctly, on the familiar scale.

    Also used to drive bot opponents, which are nothing more than this
    probability plus a random draw -- see app.bots.
    """
    mu = (rating - 1500.0) / SCALE
    mu_j = (opponent_rating - 1500.0) / SCALE
    phi_j = opponent_deviation / SCALE
    return _expected(mu, mu_j, phi_j)


def _new_volatility(phi: float, delta: float, v: float, sigma: float) -> float:
    """Illinois-algorithm root find, exactly as in Glickman's step 5."""
    a = math.log(sigma * sigma)
    phi2 = phi * phi
    delta2 = delta * delta

    def f(x: float) -> float:
        ex = math.exp(x)
        num = ex * (delta2 - phi2 - v - ex)
        den = 2.0 * (phi2 + v + ex) ** 2
        return num / den - (x - a) / (TAU * TAU)

    A = a
    if delta2 > phi2 + v:
        B = math.log(delta2 - phi2 - v)
    else:
        k = 1
        while f(a - k * TAU) < 0 and k < MAX_ITERATIONS:
            k += 1
        B = a - k * TAU

    fa, fb = f(A), f(B)
    iterations = 0
    while abs(B - A) > CONVERGENCE_TOLERANCE and iterations < MAX_ITERATIONS:
        C = A + (A - B) * fa / (fb - fa)
        fc = f(C)
        if fc * fb <= 0:
            A, fa = B, fb
        else:
            fa = fa / 2.0
        B, fb = C, fc
        iterations += 1

    return math.exp(A / 2.0)


def decay(current: Rating, rating_periods_idle: float) -> Rating:
    """
    Widen uncertainty for a student who has been away.

    Nothing is claimed about their ability -- only that the app knows less
    about it than it did. This is what lets a returning student's rating move
    quickly back to the truth instead of crawling.
    """
    if rating_periods_idle <= 0:
        return current
    phi = current.deviation / SCALE
    phi_star = math.sqrt(phi * phi + current.volatility * current.volatility * rating_periods_idle)
    return Rating(
        rating=current.rating,
        deviation=min(DEFAULT_DEVIATION, phi_star * SCALE),
        volatility=current.volatility,
    )


def update(current: Rating, outcomes: list[Outcome]) -> Rating:
    """
    Apply a batch of answered questions and return the new rating.

    Batching matters: Glicko-2 is defined over a rating PERIOD containing
    several results, and updating once per answer overreacts to each one. One
    quiz, one update.
    """
    if not outcomes:
        # No information. Uncertainty still grows -- see decay().
        return current

    mu = (current.rating - 1500.0) / SCALE
    phi = current.deviation / SCALE
    sigma = current.volatility

    v_inv = 0.0
    delta_sum = 0.0
    for o in outcomes:
        mu_j = (o.question_rating - 1500.0) / SCALE
        phi_j = o.question_deviation / SCALE
        g_j = _g(phi_j)
        e_j = _expected(mu, mu_j, phi_j)
        v_inv += g_j * g_j * e_j * (1.0 - e_j)
        delta_sum += g_j * (o.score - e_j)

    if v_inv <= 0:
        # Every question was so far from the student's level that the outcome
        # carried no information (e.g. certain-win against a trivial question).
        return current

    v = 1.0 / v_inv
    delta = v * delta_sum

    sigma_prime = _new_volatility(phi, delta, v, sigma)
    phi_star = math.sqrt(phi * phi + sigma_prime * sigma_prime)
    phi_prime = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + v_inv)
    mu_prime = mu + phi_prime * phi_prime * delta_sum

    new_rating = mu_prime * SCALE + 1500.0
    new_deviation = phi_prime * SCALE

    return Rating(
        rating=max(RATING_FLOOR, min(RATING_CEILING, new_rating)),
        # Never claim more certainty than Glicko-2's own minimum, and never
        # less than the default -- a stored RD above 350 would make the next
        # update wildly unstable.
        deviation=max(30.0, min(DEFAULT_DEVIATION, new_deviation)),
        volatility=sigma_prime,
    )


def predicted_score(rating: Rating, out_of: int = 100) -> int:
    """
    Map a rating onto the scale the student actually cares about.

    This is the critical product decision in the whole feature. "1180" means
    nothing to a JAMB candidate and quietly demoralises a weak one; "62/100"
    is the number they already think in. Same mathematics underneath -- the
    raw rating stays internal.

    The anchor is deliberate rather than fitted: 1200 (the starting rating)
    maps to 50, and each 400 points is worth 25 marks, so the full usable
    rating band spans a plausible exam range. Once there is real JAMB outcome
    data to regress against, replace this function and nothing else changes.
    """
    raw = 50.0 + (rating.rating - DEFAULT_RATING) / 400.0 * 25.0
    return int(max(0, min(out_of, round(raw))))


def confidence_band(rating: Rating, out_of: int = 100) -> tuple[int, int]:
    """
    Predicted score range, from the rating's own uncertainty.

    A single number implies precision the model does not have, especially
    early. Two thirds of the RD is roughly a one-sigma band.
    """
    spread = rating.deviation * 0.67
    low = predicted_score(Rating(rating.rating - spread, rating.deviation, rating.volatility), out_of)
    high = predicted_score(Rating(rating.rating + spread, rating.deviation, rating.volatility), out_of)
    return low, high


def question_rating_from_responses(
    times_seen: int, times_correct: int, seed_rating: float, min_responses: int = 20
) -> tuple[float, float]:
    """
    Derive a question's rating from how students have actually done on it.

    A question 30% of students get right is harder than one 90% get right,
    whatever a human tagged it. That signal is already being collected in
    UserResponse; this just reads it.

    Returns (rating, deviation). Blends toward the hand-assigned seed until
    there is enough evidence, so a question answered twice does not get a
    confident rating off two data points.
    """
    if times_seen <= 0:
        return seed_rating, SEED_QUESTION_RD

    # Clamp away from 0 and 1: a question nobody has ever got right is very
    # hard, not infinitely hard, and the inverse logit diverges at the ends.
    p = min(0.97, max(0.03, times_correct / times_seen))

    # Invert the expected-score curve: what rating would a student need for
    # this to be their success probability? That rating IS the question's.
    observed = 1500.0 - SCALE * math.log(p / (1.0 - p))

    weight = min(1.0, times_seen / min_responses)
    rating = weight * observed + (1.0 - weight) * seed_rating

    # Confidence grows with evidence, floored so a question is never treated
    # as a perfectly known quantity.
    deviation = max(50.0, SEED_QUESTION_RD * (1.0 - 0.75 * weight))

    return max(RATING_FLOOR, min(RATING_CEILING, rating)), deviation
