from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.application_status import ApplicationStatus
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
    StudentPreferencesResponse,
)
from backend.app.schemas.saved_item import SavedItemCreate
from backend.app.schemas.student_auth import (
    StudentProfileResponse,
    StudentResponse,
)


def create_student(db: Session, suffix: str = "one") -> Student:
    student = Student(
        email=f"student-{suffix}@example.com",
        password_hash="private-student-password-hash",
        full_name=f"Student {suffix}",
        city="San Jose",
    )
    db.add(student)
    db.flush()
    return student


def create_company(db: Session, suffix: str = "one") -> Company:
    company = Company(
        email=f"company-{suffix}@example.com",
        password_hash="private-company-password-hash",
        name=f"Company {suffix}",
        city="San Jose",
    )
    db.add(company)
    db.flush()
    return company


def create_job(db: Session, company: Company, suffix: str = "one") -> Job:
    job = Job(
        company_id=company.id,
        title=f"Data Analyst {suffix}",
        description="Analyze trustworthy datasets.",
        city="San Jose",
    )
    db.add(job)
    db.flush()
    return job


def create_event(
    db: Session,
    company: Company,
    suffix: str = "one",
) -> Event:
    starts_at = datetime.now(timezone.utc) + timedelta(days=7)
    event = Event(
        company_id=company.id,
        title=f"Career Fair {suffix}",
        description="Meet employers.",
        city="San Jose",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=2),
    )
    db.add(event)
    db.flush()
    return event


def test_student_new_fields_and_profile_schema(auth_test_context):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        student.college_name = "San Jose State University"
        student.major = "Data Science"
        student.state = "California"
        student.skills = "Python, SQL"
        db.commit()
        db.refresh(student)

        response = StudentProfileResponse.model_validate(student)

    assert response.college_name == "San Jose State University"
    assert response.major == "Data Science"
    assert response.state == "California"
    assert response.skills == "Python, SQL"
    assert "password_hash" not in response.model_dump()


def test_company_new_fields_use_safe_response_schema(auth_test_context):
    _, engine = auth_test_context

    with Session(engine) as db:
        company = create_company(db)
        company.description = "A data-focused employer."
        company.contact_info = "careers@example.com"
        company.profile_picture_storage_key = "generated-company-key.png"
        db.commit()
        db.refresh(company)

        response = CompanyResponse.model_validate(company)

    assert response.description == "A data-focused employer."
    assert response.contact_info == "careers@example.com"
    assert "password_hash" not in response.model_dump()
    assert "profile_picture_storage_key" not in response.model_dump()


def test_job_new_fields_and_exact_decimal_salary(auth_test_context):
    _, engine = auth_test_context
    deadline = datetime.now(timezone.utc) + timedelta(days=30)

    with Session(engine) as db:
        company = create_company(db)
        job = create_job(db, company)
        job.category = JobCategory.INTERNSHIP.value
        job.location = "Downtown campus"
        job.is_remote = True
        job.salary = Decimal("98765.43")
        job.skills = "Python, SQL"
        job.deadline = deadline
        db.commit()
        db.refresh(job)

        response = JobCanonicalResponse.model_validate(job)

    assert job.salary == Decimal("98765.43")
    assert response.salary == Decimal("98765.43")
    assert response.category is JobCategory.INTERNSHIP
    assert response.is_remote is True
    assert response.created_at is not None


def test_event_new_fields_and_canonical_names(auth_test_context):
    _, engine = auth_test_context

    with Session(engine) as db:
        company = create_company(db)
        event = create_event(db, company)
        event.location = "Student Union"
        event.major = "Computer Science"
        event.eligibility = "Open to enrolled students"
        db.commit()
        db.refresh(event)

        response = EventCanonicalResponse.model_validate(event)

    assert response.title == "Career Fair one"
    assert response.starts_at is not None
    assert response.location == "Student Union"
    assert response.major == "Computer Science"
    assert response.eligibility == "Open to enrolled students"
    assert not hasattr(event, "name")
    assert not hasattr(event, "date")


def test_student_preferences_are_one_to_one_and_typed(auth_test_context):
    _, engine = auth_test_context
    job_preferences = JobSearchPreferences(
        category=JobCategory.INTERNSHIP,
        city="San Jose",
        is_remote=True,
        skills=["Python", "SQL"],
        min_salary=Decimal("25.00"),
    )
    event_preferences = EventSearchPreferences(
        city="San Jose",
        major="Data Science",
        eligibility="Open to students",
    )

    with Session(engine) as db:
        student = create_student(db)
        preferences = StudentPreferences(
            student_id=student.id,
            job_preferences=job_preferences.model_dump(mode="json"),
            event_preferences=event_preferences.model_dump(mode="json"),
        )
        db.add(preferences)
        db.commit()
        db.refresh(preferences)

        assert student.preferences is preferences
        response = StudentPreferencesResponse.model_validate(preferences)
        student_id = student.id

    with Session(engine) as db:
        db.add(StudentPreferences(student_id=student_id))
        with pytest.raises(IntegrityError):
            db.commit()

    assert response.student_id == student_id
    assert response.job_preferences.category is JobCategory.INTERNSHIP
    assert response.job_preferences.min_salary == Decimal("25.00")
    assert response.event_preferences.major == "Data Science"


