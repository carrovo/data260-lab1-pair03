from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.application_status import ApplicationStatus
from backend.app.config import settings
from backend.app.database import Base
from backend.app.models import (
    Application,
    Company,
    Event,
    Job,
    Registration,
    Student,
)
from backend.app.routers import company_auth
from backend.app.routers.company_applications import (
    router as company_applications_router,
)
from backend.app.routers.company_auth import (
    router as company_auth_router,
)
from backend.app.routers.company_events import (
    router as company_events_router,
)
from backend.app.routers.company_jobs import (
    router as company_jobs_router,
)
from backend.app.routers.company_profile import (
    router as company_profile_router,
)
from backend.app.routers.students_search import (
    router as students_search_router,
)
from backend.app.security import (
    create_access_token,
    hash_password,
)


COMPANY_DATA = {
    "email": "recruiter@example.com",
    "password": "Password123",
    "name": "Example Analytics",
    "city": "San Jose",
    "description": "Analytics company",
    "contact_info": "recruiting@example.com",
}


@pytest.fixture
def company_test_context(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "resume_upload_dir",
        tmp_path / "resumes",
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    test_app = FastAPI()

    test_app.include_router(company_auth_router)
    test_app.include_router(company_profile_router)
    test_app.include_router(company_jobs_router)
    test_app.include_router(company_applications_router)
    test_app.include_router(company_events_router)
    test_app.include_router(students_search_router)

    def override_get_db():
        with Session(engine) as db:
            yield db

    test_app.dependency_overrides[
        company_auth.get_db
    ] = override_get_db

    with TestClient(test_app) as client:
        yield client, engine

    test_app.dependency_overrides.clear()
    engine.dispose()


def signup_company(client, **overrides):
    data = {
        **COMPANY_DATA,
        **overrides,
    }

    return client.post(
        "/api/companies/auth/signup",
        json=data,
    )


def company_headers(client):
    response = signup_company(client)

    assert response.status_code == 201

    token = response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }


def test_company_signup_and_login(company_test_context):
    client, engine = company_test_context

    signup_response = signup_company(
        client,
        email="Recruiter@Example.com",
    )

    assert signup_response.status_code == 201

    signup_data = signup_response.json()

    assert signup_data["access_token"]
    assert signup_data["token_type"] == "bearer"
    assert signup_data["company"]["email"] == (
        "recruiter@example.com"
    )
    assert signup_data["company"]["city"] == "San Jose"
    assert "password_hash" not in signup_data["company"]

    login_response = client.post(
        "/api/companies/auth/login",
        json={
            "email": "recruiter@example.com",
            "password": "Password123",
        },
    )

    assert login_response.status_code == 200
    assert login_response.json()["access_token"]

    with Session(engine) as db:
        company = db.scalar(
            select(Company).where(
                Company.email == "recruiter@example.com"
            )
        )

    assert company is not None
    assert company.password_hash != "Password123"


