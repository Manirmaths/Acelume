import csv
import pathlib
import sys

import pytest


TOOLS = pathlib.Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))

import batch_queue  # noqa: E402
import adjudicate_question_reviews as adjudicate  # noqa: E402
import classify_jamb_archive_topics as topics  # noqa: E402
import import_solved_jamb_archive as solved  # noqa: E402
import merge_keyed_questions  # noqa: E402
import promote_approved_archive_questions as promote  # noqa: E402
import repair_jamb_archive_metadata as metadata  # noqa: E402


def source_row(qid="BIO-J99999"):
    return {
        "question_id": qid,
        "exam_type": "JAMB",
        "subject": "Biology",
        "topic": "Ecology",
        "subtopic": "",
        "difficulty": "medium",
        "year": "1991",
        "passage_id": "",
        "question_text": "Which organelle releases energy?",
        "image_url": "",
        "option_a": "Nucleus",
        "option_b": "Mitochondrion",
        "option_c": "Ribosome",
        "option_d": "Vacuole",
        "correct_option": "",
        "explanation": "",
        "tags": "jamb-archive|needs-key",
        "source": "past-question",
        "status": "draft",
    }


def solved_record():
    row = source_row()
    return solved.SolvedQuestion(
        source_path="yearly/biology/jamb_biology_1991_answers_and_explanations.txt",
        number=1,
        year="1991",
        stem=row["question_text"],
        options=solved.row_options(row),
        answer_letter="B",
        answer_text="Mitochondrion",
        explanation="Mitochondria release usable energy during aerobic respiration.",
    )


def test_parser_preserves_latex_inside_supported_delimiters():
    text = r"""JAMB ECONOMICS 1991 — ANSWERS AND EXPLANATIONS
Source: example

1. Calculate elasticity.

A. 1
B. 2
C. 3
D. 4

Correct answer: A. 1
Explanation:
Use $E=\dfrac{\%\Delta Q}{\%\Delta P}$ and keep x\,y together.
"""
    records = solved.parse_solved_text(
        "x/yearly/economics/jamb_economics_1991_answers_and_explanations.txt",
        text,
    )
    assert len(records) == 1
    explanation = records[0].explanation
    assert r"\(E=\dfrac{\%\Delta Q}{\%\Delta P}\)" in explanation
    assert r"\," not in explanation
    assert r"\;" in explanation


def test_match_key_treats_equivalent_price_index_markup_as_equal():
    scraped = r"(frac{text{current price}}{text{base year price}}) x (frac{100}{1})"
    repaired = r"\(\frac{\text{current price}}{\text{base year price}} \times 100\)"
    assert solved.match_key(scraped) == solved.match_key(repaired)


def test_consensus_accepts_only_agreement_and_preserves_full_schema():
    row = source_row()
    record = solved_record()
    index = {solved.fingerprint(record.stem, record.options): record}
    agent = [{
        "question_id": row["question_id"],
        "correct_option": "B",
        "explanation": "The mitochondrion is the site of aerobic respiration.",
    }]

    keyed, review = solved.consensus_rows([row], agent, index, set())
    assert not review
    assert keyed[0]["correct_option"] == "B"
    assert keyed[0]["exam_type"] == "JAMB"
    assert keyed[0]["difficulty"] == "medium"
    assert keyed[0]["source"] == "past-question"
    assert keyed[0]["tags"] == "jamb-archive|consensus-keyed"

    agent[0]["correct_option"] = "A"
    keyed, review = solved.consensus_rows([row], agent, index, set())
    assert not keyed
    assert review[0]["correct_option"] == ""
    assert "independent pass chose A" in review[0]["explanation"]


def test_second_gate_holds_any_elimination_disagreement():
    row = source_row()
    row["correct_option"] = "B"
    row["explanation"] = "First-pass reasoning."
    row["tags"] = "jamb-archive|consensus-keyed"

    accepted, review = solved.second_gate(
        [row], [{"question_id": row["question_id"], "correct_option": "A"}]
    )
    assert not accepted
    assert review[0]["correct_option"] == ""
    assert "elimination pass chose A" in review[0]["explanation"]
    assert review[0]["tags"] == "jamb-archive|needs-key|review"


def test_metadata_repair_preserves_answer_explanation_and_status():
    original = source_row()
    bank = dict(original)
    bank.update({
        "exam_type": "", "difficulty": "", "tags": "", "source": "",
        "correct_option": "B", "explanation": "Hand-written reason.",
        "status": "draft",
    })

    repaired = metadata.repair_rows([bank], {original["question_id"]: original})
    assert repaired == [bank]
    assert bank["exam_type"] == "JAMB"
    assert bank["difficulty"] == "medium"
    assert bank["tags"] == "jamb-archive|hand-keyed"
    assert bank["correct_option"] == "B"
    assert bank["explanation"] == "Hand-written reason."
    assert bank["status"] == "draft"