def test_null_preference_payloads_mean_no_saved_preferences(
    auth_test_context,
):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        preferences = StudentPreferences(student_id=student.id)
        db.add(preferences)
        db.commit()
        db.refresh(preferences)

        response = StudentPreferencesResponse.model_validate(preferences)

    assert response.job_preferences is None
    assert response.event_preferences is None


def test_saved_item_job_save(auth_test_context):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        company = create_company(db)
        job = create_job(db, company)
        saved_item = SavedItem(
            student_id=student.id,
            item_type="job",
            job_id=job.id,
        )
        db.add(saved_item)
        db.commit()
        db.refresh(saved_item)

        assert saved_item.job is job
        assert saved_item.event is None
        assert saved_item in student.saved_items


def test_saved_item_event_save(auth_test_context):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        company = create_company(db)
        event = create_event(db, company)
        saved_item = SavedItem(
            student_id=student.id,
            item_type="event",
            event_id=event.id,
        )
        db.add(saved_item)
        db.commit()
        db.refresh(saved_item)

        assert saved_item.event is event
        assert saved_item.job is None
        assert saved_item in student.saved_items


@pytest.mark.parametrize(
    ("item_type", "target_mode"),
    [
        ("job", "neither"),
        ("job", "both"),
        ("job", "event_only"),
        ("event", "job_only"),
        ("other", "job_only"),
    ],
)
def test_saved_item_requires_exactly_one_matching_target(
    auth_test_context,
    item_type,
    target_mode,
):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        company = create_company(db)
        job = create_job(db, company)
        event = create_event(db, company)
        job_id = job.id if target_mode in {"both", "job_only"} else None
        event_id = (
            event.id if target_mode in {"both", "event_only"} else None
        )
        db.add(
            SavedItem(
                student_id=student.id,
                item_type=item_type,
                job_id=job_id,
                event_id=event_id,
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()

    with pytest.raises(ValidationError):
        SavedItemCreate(
            item_type=item_type,
            job_id=job_id,
            event_id=event_id,
        )


def test_duplicate_job_save_is_prevented(auth_test_context):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        company = create_company(db)
        job = create_job(db, company)
        db.add_all([
            SavedItem(
                student_id=student.id,
                item_type="job",
                job_id=job.id,
            ),
            SavedItem(
                student_id=student.id,
                item_type="job",
                job_id=job.id,
            ),
        ])

        with pytest.raises(IntegrityError):
            db.commit()


def test_duplicate_event_save_is_prevented(auth_test_context):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        company = create_company(db)
        event = create_event(db, company)
        db.add_all([
            SavedItem(
                student_id=student.id,
                item_type="event",
                event_id=event.id,
            ),
            SavedItem(
                student_id=student.id,
                item_type="event",
                event_id=event.id,
            ),
        ])

        with pytest.raises(IntegrityError):
            db.commit()


def test_existing_application_uniqueness_is_preserved(auth_test_context):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        company = create_company(db)
        job = create_job(db, company)
        db.add_all([
            Application(student_id=student.id, job_id=job.id),
            Application(student_id=student.id, job_id=job.id),
        ])

        with pytest.raises(IntegrityError):
            db.commit()


def test_existing_registration_uniqueness_is_preserved(auth_test_context):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        company = create_company(db)
        event = create_event(db, company)
        db.add_all([
            Registration(student_id=student.id, event_id=event.id),
            Registration(student_id=student.id, event_id=event.id),
        ])

        with pytest.raises(IntegrityError):
            db.commit()


def test_existing_application_status_values_are_preserved(
    auth_test_context,
):
    _, engine = auth_test_context

    assert [status.value for status in ApplicationStatus] == [
        "Pending",
        "Reviewed",
        "Declined",
    ]

    with Session(engine) as db:
        student = create_student(db)
        company = create_company(db)
        job = create_job(db, company)
        application = Application(student_id=student.id, job_id=job.id)
        db.add(application)
        db.commit()
        db.refresh(application)

        assert application.status == ApplicationStatus.PENDING.value


def test_password_hashes_are_excluded_from_all_read_schemas(
    auth_test_context,
):
    _, engine = auth_test_context

    with Session(engine) as db:
        student = create_student(db)
        company = create_company(db)
        db.commit()
        db.refresh(student)
        db.refresh(company)

        student_summary = StudentResponse.model_validate(student).model_dump()
        student_profile = StudentProfileResponse.model_validate(
            student
        ).model_dump()
        company_profile = CompanyResponse.model_validate(company).model_dump()

    assert "password_hash" not in student_summary
    assert "password_hash" not in student_profile
    assert "password_hash" not in company_profile
    assert "private-" not in str(
        [student_summary, student_profile, company_profile]
    )
