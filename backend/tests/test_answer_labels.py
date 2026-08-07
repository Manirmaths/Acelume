"""
Named mistake types.

The single most valuable behaviour here is telling SLIP apart from GAP. To a
student both are a red cross, but one means "you know this, read it again"
and the other means "you have not been taught this yet". Getting that backwards
would send a confused student to a lesson they have already done, or leave a
genuine knowledge gap looking like carelessness.

The second most valuable behaviour is refusing to guess: without timing there
is no Lucky or Blunder, and without a rating there is no Sharp. A label the
student cannot trust is worse than no label, because the whole point is to
give them a word they can rely on.
"""

from app.answer_labels import accuracy, classify, headline


def label_for(**kwargs):
    base = dict(
        is_correct=True,
        answered=True,
        question_rating=1200.0,
        student_rating=1200.0,
        topic_state="mastered",
        answer_seconds=30,
        average_seconds=30.0,
    )
    base.update(kwargs)
    result = classify(**base)
    return result.key if result else None


# ---------------------------------------------------------- slip vs gap ----

def test_wrong_on_a_mastered_topic_is_a_slip():
    assert label_for(is_correct=False, topic_state="mastered") == "slip"


def test_wrong_on_a_proficient_topic_is_a_slip():
    assert label_for(is_correct=False, topic_state="proficient") == "slip"


def test_wrong_on_an_unlearned_topic_is_a_gap():
    assert label_for(is_correct=False, topic_state="available") == "gap"


def test_wrong_on_a_topic_with_no_mastery_record_is_a_gap():
    assert label_for(is_correct=False, topic_state=None) == "gap"


def test_a_topic_due_for_review_still_counts_as_known():
    """Review being due means it was learned, not that it was forgotten."""
    assert label_for(is_correct=False, topic_state="review_due") == "slip"


# --------------------------------------------------------------- others ----

def test_correct_on_a_much_harder_question_is_sharp():
    assert label_for(question_rating=1500.0, student_rating=1200.0) == "sharp"


def test_correct_at_your_own_level_is_solid():
    assert label_for(question_rating=1200.0, student_rating=1200.0) == "solid"


def test_correct_but_far_slower_than_usual_is_lucky():
    assert label_for(answer_seconds=90, average_seconds=30.0) == "lucky"


def test_correct_on_an_unlearned_topic_is_lucky():
    """Right answer, topic never taught -- do not bank it."""
    assert label_for(is_correct=True, topic_state="available") == "lucky"


def test_wrong_fast_and_easy_is_a_blunder():
    assert label_for(
        is_correct=False, answer_seconds=3, question_rating=900.0, topic_state="mastered"
    ) == "blunder"


def test_a_blunder_outranks_a_slip():
    """Answering in 3 seconds is a reading problem, not a knowledge one."""
    assert label_for(
        is_correct=False, answer_seconds=2, question_rating=850.0, topic_state="mastered"
    ) == "blunder"


def test_wrong_slowly_on_an_easy_question_is_not_a_blunder():
    assert label_for(
        is_correct=False, answer_seconds=120, question_rating=900.0, topic_state="mastered"
    ) == "slip"


def test_wrong_fast_on_a_hard_question_is_not_a_blunder():
    """Giving up quickly on something genuinely hard is not carelessness."""
    assert label_for(
        is_correct=False, answer_seconds=2, question_rating=1600.0, topic_state="available"
    ) == "gap"


# ------------------------------------------------------- refuses to guess ----

def test_an_unanswered_question_gets_no_label():
    """Running out of time is not a mistake and must not be labelled as one."""
    assert label_for(answered=False, is_correct=False) is None


def test_without_timing_it_never_says_blunder():
    assert label_for(
        is_correct=False, answer_seconds=None, question_rating=900.0, topic_state="mastered"
    ) == "slip"


def test_without_timing_it_never_says_lucky_on_speed_alone():
    assert label_for(answer_seconds=None, average_seconds=None, topic_state="mastered") == "solid"


def test_without_a_student_rating_it_never_says_sharp():
    assert label_for(question_rating=1900.0, student_rating=None, topic_state="mastered") == "solid"


# -------------------------------------------------------------- accuracy ----

def test_accuracy_is_not_the_same_as_percent_correct():
    """
    Nine right out of twelve should not read the same when three of them were
    lucky guesses. If these came out equal the score would carry no more
    information than the fraction it replaced.
    """
    clean = accuracy({"solid": 9, "gap": 3}, answered=12)
    lucky = accuracy({"solid": 6, "lucky": 3, "gap": 3}, answered=12)
    assert clean > lucky


def test_a_perfect_clean_attempt_scores_100():
    assert accuracy({"solid": 10}, answered=10) == 100


def test_beating_questions_above_your_level_scores_above_par():
    assert accuracy({"sharp": 10}, answered=10) == 100


def test_all_wrong_scores_zero():
    assert accuracy({"gap": 5, "slip": 3, "blunder": 2}, answered=10) == 0


def test_accuracy_is_none_with_nothing_answered():
    assert accuracy({}, answered=0) is None


def test_accuracy_is_bounded():
    assert 0 <= accuracy({"sharp": 20}, answered=20) <= 100


# -------------------------------------------------------------- headline ----

def test_a_slip_is_reported_ahead_of_everything_else():
    """The most surprising and most fixable finding leads."""
    text = headline({"slip": 1, "gap": 4, "blunder": 2, "lucky": 3})
    assert "slip" in text.lower()


def test_headline_pluralises():
    assert "slips" in headline({"slip": 2}).lower()
    assert "slips" not in headline({"slip": 1}).lower()


def test_a_flawless_attempt_has_no_complaint():
    assert headline({"solid": 10}) is None


def test_beating_harder_questions_is_worth_saying():
    assert "above your level" in headline({"sharp": 2, "solid": 8}).lower()
