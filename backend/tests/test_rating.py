"""
Glicko-2 maths.

The first test is the important one: it checks this implementation against the
worked example in Glickman's own paper. Everything else in the rating feature
-- adaptive difficulty, bot calibration, matchmaking, predicted score -- is
downstream of these numbers being right, and a subtly wrong rating system
fails silently and looks plausible the whole time.
"""

import math

import pytest

from app.rating import (
    DEFAULT_DEVIATION, DEFAULT_RATING, PROVISIONAL_RD, RATING_FLOOR,
    Outcome, Rating, confidence_band, decay, expected_score, predicted_score,
    question_rating_from_responses, update,
)


# ------------------------------------------------------- reference check ----

def test_matches_glickmans_published_worked_example():
    """
    Glickman's Glicko-2 paper, section 'Example calculation':
    a player rated 1500 (RD 200, sigma 0.06) plays three opponents --
    1400/RD30 (win), 1550/RD100 (loss), 1700/RD300 (loss).
    Expected result: rating ~1464.06, RD ~151.52, sigma ~0.05999.
    """
    player = Rating(rating=1500.0, deviation=200.0, volatility=0.06)
    outcomes = [
        Outcome(question_rating=1400.0, question_deviation=30.0, score=1.0),
        Outcome(question_rating=1550.0, question_deviation=100.0, score=0.0),
        Outcome(question_rating=1700.0, question_deviation=300.0, score=0.0),
    ]

    result = update(player, outcomes)

    assert result.rating == pytest.approx(1464.06, abs=0.1)
    assert result.deviation == pytest.approx(151.52, abs=0.1)
    assert result.volatility == pytest.approx(0.05999, abs=0.0001)


# --------------------------------------------------------------- basics ----

def test_beating_a_harder_question_raises_the_rating():
    before = Rating(1200.0, 200.0, 0.06)
    after = update(before, [Outcome(1400.0, 100.0, 1.0)])
    assert after.rating > before.rating


def test_missing_an_easier_question_lowers_the_rating():
    before = Rating(1200.0, 200.0, 0.06)
    after = update(before, [Outcome(1000.0, 100.0, 0.0)])
    assert after.rating < before.rating


def test_answering_reduces_uncertainty():
    before = Rating(1200.0, DEFAULT_DEVIATION, 0.06)
    after = update(before, [Outcome(1200.0, 80.0, 1.0) for _ in range(10)])
    assert after.deviation < before.deviation


def test_a_harder_question_moves_the_rating_more_than_an_easier_one():
    start = Rating(1200.0, 200.0, 0.06)
    modest = update(start, [Outcome(1250.0, 80.0, 1.0)]).rating
    big = update(start, [Outcome(1600.0, 80.0, 1.0)]).rating
    assert big > modest


def test_a_confident_question_moves_the_rating_more_than_an_uncertain_one():
    """Question RD is not decorative -- an unproven question should count less."""
    start = Rating(1200.0, 200.0, 0.06)
    confident = update(start, [Outcome(1400.0, 50.0, 1.0)]).rating
    uncertain = update(start, [Outcome(1400.0, 300.0, 1.0)]).rating
    assert confident > uncertain


def test_no_outcomes_leaves_the_rating_untouched():
    start = Rating(1234.0, 180.0, 0.06)
    assert update(start, []) == start


# ----------------------------------------------------------- guardrails ----

def test_rating_cannot_fall_below_the_floor():
    """
    Product guardrail, not a mathematical one. A number that falls without
    limit teaches a struggling student to avoid hard questions -- exactly
    backwards.
    """
    r = Rating(RATING_FLOOR + 20, 200.0, 0.06)
    for _ in range(50):
        r = update(r, [Outcome(1600.0, 60.0, 0.0) for _ in range(10)])
    assert r.rating >= RATING_FLOOR


def test_deviation_never_exceeds_the_default():
    """A stored RD above 350 would make the next update wildly unstable."""
    r = update(Rating(1200.0, DEFAULT_DEVIATION, 0.06), [Outcome(1200.0, 100.0, 0.0)])
    assert r.deviation <= DEFAULT_DEVIATION


def test_a_new_student_is_provisional():
    assert Rating().is_provisional is True


