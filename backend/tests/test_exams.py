"""
School exam sessions.

This is the highest-stakes feature in the app. Everything else being wrong
costs a student a confusing evening; this being wrong costs a school its mock
exam, in front of fifty pupils, with no way to re-run it. The relationship
does not survive that.

So the tests concentrate on the things that would be unrecoverable in a hall:

  - a candidate cannot sit twice, or under someone else's number
  - the clock is the server's, and cannot be extended by refreshing
  - a dead phone loses nothing that was already answered
  - correct answers never reach the client before submission
  - a paper that ran out of time is still scored on what was attempted
"""

import io
from datetime import datetime, timedelta

from openpyxl import Workbook

from app import exam_import, exams
from app.models import ExamCandidate, ExamQuestion, ExamSession, Question, User


def _seed_bank(db_session, n=60, subject="Mathematics"):
    for i in range(n):
        db_session.add(Question(
            question_id=f"ex-{subject}-{i}", subject=subject, topic="Algebra",
            difficulty="medium", source="original", status="active",
            question_text=f"Bank question {i}?",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="B", explanation="Because B.",
        ))
    db_session.commit()


def _session(db_session, admin_id=1, duration=50, count=10, open_now=True, source="bank"):
    now = datetime.utcnow()
    s = ExamSession(
        code=exams.unique_session_code(db_session),
        title="Second Term Mock", organisation="FGC Sokoto",
        created_by=admin_id,
        blueprint=[{"subject": "Mathematics", "count": count}],
        duration_minutes=duration, source=source,
        opens_at=now - timedelta(hours=1) if open_now else now + timedelta(days=1),
        closes_at=now + timedelta(hours=6) if open_now else now + timedelta(days=2),
        status="ready",
    )
    db_session.add(s)
    db_session.commit()
    s.question_ids = exams.build_paper(db_session, s)
    db_session.commit()
    return s


def _candidates(db_session, session, n=3):
    made = exams.create_candidates(
        db_session, session,
        [{"full_name": f"Student {i+1}", "school_reference": f"{i+1:03d}"} for i in range(n)],
    )
    db_session.commit()
    return made


