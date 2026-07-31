"""
Safe insertion of rows guarded by a UNIQUE constraint.

Every gamification write is idempotent on a key, and the constraint -- not an
application-level SELECT -- is what settles concurrent duplicates. The subtlety
is what happens when the constraint DOES fire.

The obvious handler is::

    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()      # <-- wrong
        return

`Session.rollback()` discards the WHOLE transaction, not the failed statement.
These functions are called partway through request handling -- in the same
session as the student's answer, their mission progress, their XP -- so a
duplicate award would silently throw away the real work that came before it.
The student answers a question, a replayed event key collides, and their answer
disappears. Nothing raises; the request returns 200.

A SAVEPOINT scopes the undo to just this insert. Everything already pending in
the transaction survives, which is the actual intent: "this row was already
written, carry on".
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def insert_if_new(db: Session, *rows) -> bool:
    """
    Insert rows, tolerating a UNIQUE violation from a concurrent duplicate.

    Returns True if the rows were written, False if an equivalent row already
    existed. In the False case the surrounding transaction is left intact and
    the caller is responsible for reading back whatever already won the race.
    """
    try:
        with db.begin_nested():
            for row in rows:
                db.add(row)
            db.flush()
        return True
    except IntegrityError:
        # Rolled back to the savepoint only -- prior work in this transaction
        # is still pending and still valid.
        return False
