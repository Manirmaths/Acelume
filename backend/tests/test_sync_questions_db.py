import csv
import sys

from sqlalchemy import create_engine, text

import sync_questions_db as sync
from app.database import Base
from app import models  # noqa: F401  Ensure every table is registered.


def test_fresh_sqlite_sync_commits_inserts_when_there_are_no_updates(
    monkeypatch, tmp_path
):
    database = tmp_path / "fresh.db"
    database_url = f"sqlite:///{database.as_posix()}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    csv_path = tmp_path / "questions.csv"
    fields = ["question_id"] + sync.COLUMNS
    row = {field: "" for field in fields}
    row.update({
        "question_id": "BIO-TEST-001",
        "subject": "Biology",
        "topic": "Cell Biology and Biochemistry",
        "difficulty": "medium",
        "question_text": "Which organelle releases usable energy?",
        "option_a": "Nucleus",
        "option_b": "Mitochondrion",
        "option_c": "Ribosome",
        "option_d": "Vacuole",
        "correct_option": "B",
        "explanation": "Mitochondria are the site of aerobic respiration.",
        "source": "past-question",
        "status": "draft",
    })
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerow(row)

    monkeypatch.setattr(sync, "CSV_PATH", str(csv_path))
    monkeypatch.setattr(sys, "argv", ["sync_questions_db.py", database_url])
    sync.main()

    with engine.connect() as connection:
        assert connection.execute(
            text('SELECT COUNT(*) FROM "question" WHERE question_id = :qid'),
            {"qid": row["question_id"]},
        ).scalar_one() == 1