def _workbook(rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


HEADERS = ["question", "option_a", "option_b", "option_c", "option_d", "correct"]


# ------------------------------------------------------- excel import ----

def test_a_clean_sheet_imports(db_session):
    data = _workbook([HEADERS, ["2 + 2 = ?", "3", "4", "5", "6", "B"]])
    report = exam_import.parse_workbook(data)
    assert report.ok
    assert len(report.questions) == 1
    assert report.questions[0]["correct_option"] == "B"


def test_every_bad_row_is_reported_not_just_the_first(db_session):
    """
    The decision the whole importer rests on. A teacher who gets "upload
    failed" goes back to photocopying; one who gets three row numbers fixes
    three cells.
    """
    data = _workbook([
        HEADERS,
        ["Good one", "1", "2", "3", "4", "A"],
        ["Missing an option", "1", "", "3", "4", "A"],
        ["Bad answer letter", "1", "2", "3", "4", "Z"],
        ["Another good one", "1", "2", "3", "4", "C"],
    ])
    report = exam_import.parse_workbook(data)

    assert len(report.questions) == 2, "the good rows still import"
    assert len(report.errors) == 2, "both problems reported together"
    assert {e.row for e in report.errors} == {3, 4}, "row numbers match what Excel shows"


def test_an_answer_written_out_in_full_is_understood(db_session):
    """
    The single most common teacher mistake, and far too ordinary to reject a
    file over.
    """
    data = _workbook([HEADERS, ["Simplify 3x + 2x", "5x", "6x", "x", "5", "5x"]])
    report = exam_import.parse_workbook(data)
    assert report.questions[0]["correct_option"] == "A"


def test_header_spelling_variants_are_accepted(db_session):
    data = _workbook([
        ["Question", "Option A", "OPTION_B", "optionC", "Choice D", "Answer"],
        ["2 + 2 = ?", "3", "4", "5", "6", "B"],
    ])
    report = exam_import.parse_workbook(data)
    assert report.ok


def test_trailing_empty_rows_are_not_errors(db_session):
    """A teacher who deleted content leaves hundreds of these behind."""
    data = _workbook([HEADERS, ["Real question", "1", "2", "3", "4", "A"]] + [[None] * 6] * 50)
    report = exam_import.parse_workbook(data)
    assert len(report.questions) == 1
    assert report.errors == []


def test_whole_numbers_do_not_become_decimals(db_session):
    """Excel returns 1 as 1.0, and "1.0" as an answer choice looks broken."""
    data = _workbook([HEADERS, ["Pick one", 1, 2, 3, 4, "A"]])
    report = exam_import.parse_workbook(data)
    assert report.questions[0]["option_a"] == "1"


def test_duplicate_questions_are_rejected(db_session):
    data = _workbook([
        HEADERS,
        ["Same question", "1", "2", "3", "4", "A"],
        ["Same question", "1", "2", "3", "4", "A"],
    ])
    report = exam_import.parse_workbook(data)
    assert len(report.questions) == 1
    assert any("duplicate" in e.problem for e in report.errors)


def test_missing_headers_fail_clearly(db_session):
    data = _workbook([["question", "option_a"], ["Incomplete", "1"]])
    report = exam_import.parse_workbook(data)
    assert report.fatal and "missing" in report.fatal.lower()


def test_a_non_spreadsheet_fails_gracefully(db_session):
    report = exam_import.parse_workbook(b"this is not a spreadsheet")
    assert report.fatal and not report.ok


# ------------------------------------------------------- sitting rules ----

def test_a_candidate_gets_a_shuffled_paper(db_session):
    """
    Same questions, different order per candidate. Makes reading off the next
    screen along much harder without any invigilation software.
    """
    _seed_bank(db_session)
    session = _session(db_session, count=20)
    made = _candidates(db_session, session, n=6)

    orders = [tuple(c.question_order) for c in made]
    assert all(sorted(o) == sorted(orders[0]) for o in orders), "same questions"
    assert len(set(orders)) > 1, "different order"


def test_a_registration_number_matches_the_agreed_format(db_session):
    """One letter, seven digits, two letters -- A1234567BC."""
    _seed_bank(db_session)
    session = _session(db_session)
    candidate = _candidates(db_session, session, n=1)[0]
    reg = candidate.registration_number

    assert len(reg) == 10
    assert reg[0].isalpha()
    assert reg[1:8].isdigit()
    assert reg[8:].isalpha()
    assert reg.isupper()


def test_easily_misread_letters_are_avoided(db_session):
    """
    I and O never appear. The format already disambiguates position, but a
    number gets transcribed by hand from a printed slip by a teenager.
    """
    _seed_bank(db_session)
    session = _session(db_session)
    made = _candidates(db_session, session, n=40)

    letters = "".join(c.registration_number[0] + c.registration_number[8:] for c in made)
    assert "I" not in letters and "O" not in letters


def test_registration_numbers_are_unique_across_different_sessions(db_session):
    """
    Globally unique, not per-session. Two schools both numbering from 001 was
    exactly the problem generating them solves.
    """
    _seed_bank(db_session)
    first = _session(db_session)
    second = _session(db_session)

    numbers = [c.registration_number for c in _candidates(db_session, first, n=25)]
    numbers += [c.registration_number for c in _candidates(db_session, second, n=25)]

    assert len(set(numbers)) == 50


def test_a_number_is_never_reissued_even_after_the_candidate_is_deleted(db_session):
    """
    The ledger is the point. Deleting a session must not free its numbers back
    into circulation -- one registration number appearing on two different
    papers years apart would discredit the whole system.
    """
    from app.models import IssuedRegistration

    _seed_bank(db_session)
    session = _session(db_session)
    candidate = _candidates(db_session, session, n=1)[0]
    retired = candidate.registration_number

    db_session.delete(candidate)
    db_session.commit()

    assert db_session.query(IssuedRegistration).filter(
        IssuedRegistration.number == retired
    ).count() == 1, "the number stays reserved"

    fresh = [c.registration_number for c in _candidates(db_session, session, n=30)]
    assert retired not in fresh


def test_the_school_keeps_its_own_reference(db_session):
    """So a generated number can still be matched back to a class list."""
    _seed_bank(db_session)
    session = _session(db_session)
    made = exams.create_candidates(
        db_session, session, [{"full_name": "Amina Bello", "school_reference": "JSS3/014"}]
    )
    db_session.commit()

    assert made[0].school_reference == "JSS3/014"
    assert made[0].registration_number != "JSS3/014"


def test_candidates_can_be_added_by_count_alone(db_session):
    """An entrance exam has no names yet -- slips are handed out at the door."""
    _seed_bank(db_session)
    session = _session(db_session)
    made = exams.create_candidates(db_session, session, [{} for _ in range(12)])
    db_session.commit()

    assert len(made) == 12
    assert all(c.registration_number and c.access_code for c in made)
    assert all(c.full_name is None for c in made)


# --------------------------------------------------- multi-subject paper ----

def test_a_paper_can_span_several_subjects(db_session):
    """The interview/entrance case: three subjects, twenty questions each."""
    for subject in ("Mathematics", "English", "Physics"):
        _seed_bank(db_session, n=40, subject=subject)

    now = datetime.utcnow()
    session = ExamSession(
        code=exams.unique_session_code(db_session),
        title="Entrance Exam", organisation="FGC Sokoto", created_by=1,
        blueprint=[
            {"subject": "Mathematics", "count": 20},
            {"subject": "English", "count": 20},
            {"subject": "Physics", "count": 20},
        ],
        duration_minutes=60, source="bank",
        opens_at=now - timedelta(hours=1), closes_at=now + timedelta(hours=6),
        status="draft",
    )
    db_session.add(session)
    db_session.commit()
    session.question_ids = exams.build_paper(db_session, session)
    db_session.commit()

    assert len(session.question_ids) == 60

    subjects = {
        q.subject for q in
        db_session.query(Question).filter(Question.id.in_(session.question_ids)).all()
    }
    assert subjects == {"Mathematics", "English", "Physics"}


def test_subject_availability_reports_the_bank(db_session):
    _seed_bank(db_session, n=35, subject="Mathematics")
    rows = {r["subject"]: r["available"] for r in exams.subject_availability(db_session)}
    assert rows["Mathematics"] == 35
    assert rows["Chemistry"] == 0


# ---------------------------------------------------------- publish gate ----

def test_a_session_is_not_ready_until_everything_is_set(db_session):
    """
    An exam that quietly went live half-configured is a much worse failure
    than one that refuses to publish.
    """
    _seed_bank(db_session)
    session = _session(db_session)
    session.status = "draft"
    db_session.commit()

    state = exams.readiness(db_session, session)
    assert state["ready"] is False
    assert any("candidate" in p.lower() for p in state["problems"])


def test_a_fully_configured_session_is_ready(db_session):
    _seed_bank(db_session)
    session = _session(db_session)
    _candidates(db_session, session, n=3)

    state = exams.readiness(db_session, session)
    assert state["ready"] is True, state["problems"]
    assert state["candidates"] == 3


def test_an_impossible_blueprint_blocks_publishing(db_session):
    """Caught while it is a draft, not discovered in the hall."""
    _seed_bank(db_session, n=10)
    session = _session(db_session, count=40)
    _candidates(db_session, session, n=3)

    state = exams.readiness(db_session, session)
    assert state["ready"] is False
    assert any("only 10" in p for p in state["problems"])


def test_publishing_is_refused_until_ready(client, db_session):
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session)
    session.status = "draft"
    db_session.commit()

    res = client.post(f"/api/exams/manage/sessions/{session.id}/publish")
    assert res.status_code == 400
    assert "not ready" in res.json()["detail"].lower()


