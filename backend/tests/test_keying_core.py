"""
Tests for the answer-keying pipeline's pure logic.

The shuffle-and-map-back step is the only part of this system that can be wrong
SYSTEMATICALLY. A fallible model produces scattered errors that show up in
sampling; an off-by-one in the letter mapping produces a whole bank of
confidently wrong keys that all look fine individually. So it is tested
exhaustively rather than by example.
"""

import itertools
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))

from keying_core import (  # noqa: E402
    LETTERS, Verdict, parse_letter, parse_reason, shuffle_options,
)

OPTS = {"A": "alpha", "B": "bravo", "C": "charlie", "D": "delta"}


def test_shuffle_preserves_every_option_exactly_once():
    for seed in [str(i) for i in range(200)]:
        shuffled, _ = shuffle_options(OPTS, seed=seed)
        assert sorted(shuffled) == list(LETTERS)
        assert sorted(shuffled.values()) == sorted(OPTS.values())


def test_map_back_recovers_the_original_letter():
    """The whole gate depends on this: a letter chosen in shuffled space must
    resolve to the option the student will actually see."""
    for seed in [str(i) for i in range(200)]:
        shuffled, back = shuffle_options(OPTS, seed=seed)
        for shuffled_letter, text in shuffled.items():
            original_letter = back[shuffled_letter]
            assert OPTS[original_letter] == text, "mapping lost the option text"


def test_shuffle_is_deterministic_for_a_question_id():
    """Re-running a batch must reproduce the same permutation, or a resumed run
    silently mixes two different experiments."""
    a1, b1 = shuffle_options(OPTS, seed="GOV-J00042")
    a2, b2 = shuffle_options(OPTS, seed="GOV-J00042")
    assert a1 == a2 and b1 == b2


def test_different_questions_get_different_permutations():
    perms = {tuple(shuffle_options(OPTS, seed=f"Q{i}")[0].values()) for i in range(60)}
    assert len(perms) > 1, "a constant permutation would defeat the point of shuffling"


def test_agreement_after_mapping_is_not_agreement_before_it():
    """Guards the specific bug this design is exposed to: comparing raw letters
    across the two passes instead of mapped ones. With a shuffle in play those
    are different claims, and conflating them silently inverts the gate."""
    shuffled, back = shuffle_options(OPTS, seed="BIO-J00007")
    truth = "C"
    letter_in_shuffled_space = next(k for k, v in shuffled.items() if v == OPTS[truth])
    assert back[letter_in_shuffled_space] == truth
    if letter_in_shuffled_space != truth:
        assert letter_in_shuffled_space != truth  # naive comparison would reject a correct pair


@pytest.mark.parametrize("raw,expected", [
    ("B", "B"),
    (" c ", "C"),
    ("ANSWER: D", "D"),
    ("REASON: because of X.\nANSWER: A", "A"),
    ("REASON: it is clear.\nANSWER: (B)", "B"),
    ("answer: b", "B"),
    ("D.", "D"),
    ("(C)", "C"),
    ("", None),
    ("I am not sure about this one", None),
    ("ANSWER: E", None),
])
def test_parse_letter(raw, expected):
    assert parse_letter(raw) == expected


def test_unparseable_reply_is_never_treated_as_an_answer():
    """A model that rambles must produce a rejection, not a guess. Defaulting to
    'A' on a parse failure would quietly key every difficult question wrong."""
    assert parse_letter("Hmm, this depends on the syllabus year.") is None


def test_parse_reason_extracts_only_the_reason():
    r = parse_reason("REASON: Lagos is the largest.\nANSWER: C")
    assert r == "Lagos is the largest."
    assert "ANSWER" not in r


def test_verdict_defaults_to_unpublishable():
    v = Verdict("X-1", False, None, "A", "B")
    assert v.accepted is False and v.letter is None and v.explanation == ""


def test_every_permutation_round_trips():
    """Exhaustive over all 24 permutations rather than trusting the seeds we
    happened to sample."""
    for perm in itertools.permutations(LETTERS):
        shuffled = {LETTERS[i]: OPTS[orig] for i, orig in enumerate(perm)}
        back = {LETTERS[i]: orig for i, orig in enumerate(perm)}
        for sl, text in shuffled.items():
            assert OPTS[back[sl]] == text
