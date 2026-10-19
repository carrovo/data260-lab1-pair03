import re
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.ai.agent import run_assistant
from backend.app.ai.ollama_client import FakeModelClient
from backend.app.ai.tools import (
    TOOL_IMPLEMENTATIONS,
    TOOL_SCHEMAS,
    get_job_details,
    get_student_preferences,
    save_job_or_event,
    search_events,
    search_jobs,
)
from backend.app.database import Base
from backend.app.models import (
    Company,
    Event,
    Job,
    SavedItem,
    Student,
    StudentPreferences,
)


SENSITIVE_VALUES = (
    "private-alpha@example.com",
    "private-alpha-password-hash",
    "private-alpha-storage-key",
    "private-contact@example.com",
)


def _tool_call(name, arguments):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": f"call-{name}",
            "function": {"name": name, "arguments": arguments},
        }],
    }


def _text_response(content):
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": None,
    }


def _result_ids(result):
    return {int(value) for value in re.findall(r"- id=(\d+)", result)}


@pytest.fixture
def ai_tool_context():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        primary_student = Student(
            email="primary.student@example.com",
            password_hash="private-primary-student-password",
            full_name="Primary Student",
            city="San Jose",
            major="Data Science",
            skills="Python, SQL",
        )
        partial_student = Student(
            email="partial.student@example.com",
            password_hash="private-partial-student-password",
            full_name="Partial Student",
            city="Santa Clara",
        )
        missing_student = Student(
            email="missing.student@example.com",
            password_hash="private-missing-student-password",
            full_name="Missing Preferences Student",
            city="Fremont",
        )
        null_student = Student(
            email="null.student@example.com",
            password_hash="private-null-student-password",
            full_name="Null Preferences Student",
            city="San Jose",
        )
        db.add_all([
            primary_student,
            partial_student,
            missing_student,
            null_student,
        ])
        db.flush()

        db.add_all([
            StudentPreferences(
                student_id=primary_student.id,
                job_preferences={
                    "title": "Data",
                    "company": "Alpha",
                    "category": "internship",
                    "city": "San Jose",
                    "skills": ["Python", "SQL"],
                    "min_salary": "25.00",
                },
                event_preferences={
                    "city": "San Jose",
                    "major": "Data Science",
                    "eligibility": "Juniors",
                },
            ),
            StudentPreferences(
                student_id=partial_student.id,
                job_preferences={"city": "Santa Clara"},
            ),
            StudentPreferences(student_id=null_student.id),
        ])

        alpha = Company(
            email=SENSITIVE_VALUES[0],
            password_hash=SENSITIVE_VALUES[1],
            name="Alpha Analytics",
            city="San Jose",
            description="Builds responsible analytics products.",
            contact_info=SENSITIVE_VALUES[3],
            profile_picture_storage_key=SENSITIVE_VALUES[2],
        )
        beta = Company(
            email="private-beta@example.com",
            password_hash="private-beta-password-hash",
            name="Beta Systems",
            city="Santa Clara",
        )
        db.add_all([alpha, beta])
        db.flush()

        data_intern = Job(
            company_id=alpha.id,
            title="Data Analyst Intern",
            description="Analyze product data and build dashboards.",
            city="San Jose",
            category="internship",
            location="Downtown office",
            is_remote=False,
            salary=Decimal("30.50"),
            skills="Python, SQL, Tableau",
            deadline=datetime(2030, 6, 15, 17, 0),
            created_at=datetime(2030, 1, 3, 9, 0),
        )
        product_manager = Job(
            company_id=beta.id,
            title="Product Manager",
            description="Guide software product strategy.",
            city="Santa Clara",
            category="full_time",
            location="North campus",
            is_remote=True,
            salary=Decimal("120000.00"),
            skills="Strategy, SQL",
            deadline=datetime(2031, 1, 31, 17, 0),
            created_at=datetime(2030, 1, 2, 9, 0),
        )
        data_engineer = Job(
            company_id=alpha.id,
            title="Senior Data Engineer",
            description="Build reliable data pipelines.",
            city="Fremont",
            category="full_time",
            location="Engineering center",
            is_remote=True,
            salary=Decimal("150000.00"),
            skills="Python, AWS, Spark",
            deadline=None,
            created_at=datetime(2030, 1, 1, 9, 0),
        )
        db.add_all([data_intern, product_manager, data_engineer])
        db.flush()

        data_fair = Event(
            company_id=alpha.id,
            title="Data Career Fair",
            description="Meet analytics employers.",
            city="San Jose",
            starts_at=datetime(2030, 5, 1, 10, 0),
            ends_at=datetime(2030, 5, 1, 14, 0),
            location="Student Union",
            major="Data Science",
            eligibility="Juniors and seniors",
        )
        cs_workshop = Event(
            company_id=beta.id,
            title="Software Interview Workshop",
            description="Practice technical interviews.",
            city="Santa Clara",
            starts_at=datetime(2030, 6, 15, 13, 0),
            ends_at=datetime(2030, 6, 15, 15, 0),
            location="Innovation Hall",
            major="Computer Science",
            eligibility="Open to all students",
        )
        alumni_event = Event(
            company_id=None,
            title="Alumni Networking Night",
            description="Connect with alumni mentors.",
            city="Fremont",
            starts_at=datetime(2030, 7, 20, 18, 0),
            ends_at=datetime(2030, 7, 20, 20, 0),
            location="Community Center",
            major=None,
            eligibility="Alumni and graduating students",
        )
        db.add_all([data_fair, cs_workshop, alumni_event])
        db.flush()

        identifiers = {
            "primary_student": primary_student.id,
            "partial_student": partial_student.id,
            "missing_student": missing_student.id,
            "null_student": null_student.id,
            "data_intern": data_intern.id,
            "product_manager": product_manager.id,
            "data_engineer": data_engineer.id,
            "data_fair": data_fair.id,
            "cs_workshop": cs_workshop.id,
            "alumni_event": alumni_event.id,
        }
        db.commit()

    try:
        yield engine, identifiers
    finally:
        engine.dispose()