def test_a_draft_is_invisible_to_candidates(client, db_session):
    """No link works until the organiser has reviewed and published."""
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session)
    session.status = "draft"
    db_session.commit()
    client.post("/api/auth/logout")

    assert client.get(f"/api/exams/{session.code}").status_code == 404


def test_the_clock_starts_on_the_server_and_cannot_be_extended(db_session):
    """Refreshing, closing the browser or changing the phone clock buys nothing."""
    _seed_bank(db_session)
    session = _session(db_session, duration=50)
    candidate = _candidates(db_session, session, n=1)[0]

    candidate.started_at = datetime.utcnow() - timedelta(minutes=20)
    db_session.commit()

    remaining = exams.seconds_remaining(session, candidate)
    assert 29 * 60 <= remaining <= 30 * 60


def test_time_that_has_run_out_reports_zero_not_negative(db_session):
    _seed_bank(db_session)
    session = _session(db_session, duration=10)
    candidate = _candidates(db_session, session, n=1)[0]
    candidate.started_at = datetime.utcnow() - timedelta(hours=2)
    db_session.commit()

    assert exams.seconds_remaining(session, candidate) == 0


def test_an_abandoned_paper_is_still_scored_on_what_was_answered(db_session):
    """
    A phone dying at question 48 must not void the first 47. A session also
    cannot sit forever reporting candidates as "in progress".
    """
    _seed_bank(db_session)
    session = _session(db_session, duration=10, count=10)
    candidate = _candidates(db_session, session, n=1)[0]

    candidate.started_at = datetime.utcnow() - timedelta(hours=1)
    candidate.answers = {str(qid): "B" for qid in session.question_ids[:4]}
    db_session.commit()

    assert exams.auto_submit_expired(db_session, session) == 1
    # auto_submit_expired deliberately leaves committing to the caller (the
    # router does it), so commit before reloading or the change is discarded.
    db_session.commit()
    db_session.refresh(candidate)
    assert candidate.submitted_at is not None
    assert candidate.score == 4


