"""
Restore the underlining that was stripped out of English questions at import.

THE BUG
-------
Around 950 English questions instruct the candidate to consider "the underlined
word" or "the underlined letters", but the markup that said WHICH word or which
letters never survived the import. The student is told to look at something
that isn't marked.

For the phonetics questions the damage is visible in the text itself: the
scraper turned `C<u>ou</u>p` into `C ou p`. For vocabulary questions the
underline simply vanished.

THE REPAIR
----------
The explanation column is the oracle. It almost always names the target:

    "'Redundant' means unnecessary/superfluous; its opposite is 'necessary'."
    "The 'ie' in 'reprieve' has the long /iː/ sound, matching 'police'."
    "Moribund means dying or on the point of collapse..."

So the target word can be read out of the explanation and marked up in the
question. Every rule here is CONFIRMED against the explanation before it fires
-- a guess that happens to match a stopword would mark the wrong word, and a
question that underlines the wrong word is worse than one that underlines
nothing, because the student cannot tell it is broken.

Anything that cannot be confirmed is reported, never guessed at.

Usage:
    python scripts/repair_underlines.py            # report only
    python scripts/repair_underlines.py --apply    # rewrite data/questions.csv
"""

from __future__ import annotations

import argparse
import csv
import difflib
import re
import sys
from collections import Counter
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "questions.csv"

QUOTED = re.compile(r"['‘“\"]([^'’”\"]{2,60})['’”\"]")
LEAD_WORD = re.compile(r"^(?:An?|The)\s+([A-Za-z][A-Za-z'-]{3,})|^([A-Za-z][A-Za-z'-]{3,})", re.I)
# The question must INSTRUCT the candidate about an underline, not merely use
# the word. "The French colonial system was underlined by the policy of..." is
# a perfectly good Government question and must never be touched.
SAYS_UNDERLINED = re.compile(
    # "world" is a typo for "word" that recurs across a whole batch of imported
    # questions. Matching it costs nothing and recovers five real questions.
    r"underlined?\s*[.:]?\s*(?:word|world|letter|part|portion|phrase|expression|group|option|syllable)"
    r"|(?:word|world|letter|part|portion|phrase|expression|group|syllable)\s*\(?s?\)?\s*"
    r"(?:is\s+|are\s+)?(?:in\s+)?underlined?"
    # "...nearest in meaning to the underlined. The essay topic is nebulous" --
    # the instruction is elliptical, but the punctuation after "underlined"
    # marks it as one. Ordinary prose ("was underlined by the policy") does not
    # punctuate there.
    r"|underlined\s*[.:?]"
    r"|underlined\s*$",
    re.I,
)
HAS_MARKUP = re.compile(r"</?u>|</?b>|</?i>", re.I)
PHONETICS = re.compile(r"\bsounds?\b|\bletters?\b|\bvowel\b|\bconsonant\b", re.I)

# A term this common tells us nothing about which word was underlined. Marking
# up "the" would be worse than leaving the question alone.
STOPWORDS = {
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "is", "are",
    "was", "were", "in", "on", "at", "of", "to", "for", "and", "or", "but", "with",
    "his", "her", "their", "our", "your", "my", "he", "she", "they", "we", "you",
    "option", "options", "word", "words", "letter", "letters", "sound", "sounds",
    "sentence", "phrase", "answer", "correct", "means", "meaning", "opposite",
    "nearest", "same", "vowel", "consonant", "pronounced", "matching", "here",
    "there", "which", "what", "when", "note", "intended", "context", "first",
    "second", "third", "initial", "final",
}


def quoted_terms(explanation: str) -> list[str]:
    """Candidate target words, most trustworthy first."""
    out = [m.group(1).strip() for m in QUOTED.finditer(explanation)]
    lead = LEAD_WORD.match(explanation.strip())
    if lead:
        out.append((lead.group(1) or lead.group(2) or "").strip())
    return [t for t in out if t and t.lower() not in STOPWORDS and len(t) >= 3]


