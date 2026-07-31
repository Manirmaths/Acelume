"""
Tests for figure-question replacement.

A generator that invents both the question and its answer cannot mark its own
homework. These tests pin the safeguards that make its output trustworthy:
anything ambiguous, malformed, or still dependent on a picture must be thrown
away rather than quietly shipped.
"""

import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import keying_core  # noqa: E402
import replace_figure_questions as rfq  # noqa: E402

GOOD = ('{"question": "Which structure on a woody stem allows gas exchange?",'
        ' "A": "lenticel", "B": "leaf scar", "C": "girdle scar", "D": "axillary bud",'
        ' "correct": "A", "topic": "Plant Biology", "explanation": "Lenticels are pores."}')

SRC = {"question_id": "BIO-J00001", "subject": "Biology",
       "question_text": "The part labelled 3 is the", "option_a": "leaf scar",
       "option_b": "lenticel", "option_c": "axillary bud", "option_d": "girdle scar"}


def test_parses_a_well_formed_generation():
    d = rfq.parse_generated(GOOD)
    assert d and d["correct"] == "A" and d["A"] == "lenticel"


@pytest.mark.parametrize("raw,why", [
    ("not json at all", "no JSON"),
    ('{"question": "x"}', "missing options"),
    ('{"question": "Which structure allows gas exchange in a woody stem?", "A": "a",'
     ' "B": "b", "C": "c", "D": "d", "correct": "E"}', "correct is not A-D"),
    ('{"question": "Which structure allows gas exchange in a woody stem?", "A": "same",'
     ' "B": "same", "C": "c", "D": "d", "correct": "A"}', "duplicate options"),
    ('{"question": "Short?", "A": "a", "B": "b", "C": "c", "D": "d", "correct": "A"}',
     "stem too short"),
    ('{"question": "Which structure allows gas exchange in a woody stem?", "A": "a",'
     ' "B": "b", "C": "", "D": "d", "correct": "A"}', "empty option"),
])
def test_rejects_malformed_generations(raw, why):
    assert rfq.parse_generated(raw) is None, f"should have rejected: {why}"


@pytest.mark.parametrize("stem", [
    "In the diagram above, which part is the lenticel?",
    "The part labelled 3 in the figure is the",
    "From the table above, what is the total?",
    "Which structure is shown above on the woody stem?",
])
def test_rejects_replacements_that_still_need_a_picture(stem):
    """The entire purpose is to remove the dependency. A replacement that still
    says 'the diagram above' is worse than the original -- it looks answerable."""
    raw = ('{"question": "%s", "A": "aa", "B": "bb", "C": "cc", "D": "dd",'
           ' "correct": "A"}' % stem)
    assert rfq.parse_generated(raw) is None


def test_kept_only_when_an_independent_solver_agrees(monkeypatch):
    def fake(prompt, **kw):
        if "Write ONE new multiple-choice question" in prompt:
            return GOOD
        # Solver: pick whichever letter carries "lenticel" in THIS prompt.
        letters = {}
        for line in prompt.splitlines():
            s = line.strip()
            if len(s) > 3 and s[0] in "ABCD" and s[1] == ".":
                letters[s[3:].strip()] = s[0]
        L = letters.get("lenticel", "A")
        return f"REASON: gas exchange.\nANSWER: {L}" if "REASON:" in prompt else L

    monkeypatch.setattr(keying_core, "call_model", fake)
    monkeypatch.setattr(rfq, "call_model", fake)
    out = rfq.make_one(SRC, model="m", api_key="k")
    assert out["ok"] is True
    assert out["correct"] == "A"


def test_discarded_when_the_solver_disagrees(monkeypatch):
    """The generator claims A. A fresh solver reading the same question says B.
    One of them is wrong and we cannot tell which, so it must not ship."""
    def fake(prompt, **kw):
        if "Write ONE new multiple-choice question" in prompt:
            return GOOD
        letters = {}
        for line in prompt.splitlines():
            s = line.strip()
            if len(s) > 3 and s[0] in "ABCD" and s[1] == ".":
                letters[s[3:].strip()] = s[0]
        L = letters.get("leaf scar", "B")      # deliberately not the intended answer
        return f"REASON: nope.\nANSWER: {L}" if "REASON:" in prompt else L

    monkeypatch.setattr(keying_core, "call_model", fake)
    monkeypatch.setattr(rfq, "call_model", fake)
    out = rfq.make_one(SRC, model="m", api_key="k")
    assert out["ok"] is False
    assert "generator meant" in out["note"]


def test_discarded_when_the_two_solver_passes_cannot_agree(monkeypatch):
    calls = {"n": 0}

    def fake(prompt, **kw):
        if "Write ONE new multiple-choice question" in prompt:
            return GOOD
        calls["n"] += 1
        return "A" if calls["n"] == 1 else "REASON: unsure.\nANSWER: C"

    monkeypatch.setattr(keying_core, "call_model", fake)
    monkeypatch.setattr(rfq, "call_model", fake)
    out = rfq.make_one(SRC, model="m", api_key="k")
    assert out["ok"] is False
    assert "solver undecided" in out["note"]


def test_unusable_generation_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(rfq, "call_model", lambda *a, **k: "sorry, I cannot")
    out = rfq.make_one(SRC, model="m", api_key="k")
    assert out["ok"] is False and out["note"] == "unusable generation"
