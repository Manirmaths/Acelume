#!/usr/bin/env python3
"""
General-purpose sync: upserts ALL of data/questions.csv into a target
database's "question" table, matched by question_id.

Unlike seed_questions.py (insert-only -- skips any question_id already
present) this UPDATES every content column on existing rows to match the
CSV, and INSERTS any question_id that isn't in the DB yet. Nothing else
(id, user_response/quiz_attempt history, which reference Question.id) is
touched, since question_id is unique and Question.id never changes.

Updates/inserts are batched (default 200 rows/round trip) instead of one
statement per row -- over a remote connection (e.g. Neon), one-row-at-a-time
can take many minutes for 10k+ rows; batching cuts it to a few seconds.

Run with `python -u` (unbuffered) if progress lines aren't showing up as
they happen -- otherwise stdout can buffer and make it look stuck even
though it's working.

Usage:
    python -u sync_questions_db.py "<DATABASE_URL>"
    python -u sync_questions_db.py "<DATABASE_URL>" --dry-run

Examples:
    python -u sync_questions_db.py "sqlite:///./naijaprep.db"
    python -u sync_questions_db.py "postgresql://user:pass@host/dbname?sslmode=require"
"""
import csv
import os
import sys
import time

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seed_questions import sanitize, norm_choice, norm_enum, VALID_DIFFICULTY, VALID_SOURCE, VALID_STATUS
from app.subjects import normalize_subject

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "questions.csv")

COLUMNS = [
    "subject", "topic", "subtopic", "difficulty", "year", "exam_type",
    "question_text", "image_url", "option_a", "option_b", "option_c",
    "option_d", "correct_option", "explanation", "tags", "source", "status",
]

BATCH_SIZE = 200


def log(msg):
    print(msg, flush=True)


