"""Database-backed tools exposed to the student AI assistant."""

import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import Select, and_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.models import (
    Company,
    Event,
    Job,
    SavedItem,
    Student,
    StudentPreferences,
)
from backend.app.schemas.job import JobCategory
from backend.app.schemas.preferences import (
    EventSearchPreferences,
    JobSearchPreferences,
)


MAX_TOOL_RESULTS = 10
GENERIC_JOB_TITLE_SUFFIXES = frozenset({
    "job",
    "jobs",
    "role",
    "roles",
    "position",
    "positions",
    "opportunity",
    "opportunities",
})


class _ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _NoArguments(_ToolArguments):
    pass


class _JobSearchArguments(_ToolArguments):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    company: str | None = Field(default=None, min_length=1, max_length=255)
    category: JobCategory | None = None
    city: str | None = Field(default=None, min_length=1, max_length=100)
    min_salary: Decimal | None = Field(default=None, ge=0)
    skills: str | None = Field(default=None, min_length=1, max_length=1000)
    deadline_before: date | datetime | None = None


class _JobDetailsArguments(_ToolArguments):
    job_id: int = Field(gt=0)


class _EventSearchArguments(_ToolArguments):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | datetime | None = None
    end_date: date | datetime | None = None
    major: str | None = Field(default=None, min_length=1, max_length=255)
    eligibility: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    @model_validator(mode="after")
    def validate_date_range(self):
        start = _start_boundary(self.start_date)
        end = _end_boundary(self.end_date)
        if start is not None and end is not None and end < start:
            raise ValueError("end_date must be on or after start_date.")
        return self


class _SaveArguments(_ToolArguments):
    item_type: Literal["job", "event"]
    item_id: int = Field(gt=0)


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_student_preferences",
            "description": (
                "Return the authenticated student's saved job and event "
                "search preferences. Call this before a search that depends "
                "on the student's preferences."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_jobs",
            "description": (
                "Search jobs using any combination of title, company, "
                "category, city, minimum salary, skills, and deadline."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [category.value for category in JobCategory],
                    },
                    "city": {"type": "string"},
                    "min_salary": {"type": "number", "minimum": 0},
                    "skills": {
                        "type": "string",
                        "description": "Comma-separated required skills.",
                    },
                    "deadline_before": {
                        "type": "string",
                        "description": "ISO-8601 date or datetime.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_details",
            "description": (
                "Return full, non-sensitive details for one job posting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "integer", "minimum": 1},
                },
                "required": ["job_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": (
                "Search events by name, city, date range, major, and "
                "eligibility."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "city": {"type": "string"},
                    "start_date": {
                        "type": "string",
                        "description": "ISO-8601 date or datetime.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "ISO-8601 date or datetime.",
                    },
                    "major": {"type": "string"},
                    "eligibility": {"type": "string"},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_job_or_event",
            "description": (
                "Save one existing job or event for the authenticated "
                "student. This state-changing action requires confirmation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item_type": {
                        "type": "string",
                        "enum": ["job", "event"],
                    },
                    "item_id": {"type": "integer", "minimum": 1},
                },
                "required": ["item_type", "item_id"],
                "additionalProperties": False,
            },
        },
    },
]


