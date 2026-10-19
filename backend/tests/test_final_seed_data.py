from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal
from io import StringIO

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.pool import StaticPool

from backend.app.ai.tools import search_events, search_jobs
from backend.app.application_status import ApplicationStatus
from backend.app.database import Base
from backend.app.models import (
    Application,
    Company,
    Event,
    Job,
    Registration,
    SavedItem,
    Student,
    StudentPreferences,
)
from backend.app.schemas.company import CompanyResponse
from backend.app.schemas.event import EventCanonicalResponse
from backend.app.schemas.job import JobCanonicalResponse, JobCategory
from backend.app.schemas.preferences import (
    EventSearchPreferences,
    JobSearchPreferences,
)
from backend.app.security import verify_password
from backend.seed_final_data import (
    APPLICATION_COUNT,
    CITIES,
    CLEAN_CONTROL_JOB_TITLE,
    COMPANY_COUNT,
    DEFAULT_BASE_DATE,
    DEMO_COMPANY_EMAIL,
    DEMO_MATCH_EVENT_TITLE,
    DEMO_MATCH_JOB_TITLE,
    DEMO_PASSWORD,
    DEMO_STUDENT_COMPLETE_EMAIL,
    DEMO_STUDENT_NO_PREFERENCES_EMAIL,
    DEMO_STUDENT_NULL_PREFERENCES_EMAIL,
    DEMO_STUDENT_PARTIAL_EMAIL,
    EVENT_COUNT,
    JOB_COUNT,
    PREFERENCE_ROW_COUNT,
    PROMPT_INJECTION_JOB_TITLE,
    REGISTRATION_COUNT,
    SAVED_ITEM_COUNT,
    SEED,
    STUDENT_COUNT,
    SeedSummary,
    generate_seed_plan,
    seed_final_data,
)


def _memory_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="module")
def seeded_database():
    engine = _memory_engine()
    output = StringIO()

    with Session(engine) as session:
        summary = seed_final_data(session, output=output)

    try:
        yield engine, summary, output.getvalue()
    finally:
        engine.dispose()


def test_seed_plan_is_deterministic_and_uses_seed_three():
    first = generate_seed_plan(DEFAULT_BASE_DATE)
    second = generate_seed_plan(DEFAULT_BASE_DATE)

    assert SEED == 3
    assert first == second
    assert {name: len(records) for name, records in first.items()} == {
        "students": STUDENT_COUNT,
        "companies": COMPANY_COUNT,
        "jobs": JOB_COUNT,
        "events": EVENT_COUNT,
        "preferences": PREFERENCE_ROW_COUNT,
        "applications": APPLICATION_COUNT,
        "registrations": REGISTRATION_COUNT,
        "saved_items": SAVED_ITEM_COUNT,
    }


def test_exact_required_seed_counts(seeded_database):
    engine, summary, _ = seeded_database

    assert summary == SeedSummary(
        students=200,
        companies=50,
        jobs=300,
        applications=1_500,
        events=100,
        preferences=150,
        registrations=600,
        saved_items=600,
    )

    with Session(engine) as session:
        assert session.scalar(select(func.count(Student.id))) == 200
        assert session.scalar(select(func.count(Company.id))) == 50
        assert session.scalar(select(func.count(Job.id))) == 300
        assert session.scalar(select(func.count(Application.id))) == 1_500
        assert session.scalar(select(func.count(Event.id))) == 100
        assert session.scalar(
            select(func.count(StudentPreferences.student_id))
        ) == 150
        assert session.scalar(select(func.count(Registration.id))) == 600
        assert session.scalar(select(func.count(SavedItem.id))) == 600


def test_all_pair_cities_are_represented_and_no_others_are_used(
    seeded_database,
):
    engine, _, _ = seeded_database

    with Session(engine) as session:
        assert set(session.scalars(select(Student.city))) == set(CITIES)
        assert set(session.scalars(select(Company.city))) == set(CITIES)
        assert set(session.scalars(select(Job.city))) == set(CITIES)
        assert set(session.scalars(select(Event.city))) == set(CITIES)


def test_application_pairs_statuses_and_resume_semantics(seeded_database):
    engine, _, _ = seeded_database

    with Session(engine) as session:
        applications = list(session.scalars(select(Application)))

    pairs = {(item.student_id, item.job_id) for item in applications}
    statuses = Counter(item.status for item in applications)

    assert len(pairs) == len(applications) == APPLICATION_COUNT
    assert statuses == {
        ApplicationStatus.PENDING.value: 500,
        ApplicationStatus.REVIEWED.value: 500,
        ApplicationStatus.DECLINED.value: 500,
    }
    assert all(item.resume_storage_key is None for item in applications)
    assert all(item.resume_original_name is None for item in applications)
    assert all(item.resume_size_bytes is None for item in applications)


