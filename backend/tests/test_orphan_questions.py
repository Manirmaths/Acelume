"""
Tests for orphan-question detection.

The failure this guards against is not a wrong answer. It is a question that
CANNOT be answered, by anyone, because the text it refers to was never imported.
A student meets "Who instructed the Chemistry teacher to conclude the assembly?"
with no passage, guesses, gets it wrong, receives no explanation, and concludes
they are bad at comprehension. 192 of those were live.

The detector must be precise in both directions: quarantining a perfectly good
question removes real practice material.
"""

import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

from quarantine_orphan_questions import is_orphan  # noqa: E402

KNOWN = {"ENG-P001", "GEO-P002"}


def q(**kw):
    base = {"topic": "Lexis and Structure", "passage_id": "", "status": "active",
            "question_text": "Choose the word nearest in meaning to 'candid'."}
    base.update(kw)
    return base


def test_comprehension_without_a_passage_is_an_orphan():
    r = q(topic="Reading Comprehension",
          question_text="Who instructed the Chemistry teacher to conclude the assembly?")
    assert is_orphan(r, KNOWN)


def test_cloze_without_a_passage_is_an_orphan():
    assert is_orphan(q(topic="Cloze Test"), KNOWN)


def test_comprehension_with_a_real_passage_is_fine():
    assert not is_orphan(q(topic="Reading Comprehension", passage_id="ENG-P001"), KNOWN)


def test_comprehension_pointing_at_a_missing_passage_is_an_orphan():
    """A dangling reference is as broken as no reference, and easier to miss."""
    why = is_orphan(q(topic="Reading Comprehension", passage_id="ENG-P999"), KNOWN)
    assert why and "not found" in why


def test_a_self_contained_question_is_never_flagged():
    """Precision matters: over-flagging deletes good practice material."""
    assert not is_orphan(q(), KNOWN)
    assert not is_orphan(q(topic="Oral English"), KNOWN)
    assert not is_orphan(q(topic="Algebraic Processes",
                           question_text="Solve for x: x^2 - 5x + 6 = 0"), KNOWN)


def test_any_topic_with_a_dangling_passage_id_is_flagged():
    """Not just comprehension -- any question pointing at a passage that does
    not exist is showing the student an incomplete question."""
    assert is_orphan(q(topic="Population and Settlement", passage_id="GEO-P404"), KNOWN)
    assert not is_orphan(q(topic="Population and Settlement", passage_id="GEO-P002"), KNOWN)


def test_no_passages_imported_at_all_flags_every_comprehension_question():
    """The real state of the bank: passages.csv had two rows for 194 questions."""
    assert is_orphan(q(topic="Reading Comprehension", passage_id="ENG-P001"), set())