def test_a_settled_student_is_not_provisional():
    assert Rating(1200.0, PROVISIONAL_RD - 10, 0.06).is_provisional is False


def test_idle_time_widens_uncertainty_without_moving_the_rating():
    settled = Rating(1300.0, 60.0, 0.06)
    rusty = decay(settled, rating_periods_idle=10)

    assert rusty.rating == settled.rating, "being away is not evidence of getting worse"
    assert rusty.deviation > settled.deviation


def test_decay_is_capped_at_the_default_deviation():
    assert decay(Rating(1300.0, 60.0, 0.06), 10_000).deviation <= DEFAULT_DEVIATION


def test_no_idle_time_is_a_no_op():
    r = Rating(1300.0, 60.0, 0.06)
    assert decay(r, 0) == r


# ------------------------------------------------------ expected scores ----

def test_equal_rating_is_a_coin_flip():
    assert expected_score(1200.0, 1200.0) == pytest.approx(0.5, abs=1e-9)


def test_a_much_stronger_student_is_expected_to_win():
    assert expected_score(1800.0, 1000.0) > 0.9


def test_a_much_weaker_student_is_expected_to_lose():
    assert expected_score(1000.0, 1800.0) < 0.1


def test_expected_score_is_monotonic_in_rating():
    values = [expected_score(r, 1200.0) for r in range(800, 1800, 50)]
    assert values == sorted(values)


# ------------------------------------------------------ predicted score ----

def test_the_starting_rating_maps_to_the_middle_of_the_scale():
    assert predicted_score(Rating(DEFAULT_RATING, 50.0, 0.06)) == 50


def test_predicted_score_rises_with_rating():
    weak = predicted_score(Rating(900.0, 50.0, 0.06))
    strong = predicted_score(Rating(1600.0, 50.0, 0.06))
    assert strong > weak


def test_predicted_score_is_clamped_to_the_scale():
    assert predicted_score(Rating(4000.0, 50.0, 0.06)) <= 100
    assert predicted_score(Rating(0.0, 50.0, 0.06)) >= 0


def test_an_uncertain_rating_gives_a_wider_band():
    """The band is the honesty mechanism -- it must actually reflect RD."""
    certain_lo, certain_hi = confidence_band(Rating(1200.0, 40.0, 0.06))
    unsure_lo, unsure_hi = confidence_band(Rating(1200.0, 300.0, 0.06))
    assert (unsure_hi - unsure_lo) > (certain_hi - certain_lo)


# ------------------------------------------------- question calibration ----

def test_an_unanswered_question_falls_back_to_its_seed():
    rating, deviation = question_rating_from_responses(0, 0, seed_rating=1200.0)
    assert rating == 1200.0
    assert deviation > 100.0, "an unproven question should not move ratings much"


def test_a_question_most_students_miss_rates_harder_than_one_most_get_right():
    hard, _ = question_rating_from_responses(200, 60, seed_rating=1200.0)    # 30%
    easy, _ = question_rating_from_responses(200, 180, seed_rating=1200.0)   # 90%
    assert hard > easy


def test_real_performance_overrides_the_hand_assigned_difficulty():
    """
    A question tagged 'easy' that almost nobody gets right is not easy. The
    whole point of deriving this from responses is that the tag can be wrong.
    """
    rating, _ = question_rating_from_responses(500, 25, seed_rating=1000.0)  # 5%
    assert rating > 1000.0


def test_confidence_grows_with_evidence():
    _, few = question_rating_from_responses(3, 2, seed_rating=1200.0)
    _, many = question_rating_from_responses(500, 300, seed_rating=1200.0)
    assert many < few


def test_a_thin_sample_stays_close_to_the_seed():
    """Two responses must not produce a confident rating."""
    rating, _ = question_rating_from_responses(2, 0, seed_rating=1200.0)
    assert abs(rating - 1200.0) < 200.0


def test_a_question_nobody_answers_correctly_does_not_blow_up():
    rating, _ = question_rating_from_responses(100, 0, seed_rating=1200.0)
    assert math.isfinite(rating)
    assert rating <= 3000.0


def test_a_question_everybody_answers_correctly_does_not_blow_up():
    rating, _ = question_rating_from_responses(100, 100, seed_rating=1200.0)
    assert math.isfinite(rating)
    assert rating >= RATING_FLOOR