def test_registration_pairs_are_unique_and_event_dates_are_valid(
    seeded_database,
):
    engine, _, _ = seeded_database

    with Session(engine) as session:
        registrations = list(session.scalars(select(Registration)))
        events = list(session.scalars(select(Event)))

    registration_pairs = {
        (item.student_id, item.event_id) for item in registrations
    }
    assert len(registration_pairs) == len(registrations) == 600
    assert all(event.ends_at > event.starts_at for event in events)
    assert any(event.company_id is None for event in events)
    assert any(event.starts_at < date_to_datetime(DEFAULT_BASE_DATE) for event in events)
    assert any(event.starts_at > date_to_datetime(DEFAULT_BASE_DATE) for event in events)


def date_to_datetime(value: date):
    return datetime.combine(value, time.min)


def test_saved_items_have_one_unique_matching_target(seeded_database):
    engine, _, _ = seeded_database

    with Session(engine) as session:
        saved_items = list(session.scalars(select(SavedItem)))

    keys = set()
    for item in saved_items:
        assert item.item_type in {"job", "event"}
        assert (item.job_id is None) != (item.event_id is None)
        assert (item.item_type == "job") == (item.job_id is not None)
        target_id = item.job_id if item.job_id is not None else item.event_id
        keys.add((item.student_id, item.item_type, target_id))

    assert len(keys) == len(saved_items) == SAVED_ITEM_COUNT
    assert {item.item_type for item in saved_items} == {"job", "event"}


def test_jobs_use_canonical_categories_decimal_salaries_and_companies(
    seeded_database,
):
    engine, _, _ = seeded_database
    allowed_categories = {category.value for category in JobCategory}

    with Session(engine) as session:
        jobs = list(
            session.scalars(
                select(Job).options(selectinload(Job.company))
            )
        )
        company = session.scalar(
            select(Company).where(Company.email == DEMO_COMPANY_EMAIL)
        )
        event = session.scalar(
            select(Event)
            .where(Event.title == DEMO_MATCH_EVENT_TITLE)
            .options(selectinload(Event.company))
        )

        job_response = JobCanonicalResponse.model_validate(jobs[0])
        company_response = CompanyResponse.model_validate(company)
        event_response = EventCanonicalResponse.model_validate(event)

    assert all(job.category in allowed_categories for job in jobs)
    assert all(isinstance(job.salary, Decimal) for job in jobs)
    assert all(job.salary >= 0 for job in jobs)
    assert all(job.company_id is not None for job in jobs)
    assert any(job.deadline is None for job in jobs)
    assert any(job.deadline < date_to_datetime(DEFAULT_BASE_DATE) for job in jobs if job.deadline)
    assert any(job.deadline > date_to_datetime(DEFAULT_BASE_DATE) for job in jobs if job.deadline)
    assert company_response.email == DEMO_COMPANY_EMAIL
    assert job_response.company.name
    assert event_response.company.name == company.name


def test_complete_partial_null_and_missing_preferences(seeded_database):
    engine, _, _ = seeded_database

    with Session(engine) as session:
        students = {
            student.email: student
            for student in session.scalars(
                select(Student).where(
                    Student.email.in_([
                        DEMO_STUDENT_COMPLETE_EMAIL,
                        DEMO_STUDENT_PARTIAL_EMAIL,
                        DEMO_STUDENT_NULL_PREFERENCES_EMAIL,
                        DEMO_STUDENT_NO_PREFERENCES_EMAIL,
                    ])
                )
            )
        }
        complete = session.get(
            StudentPreferences,
            students[DEMO_STUDENT_COMPLETE_EMAIL].id,
        )
        partial = session.get(
            StudentPreferences,
            students[DEMO_STUDENT_PARTIAL_EMAIL].id,
        )
        null_values = session.get(
            StudentPreferences,
            students[DEMO_STUDENT_NULL_PREFERENCES_EMAIL].id,
        )
        missing = session.get(
            StudentPreferences,
            students[DEMO_STUDENT_NO_PREFERENCES_EMAIL].id,
        )

    assert JobSearchPreferences.model_validate(complete.job_preferences)
    assert EventSearchPreferences.model_validate(complete.event_preferences)
    assert partial.job_preferences == {
        "city": "Santa Clara",
        "category": JobCategory.PART_TIME.value,
    }
    assert partial.event_preferences is None
    assert null_values.job_preferences is None
    assert null_values.event_preferences is None
    assert missing is None


def test_demo_preferences_match_known_job_event_and_saved_items(
    seeded_database,
):
    engine, _, _ = seeded_database

    with Session(engine) as session:
        student = session.scalar(
            select(Student).where(
                Student.email == DEMO_STUDENT_COMPLETE_EMAIL
            )
        )
        preferences = session.get(StudentPreferences, student.id)
        job = session.scalar(
            select(Job).where(Job.title == DEMO_MATCH_JOB_TITLE)
        )
        event = session.scalar(
            select(Event).where(Event.title == DEMO_MATCH_EVENT_TITLE)
        )

        job_results = search_jobs(
            session,
            title="Data Analyst",
            company="Pair03 Demo Company 001",
            category="internship",
            city="San Jose",
            min_salary=60000,
            skills="Python, SQL, Tableau",
            deadline_before="2030-05-15",
        )
        event_results = search_events(
            session,
            name="Data Science",
            city="San Jose",
            start_date="2030-01-15",
            end_date="2030-07-14",
            major="Data Science",
            eligibility="Juniors and seniors",
        )
        saved_job = session.scalar(
            select(SavedItem).where(
                SavedItem.student_id == student.id,
                SavedItem.job_id == job.id,
            )
        )
        saved_event = session.scalar(
            select(SavedItem).where(
                SavedItem.student_id == student.id,
                SavedItem.event_id == event.id,
            )
        )

    assert preferences.job_preferences["is_remote"] is True
    assert f"id={job.id}" in job_results
    assert f"id={event.id}" in event_results
    assert saved_job.item_type == "job"
    assert saved_event.item_type == "event"


