from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Company, Job
from backend.common.events import TRACE_HEADER
from backend.common.outgoing import publish_safely
from backend.app.routers.company_auth import (
    get_current_company,
    get_db,
)
from backend.app.schemas.job import (
    JobCanonicalResponse,
    JobCreate,
    JobUpdate,
)


router = APIRouter(
    prefix="/api/companies/jobs",
    tags=["company jobs"],
)


def _owned_job_or_404(
    db: Session,
    job_id: int,
    company_id: int,
) -> Job:
    statement = (
        select(Job)
        .where(
            Job.id == job_id,
            Job.company_id == company_id,
        )
        .options(selectinload(Job.company))
    )

    job = db.scalar(statement)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    return job


@router.post(
    "",
    response_model=JobCanonicalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(
    payload: JobCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    job_data = payload.model_dump()

    # Store the enum value as a normal string in the canonical DB column.
    job_data["category"] = payload.category.value

    job = Job(
        company_id=current_company.id,
        **job_data,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    publish_safely(
        "job.created",
        {
            "job_id": str(job.id),
            "company_id": str(current_company.id),
            "title": job.title,
        },
        trace_id=request.headers.get(TRACE_HEADER),
        key=str(job.id),
    )

    return _owned_job_or_404(
        db,
        job.id,
        current_company.id,
    )


@router.get(
    "",
    response_model=list[JobCanonicalResponse],
)
def list_company_jobs(
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    statement = (
        select(Job)
        .where(Job.company_id == current_company.id)
        .options(selectinload(Job.company))
        .order_by(Job.created_at.desc(), Job.id.desc())
    )

    return list(db.scalars(statement).all())


@router.get(
    "/{job_id}",
    response_model=JobCanonicalResponse,
)
def get_company_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    return _owned_job_or_404(
        db,
        job_id,
        current_company.id,
    )


@router.put(
    "/{job_id}",
    response_model=JobCanonicalResponse,
)
def update_company_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    job = _owned_job_or_404(
        db,
        job_id,
        current_company.id,
    )

    update_data = payload.model_dump(exclude_unset=True)

    if (
        "category" in update_data
        and update_data["category"] is not None
    ):
        update_data["category"] = update_data["category"].value

    for field, value in update_data.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)

    return _owned_job_or_404(
        db,
        job.id,
        current_company.id,
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_company_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    job = _owned_job_or_404(
        db,
        job_id,
        current_company.id,
    )

    # Avoid deleting a job that already has student applications.
    if job.applications:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a job that already has applications.",
        )

    try:
        db.delete(job)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job cannot be deleted because related records exist.",
        ) from exc

    return None