import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from pypdf import PdfWriter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from backend.app.application_status import ApplicationStatus
from backend.app.config import settings
from backend.app.models import Application, Company, Job, Student
from backend.app.routers.applications import (
    MAX_RESUME_SIZE_BYTES,
    apply_to_job,
)


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


def pdf_bytes(*, encrypted=False):
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    if encrypted:
        writer.encrypt("resume-password")
    writer.write(output)
    return output.getvalue()


def resume_file(
    *,
    filename="My Resume.pdf",
    content=None,
    content_type="application/pdf",
):
    return {
        "resume": (
            filename,
            pdf_bytes() if content is None else content,
            content_type,
        )
    }


def test_authenticated_student_can_apply_with_valid_pdf(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)
    uploaded_pdf = pdf_bytes()

    response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(auth_response),
        files=resume_file(content=uploaded_pdf),
    )

    assert response.status_code == 201
    response_data = response.json()
    assert response_data["job_id"] == job_id
    assert response_data["student_id"] == auth_response["student"]["id"]
    assert response_data["status"] == "Pending"
    assert response_data["applied_at"]
    assert response_data["resume_original_name"] == "My Resume.pdf"
    assert response_data["resume_size_bytes"] == len(uploaded_pdf)
    assert "resume_storage_key" not in response_data
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

    with Session(engine) as db:
        application = db.scalar(select(Application))

    assert application is not None
    assert application.resume_storage_key
    assert (settings.resume_upload_dir / application.resume_storage_key).is_file()


def test_application_uses_authenticated_student_and_default_status(
    auth_test_context,
):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)
    student_id = auth_response["student"]["id"]

    response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(auth_response),
        data={"student_id": student_id + 1000, "status": "Declined"},
        files=resume_file(),
    )

    assert response.status_code == 201

    with Session(engine) as db:
        application = db.scalar(select(Application))

    assert application is not None
    assert application.student_id == student_id
    assert application.job_id == job_id
    assert application.status == ApplicationStatus.PENDING.value


def test_application_status_model_default_is_pending(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)

    with Session(engine) as db:
        application = Application(
            student_id=auth_response["student"]["id"],
            job_id=job_id,
            resume_storage_key="test-resume.pdf",
            resume_original_name="Resume.pdf",
            resume_size_bytes=100,
        )
        db.add(application)
        db.commit()
        db.refresh(application)

        assert application.status == ApplicationStatus.PENDING.value


def test_application_endpoints_require_authentication(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)

    apply_response = client.post(
        f"/jobs/{job_id}/applications",
        files=resume_file(),
    )
    history_response = client.get("/applications/me")
    resume_response = client.get("/applications/1/resume")

    assert apply_response.status_code == 401
    assert history_response.status_code == 401
    assert resume_response.status_code == 401


def test_applying_to_missing_job_returns_404(auth_test_context):
    client, _ = auth_test_context
    auth_response = signup_student(client)

    response = client.post(
        "/jobs/999999/applications",
        headers=authorization_headers(auth_response),
        files=resume_file(),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found."}
    assert not settings.resume_upload_dir.exists()


def test_application_requires_resume(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)

    response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(auth_response),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("filename", "content_type", "expected_detail"),
    [
        (
            "resume.txt",
            "application/pdf",
            "Resume filename must use the .pdf extension.",
        ),
        (
            "resume.pdf",
            "text/plain",
            "Resume content type must be application/pdf.",
        ),
    ],
)
def test_resume_rejects_wrong_extension_or_mime_type(
    auth_test_context,
    filename,
    content_type,
    expected_detail,
):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)

    response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(auth_response),
        files=resume_file(filename=filename, content_type=content_type),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": expected_detail}


def test_resume_rejects_invalid_pdf_content(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)

    response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(auth_response),
        files=resume_file(content=b"%PDF-not-a-parseable-document"),
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Resume must be a valid, readable PDF."
    }
    assert list(settings.resume_upload_dir.glob("*")) == []


def test_resume_rejects_encrypted_pdf(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)

    response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(auth_response),
        files=resume_file(content=pdf_bytes(encrypted=True)),
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Encrypted PDF resumes are not supported."
    }
    assert list(settings.resume_upload_dir.glob("*")) == []


def test_resume_rejects_oversized_file(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)
    oversized_content = b"%PDF-" + b"x" * MAX_RESUME_SIZE_BYTES

    response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(auth_response),
        files=resume_file(content=oversized_content),
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "Resume must be 5 MiB or smaller."
    }
    assert list(settings.resume_upload_dir.glob("*")) == []