def test_submitting_twice_cannot_change_the_score(db_session):
    """Matters when a flaky connection makes a student tap Submit three times."""
    _seed_bank(db_session)
    session = _session(db_session, count=10)
    candidate = _candidates(db_session, session, n=1)[0]
    candidate.answers = {str(qid): "B" for qid in session.question_ids[:3]}
    db_session.commit()

    first = exams.submit(db_session, session, candidate)
    candidate.answers = {str(qid): "B" for qid in session.question_ids}   # cheating attempt
    second = exams.submit(db_session, session, candidate)

    assert first == second == 3


def test_a_blank_answer_scores_zero_rather_than_being_ignored(db_session):
    """This is an exam. A blank is a wrong answer, not an excluded question."""
    _seed_bank(db_session)
    session = _session(db_session, count=10)
    candidate = _candidates(db_session, session, n=1)[0]
    candidate.answers = {str(session.question_ids[0]): "B"}
    db_session.commit()

    assert exams.submit(db_session, session, candidate) == 1


def test_a_shortfall_is_flagged_before_exam_day(db_session):
    """
    Discovering in the hall that Commerce had 12 of the 40 questions asked for
    is how a school relationship ends.
    """
    _seed_bank(db_session, n=15)
    problems = exams.blueprint_shortfall(db_session, [{"subject": "Mathematics", "count": 40}])
    assert problems and "only 15" in problems[0]


def test_no_shortfall_when_the_bank_is_deep_enough(db_session):
    _seed_bank(db_session, n=60)
    assert exams.blueprint_shortfall(db_session, [{"subject": "Mathematics", "count": 40}]) == []


def test_uploaded_questions_stay_out_of_the_practice_bank(db_session):
    """
    School content has not been through Acelume's editorial process and may be
    copied from a textbook. Mixing it into the bank students practise from
    would put unreviewed material in front of everyone.
    """
    _seed_bank(db_session, n=5)
    before = db_session.query(Question).count()

    session = _session(db_session, source="upload")
    db_session.add(ExamQuestion(
        session_id=session.id, question_text="School question", position=0,
        option_a="1", option_b="2", option_c="3", option_d="4", correct_option="A",
    ))
    db_session.commit()

    assert db_session.query(Question).count() == before


# ------------------------------------------------------------ endpoints ----

def _admin(client, db_session):
    client.post("/api/auth/register", json={
        "username": "organiser", "email": "organiser@example.com", "password": "password123",
    })
    user = db_session.query(User).filter(User.username == "organiser").first()
    user.is_admin = True
    db_session.commit()
    return user


def test_creating_a_session_requires_an_admin(client, register_user):
    register_user()
    res = client.post("/api/exams/manage/sessions", json={
        "title": "Mock", "organisation": "School", "duration_minutes": 50,
        "opens_at": datetime.utcnow().isoformat(),
        "closes_at": (datetime.utcnow() + timedelta(hours=3)).isoformat(),
    })
    assert res.status_code == 403


