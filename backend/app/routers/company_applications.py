from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.application_status import ApplicationStatus
from backend.app.models import (
    Application,
    Company,
    Job,
    Student,
)
from backend.app.routers.applications import get_stored_resume_path
from backend.app.routers.company_auth import (
    get_current_company,
    get_db,
)
from backend.common.events import TRACE_HEADER
from backend.common.outgoing import publish_safely


router = APIRouter(
    prefix="/api/companies",
    tags=["company applications"],
)


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicantResponse(BaseModel):
    application_id: int
    student_id: int
    student_name: str
    student_email: str
    college_name: str | None
    major: str | None
    city: str
    skills: str | None
    status: ApplicationStatus
    applied_at: datetime
    resume_original_name: str | None

    model_config = ConfigDict(from_attributes=True)


def _owned_job_or_404(
    db: Session,
    job_id: int,
    company_id: int,
) -> Job:
    job = db.get(Job, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    if job.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This job belongs to another company.",
        )

    return job


def _application_or_404(
    db: Session,
    application_id: int,
) -> Application:
    application = db.get(Application, application_id)

    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    return application


def _verify_company_owns_application(
    db: Session,
    application: Application,
    company_id: int,
) -> Job:
    return _owned_job_or_404(
        db,
        application.job_id,
        company_id,
    )


def _applicant_response(
    application: Application,
    student: Student,
) -> ApplicantResponse:
    return ApplicantResponse(
        application_id=application.id,
        student_id=student.id,
        student_name=student.full_name,
        student_email=student.email,
        college_name=student.college_name,
        major=student.major,
        city=student.city,
        skills=student.skills,
        status=ApplicationStatus(application.status),
        applied_at=application.applied_at,
        resume_original_name=application.resume_original_name,
    )


@router.get(
    "/jobs/{job_id}/applicants",
    response_model=list[ApplicantResponse],
)
def list_job_applicants(
    job_id: int,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    job = _owned_job_or_404(
        db,
        job_id,
        current_company.id,
    )

    statement = (
        select(Application, Student)
        .join(
            Student,
            Application.student_id == Student.id,
        )
        .where(Application.job_id == job.id)
        .order_by(
            Application.applied_at.desc(),
            Application.id.desc(),
        )
    )

    rows = db.execute(statement).all()

    return [
        _applicant_response(application, student)
        for application, student in rows
    ]


@router.get(
    "/applications/{application_id}/resume",
)
def preview_application_resume(
    application_id: int,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    application = _application_or_404(
        db,
        application_id,
    )

    _verify_company_owns_application(
        db,
        application,
        current_company.id,
    )

    if (
        application.resume_storage_key is None
        or application.resume_original_name is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )

    resume_path = get_stored_resume_path(
        application.resume_storage_key
    )

    if resume_path is None or not resume_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )

    return FileResponse(
        path=resume_path,
        media_type="application/pdf",
        filename=application.resume_original_name,
        content_disposition_type="inline",
    )


@router.put(
    "/applications/{application_id}/status",
    response_model=ApplicantResponse,
)
def update_application_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    application = _application_or_404(
        db,
        application_id,
    )

    _verify_company_owns_application(
        db,
        application,
        current_company.id,
    )

    student = db.get(
        Student,
        application.student_id,
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found.",
        )

    old_status = application.status
    application.status = payload.status.value

    db.commit()
    db.refresh(application)

    if old_status != application.status:
        publish_safely(
            "application.status_changed",
            {
                "application_id": str(application.id),
                "student_id": str(application.student_id),
                "job_id": str(application.job_id),
                "old_status": old_status,
                "new_status": application.status,
            },
            trace_id=request.headers.get(TRACE_HEADER),
            key=str(application.id),
        )

    return _applicant_response(
        application,
        student,
    )