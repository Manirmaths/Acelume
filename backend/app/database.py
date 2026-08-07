import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

logger = logging.getLogger("naijaprep.database")

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added to existing models after the app was already deployed with
# real data. Base.metadata.create_all() (called on startup) only creates
# tables that don't exist yet -- it never ALTERs an existing table to add a
# new column, so on a live DB these would silently be missing and any query
# touching them (e.g. loading a User row) would fail. This patches them in,
# idempotently, on every startup. Add an entry here whenever a new column is
# added to a model that may already be deployed with data.
_PENDING_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "user": [
        ("streak_freezes", "INTEGER NOT NULL DEFAULT 0"),
        ("daily_goal", "INTEGER NOT NULL DEFAULT 50"),
        # No UNIQUE here deliberately -- SQLite/Postgres ADD COLUMN can't
        # carry a inline UNIQUE constraint uniformly across both dialects in
        # one ALTER. The column is nullable and only ever populated one row
        # at a time via routers/family.py's own uniqueness-checked
        # generation loop, so an application-level guarantee is sufficient
        # here (same reasoning as question_id's uniqueness being enforced at
        # the ORM/import-script level in practice).
        ("guardian_link_code", "VARCHAR(16)"),
        # IANA timezone name, e.g. "Africa/Lagos". Streaks and daily-mission
        # resets are calendar-day boundaries in the STUDENT's timezone, not
        # UTC -- without this, a Nigerian student practising at 11pm loses the
        # day at midnight UTC, an hour before their own midnight.
        #
        # Defaults to Africa/Lagos rather than UTC because that is where
        # essentially the entire user base sits; a UTC default would silently
        # give every existing student the wrong day boundary.
        ("timezone", "VARCHAR(64) NOT NULL DEFAULT 'Africa/Lagos'"),
        # Second streak type (spec section 6): the Learning streak counts any
        # meaningful activity, the Mastery streak requires demonstrated
        # accuracy. Tracked separately so a student who shows up daily but is
        # struggling still keeps a streak worth having.
        ("mastery_streak", "INTEGER NOT NULL DEFAULT 0"),
        ("longest_mastery_streak", "INTEGER NOT NULL DEFAULT 0"),
        ("last_mastery_date", "DATE"),
        # Weekly leagues. Opt-OUT rather than opt-in, so the feature works by
        # default, but a student who finds public ranking discouraging can
        # leave without losing any learning feature.
        ("league_opted_out", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("league_tier", "VARCHAR(20) NOT NULL DEFAULT 'foundation'"),
        # Daily Question streak -- a third, deliberately cheap streak. See the
        # note on User.daily_question_streak for why it is separate from the
        # Learning and Mastery streaks rather than folded into either.
        ("daily_question_streak", "INTEGER NOT NULL DEFAULT 0"),
        ("longest_daily_question_streak", "INTEGER NOT NULL DEFAULT 0"),
        ("last_daily_question_date", "DATE"),
    ],
    # `battle` is new enough that most deployments will get these from
    # create_all(), but listing them is harmless there and essential on any
    # instance that already shipped the async-only version of the table.
    "battle": [
        ("mode", "VARCHAR(10) NOT NULL DEFAULT 'async'"),
        ("started_at", "TIMESTAMP"),
    ],
    "battle_participant": [
        ("last_seen_at", "TIMESTAMP"),
    ],
    "user_response": [
        # Per-question timing. Nullable with no default: rows written before
        # this column existed genuinely have no timing, and a DEFAULT 0 would
        # make every historical answer look instantaneous and corrupt any
        # average built on the column.
        ("answer_seconds", "INTEGER"),
    ],
    "quiz_attempt": [
        # Plain TEXT, not a native JSON/JSONB column type -- SQLAlchemy's
        # JSON column type serializes/deserializes at the Python boundary
        # regardless of the underlying column's declared SQL type, and TEXT
        # is the one default clause that's valid on both SQLite and Postgres
        # without dialect-specific casting syntax.
        ("marked_question_ids", "TEXT NOT NULL DEFAULT '[]'"),
    ],
}


def ensure_schema() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table, columns in _PENDING_COLUMNS.items():
        if table not in existing_tables:
            continue  # brand-new DB -- create_all() already made it with every column
        existing_cols = {c["name"] for c in inspector.get_columns(table)}
        missing = [(name, ddl) for name, ddl in columns if name not in existing_cols]
        if not missing:
            continue
        with engine.begin() as conn:
            for name, ddl in missing:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))


def normalize_emails() -> None:
    """
    One-time-safe, idempotent cleanup for accounts created before
    schemas.py started lowercasing email on write (RegisterIn/LoginIn/
    ForgotPasswordIn). Without this, an account created as "John@x.com"
    could never log in with "john@x.com" -- exact string match on a column
    that's case-sensitive by default in both SQLite and Postgres. Safe to
    run on every startup: already-lowercase rows are a no-op.
    """
    from app.models import User  # local import -- avoids a circular import at module load time

    db = SessionLocal()
    try:
        users = db.query(User).all()

        # Precompute how many existing rows would collide on the same
        # lowercased value *before* mutating anything, so we don't lowercase
        # one row into a collision with a not-yet-processed row.
        target_counts: dict[str, int] = {}
        for u in users:
            if u.email:
                target_counts[u.email.strip().lower()] = target_counts.get(u.email.strip().lower(), 0) + 1

        changed = False
        for u in users:
            if not u.email:
                continue
            lowered = u.email.strip().lower()
            if lowered == u.email:
                continue
            if target_counts.get(lowered, 0) > 1:
                logger.warning(
                    "Skipping email-case normalization for user id=%s (%r) -- would collide "
                    "with another existing account after lowercasing. Resolve manually.",
                    u.id, u.email,
                )
                continue
            u.email = lowered
            changed = True

        if changed:
            db.commit()
    finally:
        db.close()