def test_archive_topic_classifier_uses_canonical_topic_or_truthful_fallback():
    labelled = []
    for index in range(12):
        ecology = source_row(f"BIO-E{index:03d}")
        ecology.update({
            "topic": "Ecology and Environment",
            "question_text": "ecosystem habitat population food chain environment",
            "option_a": "community",
            "option_b": "habitat",
        })
        physiology = source_row(f"BIO-P{index:03d}")
        physiology.update({
            "topic": "Mammalian Physiology and Anatomy",
            "question_text": "heart kidney blood circulation mammal organ physiology",
            "option_a": "artery",
            "option_b": "nephron",
        })
        labelled.extend([ecology, physiology])

    model = topics.train(labelled)
    clear = source_row("BIO-J99998")
    clear.update({
        "topic": "",
        "question_text": "Which habitat contains this ecosystem food chain population?",
    })
    unclear = source_row("BIO-J99999")
    unclear.update({"topic": "", "question_text": "Choose the appropriate answer."})

    assert topics.accepted_topic(model, clear) == "Ecology and Environment"
    assert topics.accepted_topic(model, unclear) == topics.FALLBACK_TOPIC
    assert topics.is_archive_target(clear)
    topics.add_tag(clear, "topic-auto")
    topics.add_tag(clear, "topic-auto")
    assert clear["tags"].split("|").count("topic-auto") == 1


def test_adjudication_approves_resolved_rows_but_protects_missing_passages():
    review = source_row("BIO-J99997")
    review.update({
        "tags": "jamb-archive|needs-key|review",
        "explanation": "Earlier passes disagreed.",
    })
    approved, held = adjudicate.apply_decisions([review], [{
        "question_id": review["question_id"],
        "decision": "approve",
        "correct_option": "B",
        "explanation": "Mitochondria are the site of aerobic respiration.",
    }])
    assert not held
    assert approved[0]["correct_option"] == "B"
    assert approved[0]["status"] == "draft"
    assert "adjudicated-keyed" in approved[0]["tags"]
    assert "review" not in approved[0]["tags"]

    passage = source_row("ENG-J99997")
    passage.update({
        "subject": "English",
        "explanation": "The required passage is missing from the source CSV.",
    })
    with pytest.raises(SystemExit, match="source passage is missing"):
        adjudicate.apply_decisions([passage], [{
            "question_id": passage["question_id"],
            "decision": "approve",
            "correct_option": "A",
            "explanation": "Guess based on the options.",
        }])


def test_promotion_scope_and_passage_checks():
    row = source_row("BIO-J99996")
    row.update({
        "correct_option": "B",
        "explanation": "Mitochondria release usable energy.",
        "tags": "jamb-archive|consensus-keyed|topic-auto",
        "status": "draft",
    })
    assert promote.eligible(row)
    assert promote.blocked_reason(row, set()) == ""

    row["tags"] = "jamb-archive|hand-keyed|topic-auto"
    assert not promote.eligible(row)

    english = source_row("ENG-J99996")
    english.update({
        "subject": "English",
        "topic": "Reading Comprehension",
        "question_text": "According to the passage, what did the writer conclude?",
        "correct_option": "A",
        "explanation": "The writer states this directly.",
        "tags": "jamb-archive|consensus-keyed|topic-auto",
    })
    assert promote.blocked_reason(english, set()) == (
        "passage-dependent topic has no passage_id"
    )


def test_batch_queue_passes_explicit_safe_output_paths(monkeypatch, tmp_path):
    source = tmp_path / "key-1991-Biology.csv"
    captured = []
    monkeypatch.setattr(batch_queue, "BATCH_DIR", tmp_path)
    monkeypatch.setattr(batch_queue, "write_batch_csv", lambda batch: source)
    monkeypatch.setattr(batch_queue.subprocess, "call", lambda command: captured.append(command) or 0)

    batch = {"id": "key-1991-Biology", "kind": "key", "count": 39}
    assert batch_queue.run_batch(batch, model="gpt-4o", workers=4, apply=True) == 0
    command = captured[0]
    assert command[command.index("--out") + 1].endswith("key-1991-Biology_keyed.csv")
    assert command[command.index("--review-out") + 1].endswith(
        "key-1991-Biology_needs_review.csv"
    )


def test_merge_rejects_reduced_schema(monkeypatch, tmp_path):
    bank_path = tmp_path / "questions.csv"
    incoming_path = tmp_path / "keyed.csv"
    bank_row = source_row("BIO-J00001")
    with bank_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=solved.KEYED_FIELDS)
        writer.writeheader()
        writer.writerow(bank_row)
    reduced = [
        "question_id", "subject", "year", "question_text", "option_a",
        "option_b", "option_c", "option_d", "correct_option", "explanation",
    ]
    with incoming_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=reduced)
        writer.writeheader()
        writer.writerow({key: source_row("BIO-J00002").get(key, "") for key in reduced})

    monkeypatch.setattr(sys, "argv", [
        "merge_keyed_questions.py", "--in", str(incoming_path),
        "--bank", str(bank_path),
    ])
    with pytest.raises(SystemExit, match="refusing reduced-schema input"):
        merge_keyed_questions.main()