def test_duplicate_application_returns_409_without_orphaned_file(
    auth_test_context,
):
    client, engine = auth_test_context
    job_id = create_job(engine)
    auth_response = signup_student(client)
    headers = authorization_headers(auth_response)

    first_response = client.post(
        f"/jobs/{job_id}/applications",
        headers=headers,
        files=resume_file(filename="first.pdf"),
    )
    files_after_first_application = list(
        settings.resume_upload_dir.glob("*.pdf")
    )
    duplicate_response = client.post(
        f"/jobs/{job_id}/applications",
        headers=headers,
        files=resume_file(filename="duplicate.pdf"),
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "You have already applied to this job."
    }
    assert list(settings.resume_upload_dir.glob("*.pdf")) == (
        files_after_first_application
    )

    with Session(engine) as db:
        application_count = db.scalar(
            select(func.count()).select_from(Application)
        )

    assert application_count == 1


def test_application_history_contains_job_company_date_status_and_resume(
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

    client.post(
        f"/jobs/{first_job_id}/applications",
        headers=headers,
        files=resume_file(filename="first.pdf"),
    )
    client.post(
        f"/jobs/{second_job_id}/applications",
        headers=headers,
        files=resume_file(filename="second.pdf"),
    )
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
    assert {application["resume_original_name"] for application in history} == {
        "first.pdf",
        "second.pdf",
    }


def test_application_history_filters_by_validated_status(auth_test_context):
    client, engine = auth_test_context
    first_job_id = create_job(engine)
    second_job_id = create_job(
        engine,
        company_email="reviewed-company@example.com",
        title="Reviewed Job",
    )
    auth_response = signup_student(client)
    headers = authorization_headers(auth_response)

    client.post(
        f"/jobs/{first_job_id}/applications",
        headers=headers,
        files=resume_file(filename="pending.pdf"),
    )
    reviewed_response = client.post(
        f"/jobs/{second_job_id}/applications",
        headers=headers,
        files=resume_file(filename="reviewed.pdf"),
    )
    with Session(engine) as db:
        reviewed_application = db.get(
            Application,
            reviewed_response.json()["id"],
        )
        reviewed_application.status = ApplicationStatus.REVIEWED.value
        db.commit()

    filtered_response = client.get(
        "/applications/me?status=Reviewed",
        headers=headers,
    )
    invalid_response = client.get(
        "/applications/me?status=submitted",
        headers=headers,
    )

    assert filtered_response.status_code == 200
    assert [item["job_id"] for item in filtered_response.json()] == [
        second_job_id
    ]
    assert invalid_response.status_code == 422


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
        files=resume_file(filename="first.pdf"),
    )
    client.post(
        f"/jobs/{second_job_id}/applications",
        headers=second_headers,
        files=resume_file(filename="second.pdf"),
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


def test_student_can_view_only_their_own_resume(auth_test_context):
    client, engine = auth_test_context
    job_id = create_job(engine)
    owner = signup_student(client)
    other_student = signup_student(
        client,
        email="other@example.com",
        full_name="Other Student",
    )
    uploaded_pdf = pdf_bytes()
    apply_response = client.post(
        f"/jobs/{job_id}/applications",
        headers=authorization_headers(owner),
        files=resume_file(
            filename="../../My\nResume.pdf",
            content=uploaded_pdf,
        ),
    )
    application_id = apply_response.json()["id"]

    owner_response = client.get(
        f"/applications/{application_id}/resume",
        headers=authorization_headers(owner),
    )
    other_response = client.get(
        f"/applications/{application_id}/resume",
        headers=authorization_headers(other_student),
    )

    assert owner_response.status_code == 200
    assert owner_response.content == uploaded_pdf
    assert owner_response.headers["content-type"] == "application/pdf"
    assert owner_response.headers["content-disposition"].startswith("inline;")
    assert ".." not in owner_response.headers["content-disposition"]
    assert other_response.status_code == 404
    assert other_response.json() == {"detail": "Application not found."}


def test_integrity_error_rolls_back_and_removes_saved_resume(
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
        upload = UploadFile(
            file=BytesIO(pdf_bytes()),
            filename="resume.pdf",
            headers=Headers({"content-type": "application/pdf"}),
        )

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                apply_to_job(
                    job_id=job_id,
                    resume=upload,
                    current_student=student,
                    db=db,
                )
            )

    assert rollback_called
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "You have already applied to this job."
    assert list(settings.resume_upload_dir.glob("*")) == []
