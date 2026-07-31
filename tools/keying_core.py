"""
Shared machinery for deciding a multiple-choice answer with a language model.

The design exists to answer one question: how do you use a model that is about
91% accurate on this material to produce an answer bank you are willing to put
in front of a student sitting JAMB?

You cannot, if you publish everything it says. 9% of ~7,000 questions is over
600 confidently-wrong keys, each with a fluent explanation justifying it, and
the student has no way to detect any of them -- the app is the authority.

So this module does not try to be right more often. It tries to KNOW WHEN IT IS
UNSURE, and refuses to publish those:

  Pass A   answer cold, letter only, no reasoning.
  Pass B   answer again, independently, with the options SHUFFLED and
           relabelled, and with reasoning required.
  Gate     publish only if both passes name the same option TEXT.

The shuffle is the load-bearing part. Two identical prompts to the same model
produce correlated errors -- asking twice tells you almost nothing. Changing
which letter carries which option breaks position bias, so the two passes fail
in different ways, and a disagreement becomes real evidence of difficulty.
Measured on ground truth, the gate is what converts "91% accurate" into
"~97% accurate on a smaller published subset, with the rest queued for review".

Nothing here writes a key directly. Callers decide what to do with a verdict.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

LETTERS = ("A", "B", "C", "D")

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Bump whenever a prompt below changes. It is part of the checkpoint filename,
# so old results cannot be silently resumed under new prompts. Without this,
# fixing pass A would have left 2025 Mathematics permanently holding the numbers
# produced by the broken version.
#   v1 -> v2: pass A given room to reason; passes now differ by method, not
#             capability, after pass A scored 1/21 on maths it could not compute.
PROMPT_VERSION = "v2"

# The two passes differ in METHOD, not in capability.
#
# The first version of pass A allowed no reasoning at all -- one letter, eight
# tokens. That is fine for factual recall but hopeless for anything requiring
# working: on the 2025 Mathematics batch, pass A was right once out of the 21
# questions the gate could not settle, while pass B was right sixteen times.
# Pass A was not providing a second opinion, it was providing noise, and 38% of
# Mathematics went undecided as a result.
#
# Crippling one pass does not decorrelate errors, it just adds variance. What
# decorrelates errors is asking the same competent model to reach the answer by
# a DIFFERENT ROUTE -- solve-directly versus eliminate-the-wrong-ones -- over a
# different option order.

# Pass A: solve it forwards.
PROMPT_A = """Answer this Nigerian JAMB {subject} examination question.

Work it out directly: recall the relevant fact or do the calculation, then pick
the option that matches. Keep any working to two lines.

End with the answer on its own final line, exactly:
ANSWER: <a single letter A, B, C or D>

Question: {stem}
A. {A}
B. {B}
C. {C}
D. {D}"""

# Pass B: reach it backwards, by elimination, over a different option order.
PROMPT_B = """You are a Nigerian secondary school {subject} teacher marking a JAMB
past question. Do NOT solve it directly. Instead take each option in turn and
rule out the ones that cannot be right, then keep what survives.

Answer in this exact format:
REASON: <one or two sentences, saying what you eliminated and why>
ANSWER: <a single letter A, B, C or D>

Question: {stem}
A. {A}
B. {B}
C. {C}
D. {D}"""

PROMPT_EXPLAIN = """You are writing the explanation a Nigerian student sees after
answering a JAMB past question. The correct answer has already been established
as {letter}: "{answer_text}". Explain why it is correct in 1-3 sentences.

Rules:
- Explain the reasoning, do not merely restate the option.
- If a common wrong option is tempting, say briefly why it is wrong.
- Plain prose. No markdown, no headings, no bullet points.
- Write for a 16-18 year old preparing for JAMB.