def load_row(row):
    return {
        "subject": normalize_subject(row.get("subject")) or (row.get("subject") or "").strip() or None,
        "topic": sanitize((row.get("topic") or "").strip()),
        "subtopic": sanitize((row.get("subtopic") or "").strip()) or None,
        "difficulty": norm_enum(row.get("difficulty"), VALID_DIFFICULTY, "medium"),
        "year": (row.get("year") or "").strip() or None,
        "exam_type": (row.get("exam_type") or "").strip() or None,
        "question_text": sanitize(row.get("question_text") or ""),
        "image_url": (row.get("image_url") or "").strip() or None,
        "option_a": sanitize(row.get("option_a")),
        "option_b": sanitize(row.get("option_b")),
        "option_c": sanitize(row.get("option_c")),
        "option_d": sanitize(row.get("option_d")),
        "correct_option": norm_choice(row.get("correct_option")),
        "explanation": sanitize(row.get("explanation")),
        "tags": (row.get("tags") or "").strip() or None,
        "source": norm_enum(row.get("source"), VALID_SOURCE, "original"),
        "status": norm_enum(row.get("status"), VALID_STATUS, "active"),
    }


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    if len(args) != 1:
        log('Usage: python sync_questions_db.py "<DATABASE_URL>" [--dry-run]')
        sys.exit(1)
    db_url = args[0]

    t_start = time.time()
    log("Reading questions.csv...")
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    log(f"  {len(rows)} rows read ({time.time() - t_start:.1f}s)")

    log("Connecting to database...")
    t0 = time.time()
    engine = create_engine(db_url, connect_args={"connect_timeout": 15} if not db_url.startswith("sqlite") else {})
    is_postgres = engine.dialect.name.startswith("postgres")

    with engine.begin() as conn:
        log(f"  connected ({time.time() - t0:.1f}s)")

        t0 = time.time()
        log("Fetching existing question_ids...")
        existing_ids = {qid for (qid,) in conn.execute(text('SELECT question_id FROM "question"')).all()}
        log(f"  {len(existing_ids)} existing ids fetched ({time.time() - t0:.1f}s)")

        to_update = []
        to_insert = []
        skipped = 0
        for row in rows:
            qid = (row.get("question_id") or "").strip()
            if not qid:
                skipped += 1
                continue
            values = load_row(row)
            if not values["subject"] or not values["topic"] or not values["question_text"]:
                skipped += 1
                continue
            values["question_id"] = qid
            (to_update if qid in existing_ids else to_insert).append(values)

        log(f"Prepared {len(to_update)} updates, {len(to_insert)} inserts, {skipped} skipped.")

        if dry_run:
            log(f"DRY RUN -- Would update: {len(to_update)}")
            log(f"DRY RUN -- Would insert: {len(to_insert)}")
            log(f"Skipped (missing required field): {skipped}")
            conn.rollback()
            return

        if to_insert:
            t0 = time.time()
            log(f"Inserting {len(to_insert)} new rows in batches of {BATCH_SIZE}...")
            insert_cols = ["question_id"] + COLUMNS
            insert_sql = text(
                f'INSERT INTO "question" ({", ".join(insert_cols)}) '
                f'VALUES ({", ".join(":" + c for c in insert_cols)})'
            )
            total_insert_batches = (len(to_insert) + BATCH_SIZE - 1) // BATCH_SIZE or 1
            for batch_i, batch in enumerate(chunked(to_insert, BATCH_SIZE)):
                tb = time.time()
                conn.execute(insert_sql, batch)
                done = min((batch_i + 1) * BATCH_SIZE, len(to_insert))
                log(f"  insert batch {batch_i + 1}/{total_insert_batches}: "
                    f"{done}/{len(to_insert)} (this batch {time.time() - tb:.1f}s, "
                    f"total {time.time() - t0:.1f}s)")
            log(f"  insert phase done ({time.time() - t0:.1f}s)")

        t0 = time.time()
        log(f"Updating {len(to_update)} existing rows in batches of {BATCH_SIZE}...")
        if not to_update:
            # SQLAlchemy treats an empty executemany parameter list as one
            # missing parameter set on SQLite, so executing here raises after
            # successful inserts and rolls the whole transaction back.  A
            # fresh database legitimately has zero updates.
            pass
        elif is_postgres:
            # Bulk UPDATE ... FROM (VALUES ...) -- one round trip per batch
            # instead of one per row, which is what made the naive
            # row-by-row version painfully slow over a remote connection.
            value_cols = ["question_id"] + COLUMNS
            total_batches = (len(to_update) + BATCH_SIZE - 1) // BATCH_SIZE or 1
            for batch_i, batch in enumerate(chunked(to_update, BATCH_SIZE)):
                values_sql_parts = []
                params = {}
                for i, row in enumerate(batch):
                    placeholders = []
                    for c in value_cols:
                        key = f"{c}_{i}"
                        params[key] = row[c]
                        placeholders.append(f":{key}")
                    values_sql_parts.append(f"({', '.join(placeholders)})")
                values_sql = ", ".join(values_sql_parts)
                set_clause = ", ".join(f"{c} = v.{c}" for c in COLUMNS)
                sql = text(
                    f'UPDATE "question" AS q SET {set_clause} '
                    f'FROM (VALUES {values_sql}) AS v({", ".join(value_cols)}) '
                    f'WHERE q.question_id = v.question_id'
                )
                tb = time.time()
                conn.execute(sql, params)
                done = min((batch_i + 1) * BATCH_SIZE, len(to_update))
                log(f"  batch {batch_i + 1}/{total_batches}: updated {done}/{len(to_update)} "
                    f"(this batch {time.time() - tb:.1f}s, total {time.time() - t0:.1f}s)")
        else:
            set_clause = ", ".join(f"{c} = :{c}" for c in COLUMNS)
            update_sql = text(f'UPDATE "question" SET {set_clause} WHERE question_id = :question_id')
            conn.execute(update_sql, to_update)
        log(f"  update phase done ({time.time() - t0:.1f}s)")

    log(f"Updated: {len(to_update)}")
    log(f"Inserted: {len(to_insert)}")
    log(f"Skipped (missing required field): {skipped}")
    log(f"Total time: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