def sentence_of(question: str) -> tuple[str, int]:
    """
    The part of the question the underline belongs in, and where it starts.

    Everything up to and including the last "underlin..." is instruction; the
    target is always after it. Searching the whole string would let the rule
    mark a word inside "the underlined word" itself.
    """
    match = None
    for match in re.finditer(r"underlin\w*", question, re.I):
        pass
    if match is None:
        return question, 0
    return question[match.end():], match.end()


def _wrap(question: str, offset: int, start: int, end: int) -> str:
    absolute = offset + start
    stop = offset + end
    return f"{question[:absolute]}<u>{question[absolute:stop]}</u>{question[stop:]}"


def by_exact_term(question: str, explanation: str) -> str | None:
    """The explanation names the word and it appears verbatim in the sentence."""
    tail, offset = sentence_of(question)
    for term in quoted_terms(explanation):
        hit = re.search(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", tail, re.I)
        if hit:
            return _wrap(question, offset, hit.start(), hit.end())
    return None


def by_rejoining(question: str, explanation: str) -> str | None:
    """
    A word the scraper split across the underline boundary: `greedies t` was
    `<u>greediest</u>`, `unificatio n` was `<u>unification</u>`.

    Distinct from `by_spacing`, where only PART of the word was underlined.
    Here the whole word was, and the space is pure damage. Only fires when the
    rejoined word is one the explanation names, so a genuine two-word sequence
    is never glued together.

    Never applied to phonetics questions: there the space marks the edge of the
    underline rather than damage to it, and gluing `R oa red` into one
    underlined lump loses exactly the information being restored.
    """
    if PHONETICS.search(question):
        return None

    tail, offset = sentence_of(question)
    chunks = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[A-Za-z]+", tail)]
    wanted = {t.lower().replace(" ", "") for t in quoted_terms(explanation) if len(t) >= 5}
    if not wanted:
        return None

    for i in range(len(chunks) - 1):
        for j in (i + 2, i + 3):
            if j > len(chunks):
                continue
            span = chunks[i:j]
            # Only adjacent chunks separated by a single space count.
            if any(tail[span[k][2]:span[k + 1][1]] != " " for k in range(len(span) - 1)):
                continue
            joined = "".join(c[0] for c in span)
            if len(joined) >= 5 and joined.lower() in wanted:
                start, end = offset + span[0][1], offset + span[-1][2]
                # Rejoined, not merely wrapped -- the stray space goes too.
                return f"{question[:start]}<u>{joined}</u>{question[end:]}"
    return None


def by_close_term(question: str, explanation: str) -> str | None:
    """
    Inflection only: the explanation says 'impasse', the sentence says
    'impasses'.

    Deliberately NOT applied to phonetics questions. There the target is a
    fragment of a word rather than a word, and fuzzy matching cheerfully
    underlines 'table' inside 'p o table' or 'ought' inside 'Th ought' -- both
    the wrong half. Those are left to `by_spacing`, which confirms itself, or
    to the residual.
    """
    if PHONETICS.search(question):
        return None

    tail, offset = sentence_of(question)
    words = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[A-Za-z][A-Za-z'-]{3,}", tail)]
    if not words:
        return None
    lowered = [w[0].lower() for w in words]
    for term in quoted_terms(explanation):
        if " " in term:
            continue
        close = difflib.get_close_matches(term.lower(), lowered, n=1, cutoff=0.82)
        if close:
            _, start, end = words[lowered.index(close[0])]
            return _wrap(question, offset, start, end)
    return None


def by_spacing(question: str, explanation: str) -> str | None:
    """
    Phonetics questions where the scraper left a space either side of the
    underline: `C ou p` was `C<u>ou</u>p`.

    Confirmed two ways before firing: the chunks must rejoin into a word the
    explanation mentions, AND the explanation must quote the chunk that was
    underlined. Without both, an ordinary sentence ending in three short words
    ("for the goods") would be mangled into a nonsense word.
    """
    if not PHONETICS.search(question):
        return None

    tail, offset = sentence_of(question)
    run = re.search(r"(?<![\w'])([A-Za-z]{1,8}(?: [A-Za-z]{1,8}){1,4})\s*['\"]*\s*[.?!]*\s*$", tail.strip())
    if not run:
        return None

    # Re-find the run in the untrimmed tail so offsets stay true.
    located = re.search(re.escape(run.group(1)), tail)
    if not located:
        return None

    chunks = run.group(1).split(" ")
    joined = "".join(chunks).lower()
    if len(chunks) < 2 or len(joined) < 3:
        return None
    if not re.search(r"(?<![\w-])" + re.escape(joined) + r"(?![\w-])", explanation, re.I):
        return None

    marked = [c for c in chunks if re.search(r"['‘“\"]" + re.escape(c) + r"['’”\"]", explanation, re.I)]
    if len(marked) == 1:
        index = chunks.index(marked[0])
    elif len(chunks) >= 3:
        # Three chunks means the scraper left a boundary on BOTH sides of the
        # underline -- `C ou p` can only have been `C<u>ou</u>p`. Two chunks is
        # ambiguous (prefix or suffix?) and is left alone unless the
        # explanation says which.
        index = 1 if len(chunks) == 3 else None
        if index is None:
            return None
    else:
        return None

    target = chunks[index]
    rebuilt = "".join(chunks[:index]) + f"<u>{target}</u>" + "".join(chunks[index + 1:])

    start = offset + located.start()
    end = offset + located.end()
    return question[:start] + rebuilt + question[end:]


RULES = (
    ("exact term from the explanation", by_exact_term),
    ("spacing left by the scraper", by_spacing),
    ("word split by a stray space", by_rejoining),
    ("close term (inflection)", by_close_term),
)


def repair(row: dict) -> tuple[str | None, str]:
    question = row.get("question_text") or ""
    explanation = (row.get("explanation") or "").strip()
    for name, rule in RULES:
        try:
            fixed = rule(question, explanation)
        except re.error:
            continue
        if fixed and fixed != question:
            return fixed, name
    return None, "no confirmable signal"


def affected(rows: list[dict]) -> list[dict]:
    return [
        r for r in rows
        if SAYS_UNDERLINED.search(r.get("question_text") or "")
        and not HAS_MARKUP.search(r.get("question_text") or "")
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="rewrite data/questions.csv")
    parser.add_argument(
        "--keep-unconfirmed",
        action="store_true",
        help="leave unrepairable questions active instead of moving them to draft",
    )
    parser.add_argument("--limit", type=int, default=12, help="samples to print")
    args = parser.parse_args()

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    targets = affected(rows)
    tally: Counter[str] = Counter()
    samples: list[tuple[str, str]] = []
    residual: list[dict] = []

    for row in targets:
        fixed, reason = repair(row)
        tally[reason] += 1
        if fixed:
            if len(samples) < args.limit:
                samples.append((row["question_text"], fixed))
            row["question_text"] = fixed
        else:
            residual.append(row)

    print(f"English questions referring to underlining, with no markup: {len(targets)}\n")
    for reason, count in tally.most_common():
        print(f"  {count:5d}  {reason}")

    print("\n--- samples ---")
    for before, after in samples:
        print(f"\n  before: {before[:150]}")
        print(f"  after : {after[:170]}")

    # A question telling a student to look at an underline that isn't there is
    # unanswerable, and an unanswerable question is in the same class as a
    # wrong answer key: worse than a missing question. `draft` is already
    # filtered out of practice, quizzes and exam papers, so this takes them out
    # of circulation without deleting work that can still be fixed by hand.
    quarantined = 0
    if not args.keep_unconfirmed:
        for row in residual:
            if row.get("status") == "active":
                row["status"] = "draft"
                quarantined += 1

    print(f"\n--- {len(residual)} could not be confirmed ---")
    print(f"    {quarantined} were active and move to draft"
          f"{' (dry run)' if not args.apply else ''}")
    for row in residual[: args.limit]:
        print(f"  {row['question_id']}: {(row['question_text'] or '')[:110]}")

    if not args.apply:
        print("\n(report only — pass --apply to write)")
        return 0

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