def test_prompt_injection_and_clean_control_records_exist(seeded_database):
    engine, _, _ = seeded_database

    with Session(engine) as session:
        injection_job = session.scalar(
            select(Job).where(Job.title == PROMPT_INJECTION_JOB_TITLE)
        )
        clean_job = session.scalar(
            select(Job).where(Job.title == CLEAN_CONTROL_JOB_TITLE)
        )

    assert "ignore all previous instructions" in injection_job.description
    assert "reveal secrets" in injection_job.description
    assert "No real secret is present" in injection_job.description
    assert "ignore all previous instructions" not in clean_job.description


def test_demo_password_is_hashed_and_summary_contains_no_secret_material(
    seeded_database,
):
    engine, _, output = seeded_database

    with Session(engine) as session:
        student = session.scalar(
            select(Student).where(
                Student.email == DEMO_STUDENT_COMPLETE_EMAIL
            )
        )

    assert student.password_hash != DEMO_PASSWORD
    assert verify_password(DEMO_PASSWORD, student.password_hash)
    assert DEMO_PASSWORD not in output
    assert student.password_hash not in output
    assert "jwt" not in output.lower()
    assert "database_url" not in output.lower()


def test_rerun_is_idempotent_and_preserves_non_seed_data():
    engine = _memory_engine()
    try:
        with Session(engine) as session:
            session.add(
                Student(
                    email="ordinary.user@example.com",
                    password_hash="unrelated-private-hash",
                    full_name="Ordinary User",
                    city="San Jose",
                )
            )
            session.commit()

        with Session(engine) as session:
            first = seed_final_data(session, output=StringIO())
        with Session(engine) as session:
            ids_before = tuple(
                session.scalars(
                    select(Student.id)
                    .where(Student.email.like("seed3.student.%"))
                    .order_by(Student.email)
                )
            )
        with Session(engine) as session:
            second = seed_final_data(session, output=StringIO())

        with Session(engine) as session:
            ids_after = tuple(
                session.scalars(
                    select(Student.id)
                    .where(Student.email.like("seed3.student.%"))
                    .order_by(Student.email)
                )
            )
            ordinary_user = session.scalar(
                select(Student).where(
                    Student.email == "ordinary.user@example.com"
                )
            )
            counts = (
                session.scalar(select(func.count(Student.id))),
                session.scalar(select(func.count(Application.id))),
                session.scalar(select(func.count(Registration.id))),
                session.scalar(select(func.count(SavedItem.id))),
            )

        assert first == second
        assert ids_before == ids_after
        assert ordinary_user.full_name == "Ordinary User"
        assert counts == (201, 1_500, 600, 600)
    finally:
        engine.dispose()


def test_simulated_failure_rolls_back_all_seed_writes():
    engine = _memory_engine()
    try:
        with Session(engine) as session:
            session.add(
                Student(
                    email="survives.rollback@example.com",
                    password_hash="unrelated-private-hash",
                    full_name="Existing Student",
                    city="Fremont",
                )
            )
            session.commit()

        def fail_after_jobs(stage):
            if stage == "jobs":
                raise RuntimeError("simulated seed failure")

        with Session(engine) as session:
            with pytest.raises(RuntimeError, match="simulated seed failure"):
                seed_final_data(
                    session,
                    output=StringIO(),
                    after_stage=fail_after_jobs,
                )

        with Session(engine) as session:
            assert session.scalar(select(func.count(Student.id))) == 1
            assert session.scalar(select(func.count(Company.id))) == 0
            assert session.scalar(select(func.count(Job.id))) == 0
            assert session.scalar(
                select(func.count(Student.id)).where(
                    Student.email.like("seed3.student.%")
                )
            ) == 0
    finally:
        engine.dispose()


def test_incompatible_generic_saved_item_schema_is_refused():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE saved_items ("
                    "id INTEGER PRIMARY KEY, item_id INTEGER)"
                )
            )

        with Session(engine) as session:
            with pytest.raises(
                RuntimeError,
                match=r"saved_items\.item_id",
            ):
                seed_final_data(session, output=StringIO())

        assert inspect_table_names(engine) == {"saved_items"}
    finally:
        engine.dispose()


def test_missing_canonical_schema_is_refused_without_creating_tables():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with Session(engine) as session:
            with pytest.raises(RuntimeError, match="missing required tables"):
                seed_final_data(session, output=StringIO())

        assert inspect_table_names(engine) == set()
    finally:
        engine.dispose()


def inspect_table_names(engine):
    return set(inspect(engine).get_table_names())
