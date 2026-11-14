from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import Application
from backend.app.repos import make_repos
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
) -> Any:
    job = make_repos(db).jobs.get_for_company(job_id, company_id)

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
    db: Session = Depends(get_db),
    current_company: Any = Depends(get_current_company),
):
    job_data = payload.model_dump()

    # Store the enum value as a normal string in the canonical DB column.
    job_data["category"] = payload.category.value

    job = make_repos(db).jobs.create(current_company.id, job_data)

    publish_safely(
        "job.created",
        {
            "job_id": str(job.id),
            "company_id": str(current_company.id),
            "title": job.title,
        },
        key=str(job.id),
    )

    return job


@router.get(
    "",
    response_model=list[JobCanonicalResponse],
)
def list_company_jobs(
    db: Session = Depends(get_db),
    current_company: Any = Depends(get_current_company),
):
    return make_repos(db).jobs.list_for_company(current_company.id)


@router.get(
    "/{job_id}",
    response_model=JobCanonicalResponse,
)
def get_company_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_company: Any = Depends(get_current_company),
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
    current_company: Any = Depends(get_current_company),
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

    return make_repos(db).jobs.update(job, update_data)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_company_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_company: Any = Depends(get_current_company),
):
    job = _owned_job_or_404(
        db,
        job_id,
        current_company.id,
    )

    # Avoid deleting a job that already has student applications.
    application_count = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.job_id == job.id)
    )

    if application_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a job that already has applications.",
        )

    try:
        make_repos(db).jobs.delete(job)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job cannot be deleted because related records exist.",
        ) from exc

    return None