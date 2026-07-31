"""
Seed the syllabus graph (SyllabusTopic) from the live question bank.

    python seed_syllabus.py "sqlite:///./naijaprep.db"
    python seed_syllabus.py "<DATABASE_URL>"

Safe and re-runnable: topics are upserted by (subject, topic), and an admin's
edits to order_index, estimated_minutes or prerequisite_id are preserved unless
--reset-order is passed.

ON SEQUENCING
-------------
Prerequisites are seeded ONLY for subjects with an uncontroversial teaching
order (Mathematics, Physics, Chemistry, Biology). Those chains are still a
first pass and should be reviewed by a teacher.

For the remaining subjects -- English, Geography, Economics, Literature,
Government, Commerce, Accounting -- topics are seeded with NO prerequisite, so
every topic is immediately available and the Quest Map renders as a flat set.
That is a deliberate choice: inventing a teaching order for subjects without
one is worse than admitting there isn't one, because a wrong prerequisite
chain actively blocks students from content they are ready for.

Set prerequisites for those subjects from the admin UI once a subject
specialist has sequenced them.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Question, SyllabusTopic  # noqa: F401 -- registers every model

# Subjects where the teaching order is uncontroversial enough to seed a chain.
# Each list is in teaching order: item N is the prerequisite of item N+1.
ORDERED_SUBJECTS: dict[str, list[str]] = {
    "Mathematics": [
        "Number, Fractions, and Approximation",
        "Commercial Arithmetic",
        "Algebraic Processes",
        "Sets and Binary Operations",
        "Sequences, Series, and Variation",
        "Inequalities, Permutation, and Combination",
        "Geometry and Mensuration",
        "Coordinate Geometry and Trigonometry",
        "Statistics and Probability",
        "Calculus",
    ],
    "Physics": [
        "General Physics and Measurement",
        "Mechanics, Motion, and Energy",
        "Properties of Matter and Fluids",
        "Heat and Thermodynamics",
        "Waves, Sound, and Optics",
        "Electricity and Magnetism",
        "Electronics and Alternating Current",
        "Nuclear and Modern Physics",
    ],
    "Chemistry": [
        "Atomic Structure and Chemical Bonding",
        "Periodicity and Inorganic Chemistry",
        "Quantitative Chemistry",
        "Acids, Bases, and Salts",
        "Physical Chemistry",
        "Electrochemistry and Redox Reactions",
        "Chemistry of Non-metals and Gases",
        "Chemistry of Metals",
        "Organic Chemistry",
        "Environmental and Industrial Chemistry",
    ],
    "Biology": [
        "Cell Biology and Biochemistry",
        "Classification",
        "Plant Biology",
        "Animal Biology and Comparative Physiology",
        "Mammalian Physiology and Anatomy",
        "Reproduction and Nutrition",
        "Genetics and Evolution",
        "Microbiology and Disease",
        "Ecology and Environment",
        "Agricultural Science and Basic Biology",
    ],
}

def estimate_minutes(question_count: int) -> int:
    """
    Rough time to work through a topic, used by mission planning to keep a
    day inside the spec's 15-30 minute budget.

    A heuristic, and openly so: roughly 10 minutes to read the lesson plus
    time proportional to how much material the topic carries, using question
    count as the only breadth signal available. Clamped to 12-45 minutes so a
    thin topic is not dismissed as trivial and English comprehension (742
    questions) does not claim an hour.

    Question count is a proxy for how heavily a topic is examined, not for how
    long it takes to learn -- so these are a starting point for a teacher to
    correct in the admin UI, not a measurement.
    """
    raw = 10 + question_count / 12
    clamped = max(12, min(45, raw))
    return int(round(clamped / 5) * 5)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    url = sys.argv[1]
    reset_order = "--reset-order" in sys.argv

    engine = create_engine(url)
    # Create any missing tables first. Without this the script fails on a
    # database the FastAPI app has never started against -- syllabus_topic is
    # a brand-new table, so nothing else would have created it. Matches what
    # seed_questions.py already does.
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Source of truth for which topics exist is the active question bank.
    pairs = (
        db.query(Question.subject, Question.topic, func.count(Question.id))
        .filter(Question.status == "active")
        .group_by(Question.subject, Question.topic)
        .all()
    )
    print(f"Found {len(pairs)} (subject, topic) pairs in the question bank.")

    existing = {(r.subject, r.topic): r for r in db.query(SyllabusTopic).all()}
    created = updated = 0

    for subject, topic, q_count in pairs:
        if not subject or not topic:
            continue
        order_list = ORDERED_SUBJECTS.get(subject)
        if order_list and topic in order_list:
            order_index = order_list.index(topic)
        else:
            # Unsequenced subject: order alphabetically so the map is at least
            # stable, and leave prerequisites unset.
            order_index = 500

        row = existing.get((subject, topic))
        if row is None:
            row = SyllabusTopic(
                subject=subject,
                topic=topic,
                order_index=order_index,
                estimated_minutes=estimate_minutes(q_count),
                description=f"{q_count} practice questions available.",
            )
            db.add(row)
            existing[(subject, topic)] = row
            created += 1
        else:
            if reset_order:
                row.order_index = order_index
                # Only re-derive the estimate on an explicit --reset-order, so
                # a teacher's hand-tuned value is not silently overwritten by
                # the heuristic on every re-seed.
                row.estimated_minutes = estimate_minutes(q_count)
                updated += 1

    db.flush()

    # Second pass: wire the chains now that every row has an id.
    linked = 0
    for subject, order_list in ORDERED_SUBJECTS.items():
        previous: SyllabusTopic | None = None
        for topic in order_list:
            row = existing.get((subject, topic))
            if row is None:
                # Listed in the teaching order but absent from the bank --
                # worth surfacing rather than silently skipping.
                print(f"  ! {subject} / {topic}: in teaching order but no active questions")
                continue
            if row.prerequisite_id is None or reset_order:
                new_prereq = previous.id if previous else None
                if row.prerequisite_id != new_prereq:
                    row.prerequisite_id = new_prereq
                    linked += 1
            previous = row

    db.commit()

    flat = sorted({s for s, _, _ in pairs} - set(ORDERED_SUBJECTS))
    print(f"Created {created}, reordered {updated}, prerequisite links set {linked}.")
    print(f"Sequenced subjects:  {', '.join(sorted(ORDERED_SUBJECTS))}")
    print(f"Flat (no prereqs):   {', '.join(flat)}")
    print("  -> flat subjects render every topic as immediately available;")
    print("     sequence them from the admin UI once a specialist has ordered them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
