"""
End-to-end tests for the keying pipeline, using a stub model.

These do not check whether the model is clever. They check the properties that
decide whether a wrong key can reach a student:

  - a disagreement between the two passes is never published
  - a garbled reply is never published
  - agreement in shuffled space maps back to the right ORIGINAL letter
  - a resumed run does not re-decide, or lose, anything

The stub answers by option TEXT, so it is indifferent to the shuffle. That is
what makes it a fair test of the mapping: if map-back were broken, a stub that
always picks the same text would still produce the wrong letter.
"""

import json
import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import answer_keys  # noqa: E402
import keying_core  # noqa: E402


def make_q(qid, correct_text):
    return {"question_id": qid, "subject": "Government",
            "question_text": f"Question {qid}?",
            "option_a": "alpha", "option_b": "bravo",
            "option_c": "charlie", "option_d": "delta",
            "_correct_text": correct_text}


def stub(*, picks_text, disagree_on=(), garbled_on=()):
    """A fake model that answers by option text."""
    def _call(prompt, **kw):
        qid = None
        for line in prompt.splitlines():
            if line.startswith("Question:") or line.startswith("Question "):
                qid = line
        if "Explain why it is correct" in prompt:
            return "Because that is how it works."
        # Which letter carries the target text IN THIS PROMPT.
        letters = {}
        for line in prompt.splitlines():
            s = line.strip()
            if len(s) > 3 and s[0] in "ABCD" and s[1] == ".":
                letters[s[3:].strip()] = s[0]
        target = picks_text
        if any(d in (qid or "") for d in disagree_on) and "REASON:" in prompt:
            target = "delta" if picks_text != "delta" else "alpha"
        if any(g in (qid or "") for g in garbled_on) and "REASON:" in prompt:
            return "I could not decide, it depends."
        letter = letters.get(target, "A")
        return f"REASON: because.\nANSWER: {letter}" if "REASON:" in prompt else letter
    return _call


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(keying_core, "call_model",
                        lambda *a, **k: pytest.fail("test hit the network"))


def test_agreement_publishes_the_correct_original_letter(monkeypatch):
    """The stub always picks 'charlie'. Pass B sees a shuffled prompt, so it
    replies with a different letter -- which must map back to C."""
    monkeypatch.setattr(keying_core, "call_model", stub(picks_text="charlie"))
    v = keying_core.decide(make_q("GOV-1", "charlie"), model="m", api_key="k")
    assert v.accepted is True
    assert v.letter == "C", "map-back produced the wrong original letter"
    assert v.explanation


def test_disagreement_is_never_published(monkeypatch):
    monkeypatch.setattr(keying_core, "call_model",
                        stub(picks_text="charlie", disagree_on=["GOV-2"]))
    v = keying_core.decide(make_q("GOV-2", "charlie"), model="m", api_key="k")
    assert v.accepted is False
    assert v.letter is None
    assert v.note == "passes disagreed"
    assert v.explanation == "", "an unpublished verdict must not carry an explanation"


def test_garbled_reply_is_never_published(monkeypatch):
    monkeypatch.setattr(keying_core, "call_model",
                        stub(picks_text="charlie", garbled_on=["GOV-3"]))
    v = keying_core.decide(make_q("GOV-3", "charlie"), model="m", api_key="k")
    assert v.accepted is False
    assert v.letter is None
    assert "unparseable" in v.note


def test_explanation_is_only_requested_after_the_answer_settles(monkeypatch):
    """The explainer is told the settled answer so it explains rather than
    rationalises -- and must never run for a rejected verdict."""
    calls = []

    def counting(prompt, **kw):
        calls.append("explain" if "Explain why it is correct" in prompt else "answer")
        return stub(picks_text="charlie", disagree_on=["GOV-4"])(prompt, **kw)

    monkeypatch.setattr(keying_core, "call_model", counting)
    keying_core.decide(make_q("GOV-4", "charlie"), model="m", api_key="k")
    assert "explain" not in calls


def test_run_is_resumable_and_does_not_redecide(monkeypatch, tmp_path):
    monkeypatch.setattr(keying_core, "call_model", stub(picks_text="charlie"))
    rows = [make_q(f"GOV-{i}", "charlie") for i in range(5)]
    prog = tmp_path / "p.jsonl"

    first = answer_keys.run(rows[:3], model="m", api_key="k", workers=1, progress_path=prog)
    assert len(first) == 3

    seen = []
    def watched(prompt, **kw):
        seen.append(prompt)
        return stub(picks_text="charlie")(prompt, **kw)
    monkeypatch.setattr(keying_core, "call_model", watched)

    second = answer_keys.run(rows, model="m", api_key="k", workers=1, progress_path=prog)
    assert len(second) == 5, "resumed run lost earlier decisions"
    decided_again = {json.loads(l)["question_id"] for l in prog.read_text().splitlines() if l.strip()}
    assert decided_again == {f"GOV-{i}" for i in range(5)}
    assert all("GOV-0?" not in p for p in seen), "re-decided a question already done"


def test_every_option_position_round_trips(monkeypatch):
    """Run the whole decide() path for each correct position, so a mapping bug
    cannot hide behind one lucky permutation."""
    for want_letter, text in zip("ABCD", ["alpha", "bravo", "charlie", "delta"]):
        monkeypatch.setattr(keying_core, "call_model", stub(picks_text=text))
        v = keying_core.decide(make_q(f"GOV-pos-{want_letter}", text), model="m", api_key="k")
        assert v.accepted and v.letter == want_letter, f"{text} should map to {want_letter}"
