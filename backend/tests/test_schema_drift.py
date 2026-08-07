"""
Schema drift: a model column that the live database does not have.

This is the failure that took the exam feature down in production. A new
nullable column (`ExamCandidate.school_reference`) was added to a table that
already existed. `create_all()` creates missing TABLES but never adds a column
to an existing one, so every SELECT against the model referenced a column the
database did not have, and creating an exam returned a 500.

It was caught by a human clicking a button, not by anything here. These tests
close that gap: startup now reconciles nullable columns automatically, and if
that stops working, this fails instead of a school's exam.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base
from app.models import ExamCandidate, User


def _fresh_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _reconcile_against(engine):
    """Run ensure_schema() against a throwaway engine."""
    original = database.engine
    database.engine = engine
    try:
        database.ensure_schema()
    finally:
        database.engine = original


def test_a_nullable_column_missing_from_an_existing_table_is_added(monkeypatch):
    """
    The exact production failure, reproduced: build the table WITHOUT one of
    the model's nullable columns, then check startup repairs it.
    """
    engine = _fresh_engine()

    table = Base.metadata.tables["exam_candidate"]
    dropped = "school_reference"
    columns = ", ".join(
        f"{c.name} {c.type.compile(dialect=engine.dialect)}"
        for c in table.columns if c.name != dropped
    )
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE exam_candidate ({columns})"))

    before = {c["name"] for c in inspect(engine).get_columns("exam_candidate")}
    assert dropped not in before, "the column was genuinely missing to start with"

    _reconcile_against(engine)

    after = {c["name"] for c in inspect(engine).get_columns("exam_candidate")}
    assert dropped in after, "startup should have added the missing column"


def test_reconciliation_is_idempotent():
    """Runs on every boot, so running it twice must be a no-op."""
    engine = _fresh_engine()
    Base.metadata.create_all(engine)

    _reconcile_against(engine)
    _reconcile_against(engine)   # must not raise "duplicate column"

    assert "school_reference" in {
        c["name"] for c in inspect(engine).get_columns("exam_candidate")
    }


def test_a_brand_new_table_is_left_to_create_all():
    """
    A table that does not exist yet needs creating whole, not column by
    column. Trying to ALTER a table that is not there would fail the boot.
    """
    engine = _fresh_engine()
    inspector = inspect(engine)

    missing = database._autodetect_missing_columns(inspector, set())
    assert missing == []


def test_not_null_columns_are_left_to_a_human():
    """
    A NOT NULL column needs a considered DEFAULT for the rows that already
    exist, and what value is right for historical data is a judgement rather
    than something to guess. Those stay in _PENDING_COLUMNS, where the
    reasoning is written down.
    """
    engine = _fresh_engine()

    table = Base.metadata.tables["user"]
    columns = ", ".join(
        f"{c.name} {c.type.compile(dialect=engine.dialect)}"
        for c in table.columns if c.name != "daily_question_streak"
    )
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE user ({columns})"))

    auto = database._autodetect_missing_columns(inspect(engine), {"user"})
    assert all(name != "daily_question_streak" for _, name, _ in auto), (
        "a NOT NULL column must not be auto-added without a default"
    )


def test_every_model_column_survives_a_full_create(db_session):
    """
    Belt and braces: on a database built from scratch, every column the models
    declare must actually exist. Catches a model that cannot be created at all.
    """
    engine = db_session.get_bind()
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    problems = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing:
            problems.append(f"{table_name}: table missing entirely")
            continue
        present = {c["name"] for c in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in present:
                problems.append(f"{table_name}.{column.name}")

    assert not problems, f"columns missing after create_all: {problems}"


def test_the_exam_candidate_model_has_the_column_that_broke_production():
    """A named regression guard, so the specific field cannot quietly vanish."""
    assert hasattr(ExamCandidate, "school_reference")
    assert hasattr(User, "daily_question_streak")
