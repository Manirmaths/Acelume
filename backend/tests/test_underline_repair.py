"""
The English underline repair (scripts/repair_underlines.py).

Around 950 English questions told the candidate to consider "the underlined
word" while carrying no underline at all -- the markup was lost at import. The
repair reads the target back out of the explanation.

The risk being tested is NOT "does it fix things". It is "does it ever mark the
wrong word". A question that underlines the wrong word is worse than one that
underlines nothing, because a student cannot tell it is broken -- they will
answer the question they were shown, get it wrong, and learn the wrong thing.

So most of these tests are about the rules REFUSING to fire.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import repair_underlines as repair  # noqa: E402


def fix(question: str, explanation: str) -> tuple[str | None, str]:
    return repair.repair({"question_text": question, "explanation": explanation})


# ------------------------------------------------------------------ repairing


def test_it_underlines_the_word_the_explanation_quotes():
    fixed, rule = fix(
        "Choose the option opposite in meaning to the underlined word(s). "
        "His father surmounted the myriad of obstacles on his way?",
        "'Myriad' means countless/very many; its opposite is 'few'.",
    )
    assert "<u>myriad</u>" in fixed
    assert rule == "exact term from the explanation"


def test_it_reads_a_target_named_without_quotes():
    """Explanations often open with the bare word: 'Moribund means dying...'."""
    fixed, _ = fix(
        "Choose the option nearest in meaning to the word underlined. "
        "I cannot understand why Ali should serve in that moribund administration.",
        "Moribund means dying or on the point of collapse.",
    )
    assert "<u>moribund</u>" in fixed


def test_it_rebuilds_a_word_the_scraper_split_around_the_underline():
    """`C ou p` can only have been `C<u>ou</u>p`."""
    fixed, rule = fix(
        "Choose the option that has the same vowel sound as the letters underlined. C ou p?",
        "'Coup' is pronounced with a long 'oo' vowel sound.",
    )
    assert "C<u>ou</u>p" in fixed
    assert rule == "spacing left by the scraper"


def test_a_two_chunk_split_is_resolved_by_the_explanation():
    """`Gn ash` is ambiguous alone; the explanation quoting 'gn' settles it."""
    fixed, _ = fix(
        "Choose the option that has the same consonant sound as the letter underlined. Gn ash.",
        "The 'gn' in 'gnash' has a silent 'g', pronounced simply /n/, matching 'new'.",
    )
    assert "<u>Gn</u>ash" in fixed


def test_a_word_broken_by_a_stray_space_is_rejoined_not_wrapped():
    """`greedies t` was one underlined word, and the space is damage."""
    fixed, rule = fix(
        "choose the option nearly opposite in meaning to the word(s) underlined "
        "The lawmakers are perceived to be the greedies t set of politicians.",
        "'Greediest' means most self-interested; its opposite is 'selfless'.",
    )
    assert "<u>greediest</u>" in fixed
    assert rule == "word split by a stray space"


def test_it_tolerates_a_different_inflection():
    fixed, _ = fix(
        "Choose the option nearest in meaning to the word underlined. "
        "The conference Centre caters for transients only.",
        "A transient is someone staying only briefly.",
    )
    assert "<u>transients</u>" in fixed


# --------------------------------------------------------------- refusing


def test_it_refuses_when_the_explanation_confirms_nothing():
    fixed, reason = fix(
        "Which of the following words has the same vowel sound as the one "
        "represented by the underlined letters in the word 'boot'?",
        "",
    )
    assert fixed is None
    assert reason == "no confirmable signal"


def test_it_never_marks_a_stopword():
    """
    'The' opens countless explanations and appears in every sentence. Matching
    on it would underline an arbitrary word with total confidence.
    """
    fixed, _ = fix(
        "Choose the option opposite in meaning to the underlined word. "
        "The man walked into the room.",
        "The answer is the opposite of what is stated.",
    )
    assert fixed is None


def test_an_ordinary_sentence_is_not_mistaken_for_a_broken_word():
    """
    "...rush for the goods?" is three short words in a row, which looks exactly
    like a scraper-split word. It is only rebuilt if the rejoined string is one
    the explanation actually names -- 'forthegoods' is not.
    """
    fixed = repair.by_spacing(
        "Choose the option with the same vowel sound as the letters underlined. "
        "The trader was amused by the rush for the goods?",
        "Something unrelated entirely.",
    )
    assert fixed is None


def test_the_instruction_itself_is_never_marked():
    """
    The word 'word' appears in "the underlined word". Only text AFTER the
    instruction is a candidate, or the rule would mark its own prompt.
    """
    fixed, _ = fix(
        "Choose the option opposite in meaning to the underlined word. "
        "His speech was verbose.",
        "'Verbose' means wordy; its opposite is 'terse'.",
    )
    assert fixed.count("<u>") == 1
    assert "<u>verbose</u>" in fixed
    assert "underlined <u>word</u>" not in fixed


def test_fuzzy_matching_is_off_for_phonetics():
    """
    In `p o table` the target is the 'o'. Fuzzy matching happily finds 'table'
    inside it and marks the wrong half of the word, so it is not allowed to
    run on questions about sounds and letters.
    """
    fixed = repair.by_close_term(
        "Choose the option that has the same vowel sound as the underlined letter(s). p o table",
        "'Potable' and 'post' contain the same vowel.",
    )
    assert fixed is None


def test_questions_that_already_carry_markup_are_left_alone():
    rows = [
        {"question_text": "Choose the opposite of the underlined <u>word</u>. He is brave.",
         "explanation": "'Brave' means courageous."},
        {"question_text": "Choose the opposite of the underlined word. He is brave.",
         "explanation": "'Brave' means courageous."},
        {"question_text": "What is 2 + 2?", "explanation": "Four."},
    ]
    assert len(repair.affected(rows)) == 1
    assert repair.affected(rows)[0] is rows[1]


@pytest.mark.parametrize("markup", ["<u>", "<b>", "<i>"])
def test_any_existing_emphasis_counts_as_already_marked(markup):
    close = markup.replace("<", "</")
    row = {"question_text": f"the underlined {markup}x{close} here", "explanation": ""}
    assert repair.affected([row]) == []


# ----------------------------------------------------------------- the bank


def test_no_active_english_question_claims_an_underline_it_does_not_have():
    """
    The regression test for the whole exercise, run against the real bank.

    If someone re-imports from a source that strips markup again, this fails
    before a student ever sees it.
    """
    import csv

    path = Path(__file__).resolve().parents[2] / "data" / "questions.csv"
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    live = [r for r in rows if r.get("status") == "active"]
    broken = [r["question_id"] for r in repair.affected(live)]
    assert broken == [], f"{len(broken)} live questions reference an underline that is not there"


def test_ordinary_prose_about_underlining_is_not_treated_as_an_instruction():
    """
    "The French colonial system was underlined by the policy of..." is a good
    Government question. An earlier version of this filter quarantined it.
    """
    rows = [
        {"question_text": "The French colonial system was underlined by the policy of"},
        {"question_text": "The unrestrained power of the state over its citizens is underlined by"},
        {"question_text": "An underlined principle in the marketing of goods is that firms should"},
    ]
    assert repair.affected(rows) == []


def test_the_instructional_phrasings_in_the_bank_are_all_recognised():
    for question in [
        "Choose the option opposite in meaning to the underlined word(s). He is brave.",
        "Choose the option nearest in meaning to the word underlined. He is brave.",
        "Choose the option nearest in meaning to the underlined. He is brave.",
        "Choose the option with the same vowel sound as the letter(s) underlined. C ou p",
        "Choose the option nearest in meaning to the underlined world(S). He is brave.",
        "Choose the appropriate stress pattern. The syllables are underlined.",
    ]:
        assert repair.affected([{"question_text": question}]), question


def test_every_underline_tag_in_the_bank_is_closed():
    import csv

    path = Path(__file__).resolve().parents[2] / "data" / "questions.csv"
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    unbalanced = [
        r["question_id"] for r in rows
        if (r.get("question_text") or "").count("<u>") != (r.get("question_text") or "").count("</u>")
    ]
    assert unbalanced == []
