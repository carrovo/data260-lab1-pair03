from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.database import SessionLocal
from backend.app.models import Company, Job
from backend.app.schemas.job import JobResponse


router = APIRouter(tags=["jobs"])


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get(
    "/jobs",
    response_model=list[JobResponse],
)
def list_jobs(
    keyword: str | None = Query(
        default=None,
        max_length=100,
    ),
    city: str | None = Query(
        default=None,
        max_length=100,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
):
    statement = (
        select(Job)
        .join(Job.company)
        .options(selectinload(Job.company))
    )

    if keyword and keyword.strip():
        search_pattern = f"%{keyword.strip()}%"

        statement = statement.where(
            or_(
                Job.title.ilike(search_pattern),
                Job.description.ilike(search_pattern),
                Company.name.ilike(search_pattern),
            )
        )

    if city and city.strip():
        city_pattern = f"%{city.strip()}%"

        statement = statement.where(
            Job.city.ilike(city_pattern)
        )

    statement = (
        statement
        .order_by(Job.created_at.desc(), Job.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return db.scalars(statement).all()


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
):
    statement = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.company))
    )

    job = db.scalar(statement)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    return job