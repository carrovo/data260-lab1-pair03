from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.repos import make_repos
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
    return make_repos(db).jobs.search(
        keyword=(keyword or "").strip(),
        city=(city or "").strip(),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
):
    job = make_repos(db).jobs.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    return job