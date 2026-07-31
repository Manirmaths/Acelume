"""
Settle the finished league week: promote, demote, and open next week's cohorts.

    python close_league_week.py "<DATABASE_URL>"
    python close_league_week.py "<DATABASE_URL>" --week 2026-07-27

Intended to run every Monday from .github/workflows/close-league-week.yml.

Safe to re-run: `close_week()` only touches cohorts whose `closed_at` is NULL,
so a retried or duplicated job cannot promote anyone twice.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.gamification import leagues
from app.models import User  # noqa: F401 -- registers models


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    url = sys.argv[1]

    week: date
    if "--week" in sys.argv:
        week = date.fromisoformat(sys.argv[sys.argv.index("--week") + 1])
    else:
        # Default to the week that just ended, not the current one -- closing
        # a week still in progress would settle it early.
        week = leagues.week_start_for(datetime.utcnow().date() - timedelta(days=7))

    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()

    print(f"Closing league week beginning {week.isoformat()}...")
    stats = leagues.close_week(db, week)
    db.commit()

    print(
        f"  cohorts closed: {stats['cohorts']}\n"
        f"  promoted:       {stats['promoted']}\n"
        f"  stayed:         {stats['stayed']}\n"
        f"  demoted:        {stats['demoted']}"
    )
    if stats["cohorts"] == 0:
        print("  (nothing to close -- already settled, or no activity that week)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