def test_a_candidate_can_sit_without_any_account(client, db_session):
    """
    The whole point. Fifty students registering inside a fifty-minute slot
    would eat a quarter of the paper.
    """
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session, count=10)
    candidate = _candidates(db_session, session, n=1)[0]

    client.post("/api/auth/logout")    # no session, no account, nothing

    res = client.post(f"/api/exams/{session.code}/start", json={
        "registration_number": candidate.registration_number,
        "access_code": candidate.access_code,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["questions"]) == 10
    assert body["seconds_remaining"] > 0


def test_the_paper_never_carries_the_correct_answers(client, db_session):
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session, count=10)
    candidate = _candidates(db_session, session, n=1)[0]
    client.post("/api/auth/logout")

    body = client.post(f"/api/exams/{session.code}/start", json={
        "registration_number": candidate.registration_number,
        "access_code": candidate.access_code,
    }).json()

    for q in body["questions"]:
        assert "correct_option" not in q
        assert "explanation" not in q


def test_a_wrong_access_code_is_refused(client, db_session):
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session)
    candidate = _candidates(db_session, session, n=1)[0]
    client.post("/api/auth/logout")

    res = client.post(f"/api/exams/{session.code}/start", json={
        "registration_number": candidate.registration_number,
        "access_code": "WRONG1",
    })
    assert res.status_code == 403


def test_a_submitted_candidate_cannot_start_again(client, db_session):
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session, count=10)
    candidate = _candidates(db_session, session, n=1)[0]
    client.post("/api/auth/logout")

    creds = {
        "registration_number": candidate.registration_number,
        "access_code": candidate.access_code,
    }
    client.post(f"/api/exams/{session.code}/start", json=creds)
    client.post(f"/api/exams/{session.code}/submit", json=creds)

    assert client.post(f"/api/exams/{session.code}/start", json=creds).status_code == 409


def test_answers_survive_a_dead_phone(client, db_session):
    """
    Saved one at a time rather than all at the end, so a battery dying at
    question 48 does not lose the first 47.
    """
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session, count=10)
    candidate = _candidates(db_session, session, n=1)[0]
    client.post("/api/auth/logout")

    creds = {
        "registration_number": candidate.registration_number,
        "access_code": candidate.access_code,
    }
    client.post(f"/api/exams/{session.code}/start", json=creds)
    client.post(f"/api/exams/{session.code}/answer", json={
        **creds, "question_id": candidate.question_order[0], "selected_option": "B",
    })

    resumed = client.post(f"/api/exams/{session.code}/start", json=creds).json()
    assert resumed["answers"], "the answer came back on resume"


def test_an_exam_outside_its_window_cannot_be_started(client, db_session):
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session, open_now=False)
    candidate = _candidates(db_session, session, n=1)[0]
    client.post("/api/auth/logout")

    res = client.post(f"/api/exams/{session.code}/start", json={
        "registration_number": candidate.registration_number,
        "access_code": candidate.access_code,
    })
    assert res.status_code == 403


def test_results_are_admin_only(client, register_user, db_session):
    _seed_bank(db_session)
    session = _session(db_session)
    register_user()
    assert client.get(f"/api/exams/manage/sessions/{session.id}/results").status_code == 403


def test_results_report_the_hardest_questions(client, db_session):
    """
    What turns a mark sheet into something a teacher can teach from: the
    questions the class as a whole failed.
    """
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session, count=10)
    made = _candidates(db_session, session, n=4)

    for c in made:
        c.answers = {str(session.question_ids[0]): "A"}   # everyone wrong on the first
        c.answers[str(session.question_ids[1])] = "B"     # everyone right on the second
        exams.submit(db_session, session, c)
    db_session.commit()

    body = client.get(f"/api/exams/manage/sessions/{session.id}/results").json()
    assert body["hardest_questions"][0]["percent_correct"] == 0
    assert body["average_percent"] is not None


def test_the_csv_export_carries_every_candidate(client, db_session):
    _seed_bank(db_session)
    _admin(client, db_session)
    session = _session(db_session, count=10)
    made = _candidates(db_session, session, n=3)
    for c in made:
        exams.submit(db_session, session, c)
    db_session.commit()

    res = client.get(f"/api/exams/manage/sessions/{session.id}/results.csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    body = res.text
    for c in made:
        assert c.registration_number in body
