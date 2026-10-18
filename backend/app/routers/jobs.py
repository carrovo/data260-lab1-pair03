from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, Company
from app.schemas import JobCreate, JobUpdate, JobOut
from app.auth import require_company

router = APIRouter(prefix="/api/companies/jobs", tags=["company-jobs"])


@router.post("", response_model=JobOut, status_code=201)
def post_job(payload: JobCreate, db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    company_id = int(claims["sub"])
    job = Job(company_id=company_id, **payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=List[JobOut])
def list_owned_jobs(db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    company_id = int(claims["sub"])
    return db.query(Job).filter(Job.company_id == company_id).order_by(Job.posting_date.desc()).all()


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    job = _owned_job_or_404(db, job_id, int(claims["sub"]))
    return job


@router.put("/{job_id}", response_model=JobOut)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_company),
):
    job = _owned_job_or_404(db, job_id, int(claims["sub"]))
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    job = _owned_job_or_404(db, job_id, int(claims["sub"]))
    db.delete(job)
    db.commit()
    return None


def _owned_job_or_404(db: Session, job_id: int, company_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.company_id != company_id:
        raise HTTPException(status_code=403, detail="This job belongs to another company")
    return job