def test_company_duplicate_signup_is_rejected(
    company_test_context,
):
    client, _ = company_test_context

    first = signup_company(client)
    duplicate = signup_company(
        client,
        email="RECRUITER@example.com",
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_company_profile_can_be_read_and_updated(
    company_test_context,
):
    client, _ = company_test_context
    headers = company_headers(client)

    profile = client.get(
        "/api/companies/me",
        headers=headers,
    )

    assert profile.status_code == 200
    assert profile.json()["name"] == "Example Analytics"

    update = client.put(
        "/api/companies/me",
        headers=headers,
        json={
            "name": "Updated Analytics",
            "city": "Santa Clara",
            "description": "Updated description",
            "contact_info": "jobs@example.com",
        },
    )

    assert update.status_code == 200
    assert update.json()["name"] == "Updated Analytics"
    assert update.json()["city"] == "Santa Clara"


def test_company_job_crud(company_test_context):
    client, _ = company_test_context
    headers = company_headers(client)

    deadline = (
        datetime.now(timezone.utc)
        + timedelta(days=30)
    ).isoformat()

    create_response = client.post(
        "/api/companies/jobs",
        headers=headers,
        json={
            "title": "Data Analyst Intern",
            "description": "Analyze business data.",
            "city": "San Jose",
            "category": "internship",
            "location": "Downtown",
            "is_remote": False,
            "salary": "32.50",
            "skills": "Python, SQL",
            "deadline": deadline,
        },
    )

    assert create_response.status_code == 201

    job = create_response.json()
    job_id = job["id"]

    assert job["title"] == "Data Analyst Intern"
    assert job["category"] == "internship"

    list_response = client.get(
        "/api/companies/jobs",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(
        f"/api/companies/jobs/{job_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200

    update_response = client.put(
        f"/api/companies/jobs/{job_id}",
        headers=headers,
        json={
            "title": "Senior Data Analyst Intern",
            "is_remote": True,
        },
    )

    assert update_response.status_code == 200
    assert (
        update_response.json()["title"]
        == "Senior Data Analyst Intern"
    )
    assert update_response.json()["is_remote"] is True

    delete_response = client.delete(
        f"/api/companies/jobs/{job_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204


def test_company_cannot_access_another_company_job(
    company_test_context,
):
    client, engine = company_test_context
    headers = company_headers(client)

    with Session(engine) as db:
        other_company = Company(
            email="other@example.com",
            password_hash=hash_password("Password123"),
            name="Other Company",
            city="Fremont",
        )

        db.add(other_company)
        db.flush()

        other_job = Job(
            company_id=other_company.id,
            title="Private Job",
            description="Another company's job.",
            city="Fremont",
            category="internship",
            is_remote=False,
        )

        db.add(other_job)
        db.commit()
        job_id = other_job.id

    response = client.get(
        f"/api/companies/jobs/{job_id}",
        headers=headers,
    )

    assert response.status_code == 404


def test_company_can_list_applicants_and_update_status(
    company_test_context,
):
    client, engine = company_test_context
    headers = company_headers(client)

    with Session(engine) as db:
        company = db.scalar(select(Company))

        student = Student(
            email="student@example.com",
            password_hash=hash_password("Password123"),
            full_name="Test Student",
            city="San Jose",
            college_name="SJSU",
            major="Data Science",
            skills="Python, SQL",
        )

        db.add(student)
        db.flush()

        job = Job(
            company_id=company.id,
            title="ML Intern",
            description="Machine learning internship.",
            city="San Jose",
            category="internship",
            is_remote=False,
        )

        db.add(job)
        db.flush()

        application = Application(
            student_id=student.id,
            job_id=job.id,
            status=ApplicationStatus.PENDING.value,
        )

        db.add(application)
        db.commit()

        job_id = job.id
        application_id = application.id

    applicants = client.get(
        f"/api/companies/jobs/{job_id}/applicants",
        headers=headers,
    )

    assert applicants.status_code == 200
    assert len(applicants.json()) == 1
    assert (
        applicants.json()[0]["student_name"]
        == "Test Student"
    )

    update = client.put(
        (
            "/api/companies/applications/"
            f"{application_id}/status"
        ),
        headers=headers,
        json={
            "status": ApplicationStatus.REVIEWED.value,
        },
    )

    assert update.status_code == 200
    assert (
        update.json()["status"]
        == ApplicationStatus.REVIEWED.value
    )


def test_company_event_crud(company_test_context):
    client, _ = company_test_context
    headers = company_headers(client)

    starts_at = (
        datetime.now(timezone.utc)
        + timedelta(days=10)
    )

    ends_at = starts_at + timedelta(hours=2)

    create = client.post(
        "/api/companies/events",
        headers=headers,
        json={
            "title": "Data Career Night",
            "description": "Meet analytics recruiters.",
            "city": "San Jose",
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "location": "SJSU",
            "major": "Data Science",
            "eligibility": "Open to students",
        },
    )

    assert create.status_code == 201

    event_id = create.json()["id"]

    listing = client.get(
        "/api/companies/events",
        headers=headers,
    )

    assert listing.status_code == 200
    assert len(listing.json()) == 1

    detail = client.get(
        f"/api/companies/events/{event_id}",
        headers=headers,
    )

    assert detail.status_code == 200

    update = client.put(
        f"/api/companies/events/{event_id}",
        headers=headers,
        json={
            "title": "Updated Data Career Night",
        },
    )

    assert update.status_code == 200
    assert (
        update.json()["title"]
        == "Updated Data Career Night"
    )

    delete = client.delete(
        f"/api/companies/events/{event_id}",
        headers=headers,
    )

    assert delete.status_code == 204


def test_company_can_view_event_registrants(
    company_test_context,
):
    client, engine = company_test_context
    headers = company_headers(client)

    with Session(engine) as db:
        company = db.scalar(select(Company))

        student = Student(
            email="registered@example.com",
            password_hash=hash_password("Password123"),
            full_name="Registered Student",
            city="San Jose",
            college_name="SJSU",
            major="Computer Science",
            skills="Python",
        )

        db.add(student)
        db.flush()

        event = Event(
            company_id=company.id,
            title="Career Fair",
            description="Recruiting event",
            city="San Jose",
            starts_at=datetime.now(timezone.utc)
            + timedelta(days=5),
            ends_at=datetime.now(timezone.utc)
            + timedelta(days=5, hours=2),
        )

        db.add(event)
        db.flush()

        registration = Registration(
            student_id=student.id,
            event_id=event.id,
        )

        db.add(registration)
        db.commit()

        event_id = event.id

    response = client.get(
        f"/api/companies/events/{event_id}/registrants",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert (
        response.json()[0]["full_name"]
        == "Registered Student"
    )


def test_company_can_search_and_view_student_profile(
    company_test_context,
):
    client, engine = company_test_context
    headers = company_headers(client)

    with Session(engine) as db:
        student = Student(
            email="analyst@example.com",
            password_hash=hash_password("Password123"),
            full_name="Analytics Student",
            city="San Jose",
            college_name="SJSU",
            major="Data Analytics",
            skills="Python, Tableau",
        )

        db.add(student)
        db.commit()
        student_id = student.id

    search_response = client.get(
        "/api/companies/students",
        headers=headers,
        params={
            "name": "Analytics",
            "skill": "Python",
        },
    )

    assert search_response.status_code == 200
    assert len(search_response.json()) == 1
    assert (
        search_response.json()[0]["full_name"]
        == "Analytics Student"
    )

    profile_response = client.get(
        (
            "/api/companies/students/"
            f"{student_id}/profile"
        ),
        headers=headers,
    )

    assert profile_response.status_code == 200
    assert (
        profile_response.json()["full_name"]
        == "Analytics Student"
    )


def test_company_routes_require_company_auth(
    company_test_context,
):
    client, _ = company_test_context

    missing_token = client.get(
        "/api/companies/jobs"
    )

    assert missing_token.status_code == 401

    student_token = create_access_token(
        999,
        "student",
    )

    student_role_response = client.get(
        "/api/companies/jobs",
        headers={
            "Authorization": (
                f"Bearer {student_token}"
            )
        },
    )

    assert student_role_response.status_code == 403