Subject: {subject}
Question: {stem}
A. {A}
B. {B}
C. {C}
D. {D}"""


class ModelError(RuntimeError):
    pass


@dataclass
class Verdict:
    """The outcome for one question. `accepted` is the only publishable state."""
    question_id: str
    accepted: bool
    letter: str | None            # settled answer in the ORIGINAL lettering
    pass_a: str | None
    pass_b: str | None            # already mapped back to original lettering
    reason: str = ""
    explanation: str = ""
    note: str = ""
    # A third-pass guess used ONLY to give a human reviewer a starting point on
    # questions the gate rejected. Measured on ground truth, the two passes
    # between them held the right answer 12 times out of 14 -- but a tie broken
    # by majority vote lands near 70% correct, nowhere near the ~95% the gate
    # achieves. So this is a suggestion in the review file and never a key.
    suggestion: str | None = None
    meta: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Option shuffling.
#
# This is the highest-risk code in the pipeline: a mistake mapping a shuffled
# letter back to the original produces keys that are wrong SYSTEMATICALLY and
# silently, which is far worse than a model that is merely fallible. It is pure
# and separately tested in tests/test_keying_core.py for that reason.
# --------------------------------------------------------------------------

def shuffle_options(options: dict[str, str], seed: str) -> tuple[dict[str, str], dict[str, str]]:
    """
    Return (shuffled options, map from shuffled letter -> original letter).

    Seeded by question id so a re-run reproduces the same permutation and the
    checkpoint stays meaningful.
    """
    items = [(k, options[k]) for k in LETTERS]
    rng = random.Random(seed)
    rng.shuffle(items)
    shuffled = {LETTERS[i]: text for i, (_orig, text) in enumerate(items)}
    back = {LETTERS[i]: orig for i, (orig, _text) in enumerate(items)}
    return shuffled, back


def parse_letter(raw: str) -> str | None:
    """Pull a single answer letter out of a model reply, or None."""
    if not raw:
        return None
    m = re.search(r"ANSWER:\s*\(?([A-D])\b", raw, re.I)
    if m:
        return m.group(1).upper()
    stripped = raw.strip()
    if len(stripped) == 1 and stripped.upper() in LETTERS:
        return stripped.upper()
    # A bare letter on its own line, e.g. "B." or "(C)".
    m = re.search(r"^\s*\(?([A-D])\)?[.:]?\s*$", stripped, re.M)
    return m.group(1).upper() if m else None


def parse_reason(raw: str) -> str:
    m = re.search(r"REASON:\s*(.+?)(?:\n\s*ANSWER:|$)", raw or "", re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


# --------------------------------------------------------------------------
# Model transport
# --------------------------------------------------------------------------

def call_model(prompt: str, *, model: str, api_key: str, temperature: float = 0.0,
               max_tokens: int = 300, retries: int = 4) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            OPENAI_URL, data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            last = e
            # 429/5xx are transient; anything else will not improve with retries.
            if e.code not in (429, 500, 502, 503, 504):
                raise ModelError(f"{e.code} {e.read()[:200]!r}") from e
            time.sleep(min(2 ** attempt, 20))
        except Exception as e:                       # noqa: BLE001 -- network
            last = e
            time.sleep(min(2 ** attempt, 20))
    raise ModelError(f"gave up after {retries} attempts: {last}")


def decide(question: dict, *, model: str, api_key: str, explain: bool = True,
           suggest_on_conflict: bool = False) -> Verdict:
    """
    Run both passes over one question and return a Verdict.

    `question` needs: question_id, subject, question_text, option_a..option_d.
    """
    qid = question["question_id"]
    opts = {L: question[f"option_{L.lower()}"] for L in LETTERS}
    base = {"subject": question.get("subject", ""), "stem": question["question_text"], **opts}

    # Enough room to actually compute. See the note above PROMPT_A.
    a_raw = call_model(PROMPT_A.format(**base), model=model, api_key=api_key, max_tokens=300)
    a = parse_letter(a_raw)

    shuffled, back = shuffle_options(opts, seed=qid)
    b_raw = call_model(
        PROMPT_B.format(subject=base["subject"], stem=base["stem"], **shuffled),
        model=model, api_key=api_key, max_tokens=300,
    )
    b_shuffled = parse_letter(b_raw)
    # Map back BEFORE comparing. Comparing shuffled letters would be nonsense.
    b = back.get(b_shuffled) if b_shuffled else None

    if a is None or b is None:
        return Verdict(qid, False, None, a, b, parse_reason(b_raw),
                       note="unparseable reply from one pass")
    if a != b:
        v = Verdict(qid, False, None, a, b, parse_reason(b_raw), note="passes disagreed")
        if suggest_on_conflict:
            # Third opinion, shuffled differently again, purely to seed the
            # review queue. It does NOT make the verdict publishable.
            shuffled_c, back_c = shuffle_options(opts, seed=qid + ":tiebreak")
            c_raw = call_model(
                PROMPT_B.format(subject=base["subject"], stem=base["stem"], **shuffled_c),
                model=model, api_key=api_key, max_tokens=300,
            )
            c = parse_letter(c_raw)
            c = back_c.get(c) if c else None
            v.suggestion = c if c in (a, b) else None
        return v

    v = Verdict(qid, True, a, a, b, parse_reason(b_raw))
    if explain:
        v.explanation = re.sub(r"\s+", " ", call_model(
            PROMPT_EXPLAIN.format(letter=a, answer_text=opts[a], **base),
            model=model, api_key=api_key, max_tokens=220,
        )).strip()
    return v


def api_key_from_env() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "OPENAI_API_KEY is not set.\n"
            "  PowerShell:  $env:OPENAI_API_KEY = 'sk-...'\n"
            "Use a strong model. On the ground-truth sample a small/cheap model\n"
            "scores far below the ~91% this pipeline was measured against, and\n"
            "the agreement gate cannot rescue a model that is confidently wrong."
        )
    return key