def test_get_complete_student_preferences(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = get_student_preferences(
            db,
            student_id=identifiers["primary_student"],
        )

    assert isinstance(result, str)
    assert '"category": "internship"' in result
    assert '"skills": ["Python", "SQL"]' in result
    assert '"major": "Data Science"' in result


def test_get_partial_student_preferences(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = get_student_preferences(
            db,
            student_id=identifiers["partial_student"],
        )

    assert '"city": "Santa Clara"' in result
    assert "Saved event preferences: none saved." in result


@pytest.mark.parametrize("student_key", ["missing_student", "null_student"])
def test_get_missing_student_preferences(ai_tool_context, student_key):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = get_student_preferences(
            db,
            student_id=identifiers[student_key],
        )

    assert result == "No saved job or event preferences were found."


@pytest.mark.parametrize(
    ("arguments", "expected_keys"),
    [
        ({"title": "analyst"}, {"data_intern"}),
        ({"company": "Alpha"}, {"data_intern", "data_engineer"}),
        ({"category": "internship"}, {"data_intern"}),
        ({"city": "Santa Clara"}, {"product_manager"}),
        ({"min_salary": 130000}, {"data_engineer"}),
        ({"skills": "Python, AWS"}, {"data_engineer"}),
        ({"deadline_before": "2030-12-31"}, {"data_intern"}),
    ],
)
def test_search_jobs_supports_each_filter(
    ai_tool_context,
    arguments,
    expected_keys,
):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = search_jobs(db, **arguments)

    assert _result_ids(result) == {
        identifiers[key] for key in expected_keys
    }


def test_search_jobs_combines_filters_case_insensitively(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = search_jobs(
            db,
            title="dAtA",
            company="aLpHa",
            category="internship",
            city="sAn JoSe",
            min_salary="25.00",
            skills="python, sql",
            deadline_before="2030-06-30",
        )

    assert _result_ids(result) == {identifiers["data_intern"]}
    assert "Alpha Analytics" in result


@pytest.mark.parametrize(
    "suffix",
    [
        "job",
        "jobs",
        "role",
        "roles",
        "position",
        "positions",
        "opportunity",
        "opportunities",
    ],
)
def test_search_jobs_normalizes_generic_trailing_title_words(
    ai_tool_context,
    suffix,
):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = search_jobs(
            db,
            title=f"data analyst intern {suffix}",
            city="San Jose",
        )

    assert _result_ids(result) == {identifiers["data_intern"]}
    assert "Data Analyst Intern" in result


def test_search_jobs_keeps_normal_title_search_behavior(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = search_jobs(db, title="Data Analyst Intern")

    assert _result_ids(result) == {identifiers["data_intern"]}


def test_normalized_job_title_preserves_compatible_filters(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        matching = search_jobs(
            db,
            title="data analyst intern opportunities",
            company="Alpha",
            category="internship",
            city="San Jose",
            min_salary="25.00",
            skills="Python, SQL",
            deadline_before="2030-06-30",
        )

    assert _result_ids(matching) == {identifiers["data_intern"]}


@pytest.mark.parametrize(
    "conflicting_filter",
    [
        {"company": "Beta"},
        {"category": "full_time"},
        {"city": "Santa Clara"},
        {"min_salary": "31.00"},
        {"skills": "AWS"},
        {"deadline_before": "2029-12-31"},
    ],
)
def test_normalized_job_title_keeps_other_filters_enforced(
    ai_tool_context,
    conflicting_filter,
):
    engine, _ = ai_tool_context

    with Session(engine) as db:
        result = search_jobs(
            db,
            title="data analyst intern positions",
            **conflicting_filter,
        )

    assert result == "No jobs matched those filters."


def test_normalized_job_title_preserves_genuine_no_match(ai_tool_context):
    engine, _ = ai_tool_context

    with Session(engine) as db:
        result = search_jobs(db, title="Quantum Farmer roles")
        generic_only = search_jobs(db, title="jobs")

    assert result == "No jobs matched those filters."
    assert generic_only == "No jobs matched those filters."


def test_normalized_job_search_excludes_sensitive_fields(ai_tool_context):
    engine, _ = ai_tool_context

    with Session(engine) as db:
        result = search_jobs(db, title="data analyst intern jobs")

    assert all(secret not in result for secret in SENSITIVE_VALUES)
    assert "private-primary-student-password" not in result
    assert "password_hash" not in result
    assert "storage_key" not in result


def test_search_jobs_returns_clear_no_match_and_validation_strings(
    ai_tool_context,
):
    engine, _ = ai_tool_context

    with Session(engine) as db:
        no_match = search_jobs(db, title="Quantum Farmer")
        invalid = search_jobs(db, min_salary=-1)
        unknown = search_jobs(db, unsupported_filter="value")

    assert no_match == "No jobs matched those filters."
    assert invalid.startswith("Invalid tool arguments:")
    assert unknown.startswith("Invalid tool arguments:")


def test_get_job_details_success_and_not_found(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = get_job_details(db, job_id=identifiers["data_intern"])
        missing = get_job_details(db, job_id=999999)

    assert f"Job #{identifiers['data_intern']}: Data Analyst Intern" in result
    assert "Company: Alpha Analytics" in result
    assert "Salary: 30.50" in result
    assert "Description: Analyze product data" in result
    assert missing == "No job was found with id 999999."


@pytest.mark.parametrize(
    ("arguments", "expected_keys"),
    [
        ({"name": "career"}, {"data_fair"}),
        ({"city": "Santa Clara"}, {"cs_workshop"}),
        (
            {"start_date": "2030-06-01"},
            {"cs_workshop", "alumni_event"},
        ),
        (
            {"end_date": "2030-06-30"},
            {"data_fair", "cs_workshop"},
        ),
        ({"major": "data science"}, {"data_fair"}),
        ({"eligibility": "alumni"}, {"alumni_event"}),
    ],
)
def test_search_events_supports_each_filter(
    ai_tool_context,
    arguments,
    expected_keys,
):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = search_events(db, **arguments)

    assert _result_ids(result) == {
        identifiers[key] for key in expected_keys
    }


def test_search_events_combines_filters(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = search_events(
            db,
            name="DATA",
            city="san jose",
            start_date="2030-05-01",
            end_date="2030-05-01",
            major="science",
            eligibility="juniors",
        )

    assert _result_ids(result) == {identifiers["data_fair"]}
    assert "company=Alpha Analytics" in result


def test_search_events_rejects_invalid_date_range(ai_tool_context):
    engine, _ = ai_tool_context

    with Session(engine) as db:
        result = search_events(
            db,
            start_date="2030-07-01",
            end_date="2030-06-01",
        )

    assert result.startswith("Invalid tool arguments:")


def test_save_job_and_event(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        job_result = save_job_or_event(
            db,
            student_id=identifiers["primary_student"],
            item_type="job",
            item_id=identifiers["data_intern"],
        )
        event_result = save_job_or_event(
            db,
            student_id=identifiers["primary_student"],
            item_type="event",
            item_id=identifiers["data_fair"],
        )

        saves = db.scalars(
            select(SavedItem).where(
                SavedItem.student_id == identifiers["primary_student"]
            )
        ).all()

    assert job_result == f"Saved job #{identifiers['data_intern']}."
    assert event_result == f"Saved event #{identifiers['data_fair']}."
    assert {(item.item_type, item.job_id, item.event_id) for item in saves} == {
        ("job", identifiers["data_intern"], None),
        ("event", None, identifiers["data_fair"]),
    }


@pytest.mark.parametrize(
    "arguments",
    [
        {"item_type": "profile", "item_id": 1},
        {"item_type": "job", "item_id": 0},
        {"item_type": "job"},
    ],
)
def test_save_rejects_invalid_arguments(ai_tool_context, arguments):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = save_job_or_event(
            db,
            student_id=identifiers["primary_student"],
            **arguments,
        )

    assert isinstance(result, str)
    assert result.startswith("Invalid tool arguments:")


@pytest.mark.parametrize("item_type", ["job", "event"])
def test_save_rejects_nonexistent_target(ai_tool_context, item_type):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        result = save_job_or_event(
            db,
            student_id=identifiers["primary_student"],
            item_type=item_type,
            item_id=999999,
        )

    assert result == (
        f"No {item_type} was found with id 999999; nothing was saved."
    )


def test_duplicate_save_is_deterministic(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        first = save_job_or_event(
            db,
            student_id=identifiers["primary_student"],
            item_type="job",
            item_id=identifiers["data_intern"],
        )
        second = save_job_or_event(
            db,
            student_id=identifiers["primary_student"],
            item_type="job",
            item_id=identifiers["data_intern"],
        )
        count = db.scalar(select(func.count(SavedItem.id)))

    assert first.startswith("Saved job")
    assert second == (
        "This job is already saved; no duplicate was created."
    )
    assert count == 1


class RaceDuplicateSession:
    def __init__(self):
        self.rolled_back = False

    def get(self, *args, **kwargs):
        return object()

    def scalar(self, *args, **kwargs):
        return None

    def add(self, *args, **kwargs):
        return None

    def commit(self):
        raise IntegrityError("insert", {}, Exception("duplicate"))

    def rollback(self):
        self.rolled_back = True


def test_duplicate_save_race_returns_deterministic_string():
    db = RaceDuplicateSession()

    result = save_job_or_event(
        db,
        student_id=1,
        item_type="job",
        item_id=1,
    )

    assert result == "This job is already saved; no duplicate was created."
    assert db.rolled_back is True


def test_trusted_student_context_is_required(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        preferences_result = get_student_preferences(db)
        save_result = save_job_or_event(
            db,
            item_type="job",
            item_id=identifiers["data_intern"],
        )

    assert "authenticated student missing" in preferences_result
    assert "authenticated student missing" in save_result


def test_saves_are_isolated_by_trusted_student(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        for student_key in ("primary_student", "partial_student"):
            result = save_job_or_event(
                db,
                student_id=identifiers[student_key],
                item_type="job",
                item_id=identifiers["data_intern"],
            )
            assert result.startswith("Saved job")

        student_ids = set(
            db.scalars(select(SavedItem.student_id)).all()
        )

    assert student_ids == {
        identifiers["primary_student"],
        identifiers["partial_student"],
    }


def test_agent_overrides_model_supplied_student_id(ai_tool_context):
    engine, identifiers = ai_tool_context
    model = FakeModelClient([
        _tool_call(
            "save_job_or_event",
            {
                "item_type": "job",
                "item_id": identifiers["data_intern"],
                "student_id": identifiers["primary_student"],
            },
        ),
        _text_response("The job was saved."),
    ])

    with Session(engine) as db:
        result = run_assistant(
            db,
            "Save job for me.",
            [],
            model,
            student_id=identifiers["partial_student"],
            auto_approve=True,
            tool_schemas=TOOL_SCHEMAS,
            tool_implementations=TOOL_IMPLEMENTATIONS,
        )
        saved_item = db.scalar(select(SavedItem))

    assert result["reply"] == "The job was saved."
    assert saved_item.student_id == identifiers["partial_student"]
    assert saved_item.student_id != identifiers["primary_student"]


def test_agent_discards_model_student_id_without_trusted_context(
    ai_tool_context,
):
    engine, identifiers = ai_tool_context
    model = FakeModelClient([
        _tool_call(
            "save_job_or_event",
            {
                "item_type": "job",
                "item_id": identifiers["data_intern"],
                "student_id": identifiers["primary_student"],
            },
        ),
        _text_response("The save was not authorized."),
    ])

    with Session(engine) as db:
        result = run_assistant(
            db,
            "Save job for me.",
            [],
            model,
            student_id=None,
            auto_approve=True,
            tool_schemas=TOOL_SCHEMAS,
            tool_implementations=TOOL_IMPLEMENTATIONS,
        )
        saved_count = db.scalar(select(func.count(SavedItem.id)))

    tool_messages = [
        message
        for message in result["conversation"]
        if message["role"] == "tool"
    ]
    assert saved_count == 0
    assert "authenticated student missing" in tool_messages[0]["content"]


class FailingSession:
    def get(self, *args, **kwargs):
        raise SQLAlchemyError("forced database failure")

    def execute(self, *args, **kwargs):
        raise SQLAlchemyError("forced database failure")

    def rollback(self):
        return None


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        (get_student_preferences, {"student_id": 1}),
        (search_jobs, {}),
        (get_job_details, {"job_id": 1}),
        (search_events, {}),
        (
            save_job_or_event,
            {"student_id": 1, "item_type": "job", "item_id": 1},
        ),
    ],
)
def test_database_failures_return_strings(tool, arguments):
    result = tool(FailingSession(), **arguments)

    assert isinstance(result, str)
    assert "database operation failed" in result
    assert "forced database failure" not in result


def test_tool_outputs_exclude_sensitive_fields(ai_tool_context):
    engine, identifiers = ai_tool_context

    with Session(engine) as db:
        outputs = [
            get_student_preferences(
                db,
                student_id=identifiers["primary_student"],
            ),
            search_jobs(db),
            get_job_details(db, job_id=identifiers["data_intern"]),
            search_events(db),
        ]

    combined = "\n".join(outputs)
    assert all(secret not in combined for secret in SENSITIVE_VALUES)
    assert "password_hash" not in combined
    assert "storage_key" not in combined


def test_model_visible_tool_schemas_are_complete_and_trusted():
    schemas_by_name = {
        schema["function"]["name"]: schema["function"]
        for schema in TOOL_SCHEMAS
    }

    assert set(schemas_by_name) == {
        "get_student_preferences",
        "search_jobs",
        "get_job_details",
        "search_events",
        "save_job_or_event",
    }
    assert set(TOOL_IMPLEMENTATIONS) == set(schemas_by_name)
    assert set(
        schemas_by_name["search_jobs"]["parameters"]["properties"]
    ) == {
        "title",
        "company",
        "category",
        "city",
        "min_salary",
        "skills",
        "deadline_before",
    }
    assert set(
        schemas_by_name["search_events"]["parameters"]["properties"]
    ) == {
        "name",
        "city",
        "start_date",
        "end_date",
        "major",
        "eligibility",
    }
    assert set(
        schemas_by_name["save_job_or_event"]["parameters"]["properties"]
    ) == {"item_type", "item_id"}

    for function in schemas_by_name.values():
        parameters = function["parameters"]
        assert parameters["type"] == "object"
        assert parameters["additionalProperties"] is False
        assert "student_id" not in parameters["properties"]
