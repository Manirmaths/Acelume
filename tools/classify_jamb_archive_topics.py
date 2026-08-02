"""Assign sync-safe topics to JAMB archive questions without inventing precision.

The solved archive does not carry topic metadata, while ``sync_questions_db.py``
intentionally skips rows whose topic is blank.  This tool learns the existing,
subject-specific topic vocabulary from the labelled question bank.  It applies a
canonical topic only when two different text classifiers agree with calibrated
margins; uncertain rows receive ``General Past Questions``.  A broad truthful
label is safer than placing a question in the wrong lesson or quest-map node.

The command is a dry run unless ``--apply`` is supplied.  Applying writes a
backup and atomically replaces the bank.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import pathlib
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass


csv.field_size_limit(10**7)
REPO = pathlib.Path(__file__).resolve().parents[1]
BANK = REPO / "data" / "questions.csv"
FALLBACK_TOPIC = "General Past Questions"
COSINE_MARGIN = 0.08
NB_MARGIN = 2.0

TEXT_FIELDS = ("question_text", "option_a", "option_b", "option_c", "option_d")
STOP_WORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "with", "is", "are",
    "was", "were", "be", "been", "being", "and", "or", "that", "this",
    "these", "those", "which", "what", "who", "whom", "whose", "how", "when",
    "where", "why", "from", "by", "as", "at", "it", "its", "into", "than",
    "then", "can", "could", "should", "would", "may", "might", "will", "shall",
    "do", "does", "did", "not", "no", "all", "any", "each", "every", "both",
    "either", "neither", "if", "about", "question", "following", "most", "best",
    "mainly", "means", "referred", "according",
}


@dataclass
class TopicModel:
    idf: dict[str, float]
    centroids: dict[str, tuple[Counter[str], float]]
    class_counts: Counter[str]
    word_counts: dict[str, Counter[str]]
    word_totals: Counter[str]
    vocab_size: int


def load(path: pathlib.Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def features(row: dict[str, str]) -> Counter[str]:
    text = " ".join(row.get(field, "") for field in TEXT_FIELDS).lower()
    words = [
        word for word in re.findall(r"[a-z][a-z'-]+", text)
        if len(word) > 2 and word not in STOP_WORDS
    ]
    return Counter(words + [f"{words[i]}__{words[i + 1]}" for i in range(len(words) - 1)])


def train(rows: list[dict[str, str]]) -> TopicModel:
    document_frequency: Counter[str] = Counter()
    by_topic: dict[str, list[Counter[str]]] = defaultdict(list)
    class_counts: Counter[str] = Counter()
    word_counts: dict[str, Counter[str]] = defaultdict(Counter)
    word_totals: Counter[str] = Counter()
    vocabulary: set[str] = set()

    for row in rows:
        topic = row["topic"].strip()
        row_features = features(row)
        document_frequency.update(row_features)
        by_topic[topic].append(row_features)
        class_counts[topic] += 1
        word_counts[topic].update(row_features)
        word_totals[topic] += sum(row_features.values())
        vocabulary.update(row_features)

    count = len(rows)
    idf = {
        word: math.log((count + 1) / (frequency + 1)) + 1
        for word, frequency in document_frequency.items()
    }
    centroids: dict[str, tuple[Counter[str], float]] = {}
    for topic, documents in by_topic.items():
        centroid: Counter[str] = Counter()
        for document in documents:
            for word, frequency in document.items():
                centroid[word] += (1 + math.log(frequency)) * idf[word]
        for word in list(centroid):
            centroid[word] /= len(documents)
        norm = math.sqrt(sum(weight * weight for weight in centroid.values()))
        centroids[topic] = centroid, norm

    return TopicModel(
        idf=idf,
        centroids=centroids,
        class_counts=class_counts,
        word_counts=dict(word_counts),
        word_totals=word_totals,
        vocab_size=len(vocabulary),
    )


def predict(model: TopicModel, row: dict[str, str]) -> tuple[str, float, str, float]:
    row_features = features(row)
    vector = {
        word: (1 + math.log(frequency)) * model.idf.get(word, 0)
        for word, frequency in row_features.items()
        if word in model.idf
    }
    vector_norm = math.sqrt(sum(weight * weight for weight in vector.values())) or 1
    cosine_scores: list[tuple[float, str]] = []
    for topic, (centroid, centroid_norm) in model.centroids.items():
        dot = sum(weight * centroid.get(word, 0) for word, weight in vector.items())
        cosine_scores.append((dot / (vector_norm * centroid_norm or 1), topic))
    cosine_scores.sort(reverse=True)

    total_classes = sum(model.class_counts.values())
    nb_scores: list[tuple[float, str]] = []
    for topic, class_count in model.class_counts.items():
        score = math.log(class_count / total_classes)
        denominator = model.word_totals[topic] + model.vocab_size
        for word, frequency in row_features.items():
            score += frequency * math.log(
                (model.word_counts[topic][word] + 1) / denominator
            )
        nb_scores.append((score, topic))
    nb_scores.sort(reverse=True)

    cosine_margin = cosine_scores[0][0] - cosine_scores[1][0]
    nb_margin = nb_scores[0][0] - nb_scores[1][0]
    return cosine_scores[0][1], cosine_margin, nb_scores[0][1], nb_margin


def accepted_topic(model: TopicModel, row: dict[str, str]) -> str:
    cosine_topic, cosine_margin, nb_topic, nb_margin = predict(model, row)
    if (
        cosine_topic == nb_topic
        and cosine_margin >= COSINE_MARGIN
        and nb_margin >= NB_MARGIN
    ):
        return cosine_topic
    return FALLBACK_TOPIC


def is_archive_target(row: dict[str, str]) -> bool:
    tags = {tag.strip() for tag in row.get("tags", "").split("|") if tag.strip()}
    return (
        not row.get("topic", "").strip()
        and row.get("source", "").strip() == "past-question"
        and "jamb-archive" in tags
    )


def is_training_row(row: dict[str, str]) -> bool:
    """Keep prior model output from becoming its own training evidence."""
    tags = {tag.strip() for tag in row.get("tags", "").split("|") if tag.strip()}
    return (
        bool(row.get("topic", "").strip())
        and "topic-auto" not in tags
        and "topic-general" not in tags
    )


def add_tag(row: dict[str, str], tag: str) -> None:
    tags = [item.strip() for item in row.get("tags", "").split("|") if item.strip()]
    if tag not in tags:
        tags.append(tag)
    row["tags"] = "|".join(tags)


def validation_split(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    training: list[dict[str, str]] = []
    held_out: list[dict[str, str]] = []
    by_topic: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_topic[row["topic"].strip()].append(row)
    for topic_rows in by_topic.values():
        ordered = sorted(
            topic_rows,
            key=lambda row: hashlib.sha256(row["question_id"].encode()).hexdigest(),
        )
        count = max(1, round(len(ordered) * 0.2))
        held_out.extend(ordered[:count])
        training.extend(ordered[count:])
    return training, held_out


def validate(labelled: list[dict[str, str]]) -> tuple[int, int, float]:
    training, held_out = validation_split(labelled)
    model = train(training)
    accepted = 0
    correct = 0
    for row in held_out:
        topic = accepted_topic(model, row)
        if topic == FALLBACK_TOPIC:
            continue
        accepted += 1
        correct += topic == row["topic"].strip()
    precision = correct / accepted if accepted else 0
    return accepted, correct, precision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--bank", type=pathlib.Path, default=BANK)
    parser.add_argument("--minimum-validation-precision", type=float, default=0.90)
    args = parser.parse_args()

    fields, rows = load(args.bank)
    labelled_by_subject: dict[str, list[dict[str, str]]] = defaultdict(list)
    targets_by_subject: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if is_training_row(row):
            labelled_by_subject[row["subject"]].append(row)
        elif is_archive_target(row):
            targets_by_subject[row["subject"]].append(row)

    print(f"bank rows             : {len(rows):,}")
    print(f"blank archive topics  : {sum(map(len, targets_by_subject.values())):,}")
    assignments: Counter[str] = Counter()
    validation_failed = False
    for subject in sorted(targets_by_subject):
        labelled = labelled_by_subject.get(subject, [])
        if not labelled:
            print(f"ERROR: {subject} has no labelled training questions")
            validation_failed = True
            continue
        accepted, correct, precision = validate(labelled)
        print(
            f"{subject:12s} validation {correct:3d}/{accepted:3d} "
            f"({precision:.1%} precision among classified rows)"
        )
        if precision < args.minimum_validation_precision:
            validation_failed = True
            continue
        model = train(labelled)
        for row in targets_by_subject[subject]:
            topic = accepted_topic(model, row)
            row["topic"] = topic
            add_tag(row, "topic-general" if topic == FALLBACK_TOPIC else "topic-auto")
            assignments[topic] += 1

    if validation_failed:
        print("ERROR: validation gate failed; bank was not changed")
        return 1

    print(f"canonical assignments : {sum(v for k, v in assignments.items() if k != FALLBACK_TOPIC):,}")
    print(f"general fallback      : {assignments[FALLBACK_TOPIC]:,}")
    if not args.apply:
        print("\nDry run. Re-run with --apply to write assignments.")
        return 0
    if not assignments:
        print("nothing to do")
        return 0

    temp = args.bank.with_suffix(".csv.topic-classify.tmp")
    backup = args.bank.with_suffix(".csv.topic-classify.bak")
    with temp.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    shutil.copy2(args.bank, backup)
    temp.replace(args.bank)
    print(f"backup -> {backup}")
    print(f"wrote  -> {args.bank}")

    _, verified = load(args.bank)
    remaining = [row for row in verified if is_archive_target(row)]
    if remaining:
        print(f"ERROR: {len(remaining)} archive rows still have blank topics")
        return 1
    print(f"verified {len(verified):,} rows; no archive topic gaps remain")
    return 0


if __name__ == "__main__":
    sys.exit(main())