def _without_trusted_context(arguments: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(arguments)
    cleaned.pop("student_id", None)
    return cleaned


def _validation_error(error: ValidationError) -> str:
    first_error = error.errors(include_input=False)[0]
    location = ".".join(str(part) for part in first_error["loc"])
    prefix = f"{location}: " if location else ""
    return f"Invalid tool arguments: {prefix}{first_error['msg']}."


def _rollback_safely(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _start_boundary(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _normalize_datetime(value)
    return datetime.combine(value, time.min)


def _end_boundary(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _normalize_datetime(value)
    return datetime.combine(value, time.max)


def _format_datetime(value: datetime | None) -> str:
    return value.isoformat(sep=" ", timespec="minutes") if value else "None"


def _format_decimal(value: Decimal | None) -> str:
    return f"{value:.2f}" if value is not None else "None"


def _job_title_fallback(title: str) -> str | None:
    """Remove only generic trailing search words from a title phrase."""

    words = title.split()
    end = len(words)

    while end > 0:
        trailing_word = words[end - 1].casefold().rstrip(".,!?;:")
        if trailing_word not in GENERIC_JOB_TITLE_SUFFIXES:
            break
        end -= 1

    if end == 0 or end == len(words):
        return None
    return " ".join(words[:end])


def _validated_preferences(
    preferences: StudentPreferences,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    job_preferences = None
    event_preferences = None

    if preferences.job_preferences is not None:
        job_preferences = JobSearchPreferences.model_validate(
            preferences.job_preferences
        ).model_dump(mode="json", exclude_none=True)
    if preferences.event_preferences is not None:
        event_preferences = EventSearchPreferences.model_validate(
            preferences.event_preferences
        ).model_dump(mode="json", exclude_none=True)

    return job_preferences, event_preferences


def get_student_preferences(
    db: Session,
    student_id: int | None = None,
    **arguments: Any,
) -> str:
    """Return only the authenticated student's stored preferences."""

    try:
        _NoArguments.model_validate(_without_trusted_context(arguments))
        if student_id is None or student_id < 1:
            return "Unable to read preferences: authenticated student missing."

        student = db.get(Student, student_id)
        if student is None:
            return "No authenticated student record was found."

        preferences = db.get(StudentPreferences, student_id)
        if preferences is None:
            return "No saved job or event preferences were found."

        job_preferences, event_preferences = _validated_preferences(
            preferences
        )
        if job_preferences is None and event_preferences is None:
            return "No saved job or event preferences were found."

        job_text = (
            json.dumps(job_preferences, sort_keys=True)
            if job_preferences is not None
            else "none saved"
        )
        event_text = (
            json.dumps(event_preferences, sort_keys=True)
            if event_preferences is not None
            else "none saved"
        )
        return (
            f"Saved job preferences: {job_text}. "
            f"Saved event preferences: {event_text}."
        )
    except ValidationError as error:
        return _validation_error(error)
    except SQLAlchemyError:
        return "Unable to read preferences because the database operation failed."
    except Exception:
        return "Unable to read preferences because the stored data is invalid."


def _job_search_statement(arguments: _JobSearchArguments) -> Select:
    statement = select(Job, Company).join(Company, Job.company_id == Company.id)

    if arguments.title:
        statement = statement.where(
            Job.title.ilike(f"%{arguments.title}%")
        )
    if arguments.company:
        statement = statement.where(
            Company.name.ilike(f"%{arguments.company}%")
        )
    if arguments.category:
        statement = statement.where(Job.category == arguments.category.value)
    if arguments.city:
        statement = statement.where(Job.city.ilike(f"%{arguments.city}%"))
    if arguments.min_salary is not None:
        statement = statement.where(Job.salary >= arguments.min_salary)
    if arguments.skills:
        skills = [
            skill.strip()
            for skill in arguments.skills.split(",")
            if skill.strip()
        ]
        for skill in skills:
            statement = statement.where(Job.skills.ilike(f"%{skill}%"))
    if arguments.deadline_before is not None:
        deadline = _end_boundary(arguments.deadline_before)
        statement = statement.where(
            and_(Job.deadline.is_not(None), Job.deadline <= deadline)
        )

    return statement.order_by(Job.created_at.desc(), Job.id.desc()).limit(
        MAX_TOOL_RESULTS
    )


def search_jobs(db: Session, **arguments: Any) -> str:
    """Search canonical jobs and return a bounded non-sensitive summary."""

    try:
        validated = _JobSearchArguments.model_validate(
            _without_trusted_context(arguments)
        )
        rows = db.execute(_job_search_statement(validated)).all()
        if not rows and validated.title:
            fallback_title = _job_title_fallback(validated.title)
            if fallback_title is not None:
                fallback_arguments = validated.model_copy(
                    update={"title": fallback_title}
                )
                rows = db.execute(
                    _job_search_statement(fallback_arguments)
                ).all()
        if not rows:
            return "No jobs matched those filters."

        lines = []
        for job, company in rows:
            lines.append(
                f"- id={job.id} | {job.title} | company={company.name} | "
                f"category={job.category or 'None'} | city={job.city} | "
                f"location={job.location or 'None'} | "
                f"remote={'yes' if job.is_remote else 'no'} | "
                f"salary={_format_decimal(job.salary)} | "
                f"skills={job.skills or 'None'} | "
                f"deadline={_format_datetime(job.deadline)}"
            )
        return "Matching jobs:\n" + "\n".join(lines)
    except ValidationError as error:
        return _validation_error(error)
    except SQLAlchemyError:
        return "Unable to search jobs because the database operation failed."
    except Exception:
        return "Unable to search jobs because an unexpected error occurred."


def get_job_details(db: Session, **arguments: Any) -> str:
    """Return one job with public company information only."""

    try:
        validated = _JobDetailsArguments.model_validate(
            _without_trusted_context(arguments)
        )
        row = db.execute(
            select(Job, Company)
            .join(Company, Job.company_id == Company.id)
            .where(Job.id == validated.job_id)
        ).one_or_none()
        if row is None:
            return f"No job was found with id {validated.job_id}."

        job, company = row
        return (
            f"Job #{job.id}: {job.title}\n"
            f"Company: {company.name}\n"
            f"Company city: {company.city}\n"
            f"Company description: {company.description or 'None'}\n"
            f"Category: {job.category or 'None'}\n"
            f"City: {job.city}\n"
            f"Location: {job.location or 'None'}\n"
            f"Remote: {'yes' if job.is_remote else 'no'}\n"
            f"Salary: {_format_decimal(job.salary)}\n"
            f"Skills: {job.skills or 'None'}\n"
            f"Deadline: {_format_datetime(job.deadline)}\n"
            f"Created: {_format_datetime(job.created_at)}\n"
            f"Description: {job.description}"
        )
    except ValidationError as error:
        return _validation_error(error)
    except SQLAlchemyError:
        return "Unable to load the job because the database operation failed."
    except Exception:
        return "Unable to load the job because an unexpected error occurred."


def _event_search_statement(arguments: _EventSearchArguments) -> Select:
    statement = select(Event, Company).outerjoin(
        Company,
        Event.company_id == Company.id,
    )

    if arguments.name:
        statement = statement.where(
            Event.title.ilike(f"%{arguments.name}%")
        )
    if arguments.city:
        statement = statement.where(
            Event.city.ilike(f"%{arguments.city}%")
        )
    if arguments.start_date is not None:
        statement = statement.where(
            Event.starts_at >= _start_boundary(arguments.start_date)
        )
    if arguments.end_date is not None:
        statement = statement.where(
            Event.starts_at <= _end_boundary(arguments.end_date)
        )
    if arguments.major:
        statement = statement.where(
            Event.major.ilike(f"%{arguments.major}%")
        )
    if arguments.eligibility:
        statement = statement.where(
            Event.eligibility.ilike(f"%{arguments.eligibility}%")
        )

    return statement.order_by(Event.starts_at.asc(), Event.id.asc()).limit(
        MAX_TOOL_RESULTS
    )


def search_events(db: Session, **arguments: Any) -> str:
    """Search canonical events and return a bounded public summary."""

    try:
        validated = _EventSearchArguments.model_validate(
            _without_trusted_context(arguments)
        )
        rows = db.execute(_event_search_statement(validated)).all()
        if not rows:
            return "No events matched those filters."

        lines = []
        for event, company in rows:
            company_name = company.name if company is not None else "None"
            lines.append(
                f"- id={event.id} | {event.title} | "
                f"company={company_name} | city={event.city} | "
                f"location={event.location or 'None'} | "
                f"starts={_format_datetime(event.starts_at)} | "
                f"ends={_format_datetime(event.ends_at)} | "
                f"major={event.major or 'None'} | "
                f"eligibility={event.eligibility or 'None'} | "
                f"description={event.description}"
            )
        return "Matching events:\n" + "\n".join(lines)
    except ValidationError as error:
        return _validation_error(error)
    except SQLAlchemyError:
        return "Unable to search events because the database operation failed."
    except Exception:
        return "Unable to search events because an unexpected error occurred."


def save_job_or_event(
    db: Session,
    student_id: int | None = None,
    **arguments: Any,
) -> str:
    """Save an existing target for the trusted authenticated student."""

    try:
        validated = _SaveArguments.model_validate(
            _without_trusted_context(arguments)
        )
        if student_id is None or student_id < 1:
            return "Unable to save: authenticated student missing."
        if db.get(Student, student_id) is None:
            return "No authenticated student record was found."

        target_model = Job if validated.item_type == "job" else Event
        if db.get(target_model, validated.item_id) is None:
            return (
                f"No {validated.item_type} was found with id "
                f"{validated.item_id}; nothing was saved."
            )

        target_column = (
            SavedItem.job_id
            if validated.item_type == "job"
            else SavedItem.event_id
        )
        existing_id = db.scalar(
            select(SavedItem.id).where(
                SavedItem.student_id == student_id,
                target_column == validated.item_id,
            )
        )
        if existing_id is not None:
            return (
                f"This {validated.item_type} is already saved; "
                "no duplicate was created."
            )

        saved_item = SavedItem(
            student_id=student_id,
            item_type=validated.item_type,
            job_id=(
                validated.item_id
                if validated.item_type == "job"
                else None
            ),
            event_id=(
                validated.item_id
                if validated.item_type == "event"
                else None
            ),
        )
        db.add(saved_item)
        try:
            db.commit()
        except IntegrityError:
            _rollback_safely(db)
            return (
                f"This {validated.item_type} is already saved; "
                "no duplicate was created."
            )
        except SQLAlchemyError:
            _rollback_safely(db)
            return "Unable to save because the database operation failed."

        return f"Saved {validated.item_type} #{validated.item_id}."
    except ValidationError as error:
        return _validation_error(error)
    except SQLAlchemyError:
        _rollback_safely(db)
        return "Unable to save because the database operation failed."
    except Exception:
        _rollback_safely(db)
        return "Unable to save because an unexpected error occurred."


TOOL_IMPLEMENTATIONS = {
    "get_student_preferences": get_student_preferences,
    "search_jobs": search_jobs,
    "get_job_details": get_job_details,
    "search_events": search_events,
    "save_job_or_event": save_job_or_event,
}
