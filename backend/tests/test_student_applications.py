import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import Application, Company, Job, Student
from backend.app.routers.applications import apply_to_job


def signup_student(
    client,
    email="student@example.com",
    full_name="Test Student",
):
    response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "Password123",
            "full_name": full_name,
            "city": "San Jose",
        },
    )
    assert response.status_code == 201
    return response.json()


def authorization_headers(auth_response):
    return {
        "Authorization": f"Bearer {auth_response['access_token']}"
    }


def create_job(
    engine,
    company_email="company@example.com",
    company_name="Example Company",
    title="Data Analyst Intern",
    city="San Jose",
):
    with Session(engine) as db:
        company = Company(
            email=company_email,
            password_hash="not-used-in-application-tests",
            name=company_name,
            city=city,
        )
        db.add(company)
        db.flush()

        job = Job(
            company_id=company.id,
            title=title,
            description="Analyze data and create reports.",
            city=city,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id


def test_authenticated_student_can_apply_to_existing_job(
    auth_test_context,
):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)

    response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(auth_response),
    )

    assert response.status_code == 201
    response_data = response.json()
    assert response_data["job_id"] == job_id
    assert response_data["student_id"] == auth_response["student"]["id"]
    assert response_data["status"] == "Pending"
    assert response_data["applied_at"]
    assert response_data["job"] == {
        "id": job_id,
        "title": "Data Analyst Intern",
        "city": "San Jose",
        "company": {
            "id": response_data["job"]["company"]["id"],
            "name": "Example Company",
            "city": "San Jose",
        },
    }
    assert "student" not in response_data
    assert "password_hash" not in str(response_data)


def test_application_is_linked_to_authenticated_student(
    auth_test_context,
):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)
    student_id = auth_response["student"]["id"]

    response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(auth_response),
        json={"student_id": student_id + 1000},
    )

    assert response.status_code == 201

    with Session(engine) as db:
        application = db.scalar(select(Application))

    assert application is not None
    assert application.student_id == student_id
    assert application.job_id == job_id


def test_application_endpoints_require_authentication(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)

    apply_response = client.post(f"/jobs/{job_id}/applications")
    history_response = client.get("/applications/me")

    assert apply_response.status_code == 401
    assert history_response.status_code == 401


def test_applying_to_missing_job_returns_404(auth_test_context):
    client, _ = auth_test_context
    auth_response = signup_student(client)

    response = client.post(
        "/jobs/999999/applications",
        headers=authorization_headers(auth_response),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found."}


def test_duplicate_application_returns_409(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)
    headers = authorization_headers(auth_response)

    first_response = client.post(
        f"/jobs/{job_id}/applications",
        headers=headers,
    )
    duplicate_response = client.post(
        f"/jobs/{job_id}/applications",
        headers=headers,
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "You have already applied to this job."
    }

    with Session(engine) as db:
        application_count = db.scalar(
            select(func.count()).select_from(Application)
        )

    assert application_count == 1


def test_application_history_contains_job_company_date_and_status(
    auth_test_context,
):
    client, engine = auth_test_context
    first_job_id = create_job(engine)
    second_job_id = create_job(
        engine,
        company_email="second-company@example.com",
        company_name="Second Company",
        title="Software Engineering Intern",
        city="Fremont",
    )
    auth_response = signup_student(client)
    headers = authorization_headers(auth_response)

    client.post(f"/jobs/{first_job_id}/applications", headers=headers)
    client.post(f"/jobs/{second_job_id}/applications", headers=headers)
    history_response = client.get("/applications/me", headers=headers)

    assert history_response.status_code == 200
    history = history_response.json()
    assert {application["job_id"] for application in history} == {
        first_job_id,
        second_job_id,
    }
    assert all(application["applied_at"] for application in history)
    assert all(application["status"] == "Pending" for application in history)
    assert all(application["job"]["company"]["name"] for application in history)


def test_student_cannot_see_another_students_application(
    auth_test_context,
):
    client, engine = auth_test_context
    first_job_id = create_job(engine)
    second_job_id = create_job(
        engine,
        company_email="private-company@example.com",
        company_name="Private Company",
        title="Private Job",
    )
    first_student = signup_student(client)
    second_student = signup_student(
        client,
        email="other-student@example.com",
        full_name="Other Student",
    )
    first_headers = authorization_headers(first_student)
    second_headers = authorization_headers(second_student)

    client.post(
        f"/jobs/{first_job_id}/applications",
        headers=first_headers,
    )
    client.post(
        f"/jobs/{second_job_id}/applications",
        headers=second_headers,
    )

    first_history = client.get(
        "/applications/me",
        headers=first_headers,
    ).json()
    second_history = client.get(
        "/applications/me",
        headers=second_headers,
    ).json()

    assert [application["job_id"] for application in first_history] == [
        first_job_id
    ]
    assert [application["job_id"] for application in second_history] == [
        second_job_id
    ]


def test_integrity_error_rolls_back_and_returns_duplicate_conflict(
    auth_test_context,
    monkeypatch,
):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)
    student_id = auth_response["student"]["id"]

    with Session(engine) as db:
        student = db.get(Student, student_id)
        original_rollback = db.rollback
        rollback_called = False

        def fail_commit():
            raise IntegrityError(
                "INSERT INTO applications",
                {},
                Exception("duplicate application"),
            )

        def track_rollback():
            nonlocal rollback_called
            rollback_called = True
            original_rollback()

        monkeypatch.setattr(db, "commit", fail_commit)
        monkeypatch.setattr(db, "rollback", track_rollback)

        with pytest.raises(HTTPException) as exc_info:
            apply_to_job(
                job_id=job_id,
                current_student=student,
                db=db,
            )

    assert rollback_called
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "You have already applied to this job."
