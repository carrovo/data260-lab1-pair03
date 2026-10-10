from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Application, Job, Student
from backend.app.routers.student_auth import get_current_student, get_db
from backend.app.schemas.application import ApplicationResponse


router = APIRouter(tags=["student applications"])

DUPLICATE_APPLICATION_DETAIL = (
    "You have already applied to this job."
)


def application_with_job_and_company():
    return selectinload(Application.job).selectinload(Job.company)


@router.post(
    "/jobs/{job_id}/applications",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_job(
    job_id: int,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    existing_application_id = db.scalar(
        select(Application.id).where(
            Application.student_id == current_student.id,
            Application.job_id == job_id,
        )
    )

    if existing_application_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_APPLICATION_DETAIL,
        )

    application = Application(
        student_id=current_student.id,
        job_id=job_id,
        status="Pending",
    )
    db.add(application)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_APPLICATION_DETAIL,
        ) from exc

    statement = (
        select(Application)
        .where(Application.id == application.id)
        .options(application_with_job_and_company())
    )

    return db.scalar(statement)


@router.get(
    "/applications/me",
    response_model=list[ApplicationResponse],
)
def list_current_student_applications(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    statement = (
        select(Application)
        .where(Application.student_id == current_student.id)
        .options(application_with_job_and_company())
        .order_by(Application.applied_at.desc(), Application.id.desc())
    )

    return db.scalars(statement).all()
