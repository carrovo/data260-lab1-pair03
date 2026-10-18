import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, Application, Student
from app.schemas import ApplicantOut, ApplicationStatusUpdate, StudentSummaryOut
from app.auth import require_company

router = APIRouter(prefix="/api/companies", tags=["company-applications"])


def _owned_job_or_404(db: Session, job_id: int, company_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.company_id != company_id:
        raise HTTPException(status_code=403, detail="This job belongs to another company")
    return job


@router.get("/jobs/{job_id}/applicants", response_model=List[ApplicantOut])
def list_applicants(job_id: int, db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    job = _owned_job_or_404(db, job_id, int(claims["sub"]))
    rows = (
        db.query(Application, Student)
        .join(Student, Application.student_id == Student.id)
        .filter(Application.job_id == job.id)
        .order_by(Application.applied_at.desc())
        .all()
    )
    return [
        ApplicantOut(
            application_id=app.id,
            student_id=student.id,
            student_name=student.name,
            student_email=student.email,
            college_name=student.college_name,
            status=app.status,
            applied_at=app.applied_at,
            resume_path=app.resume_path,
        )
        for app, student in rows
    ]


@router.get("/students/{student_id}/profile", response_model=StudentSummaryOut)
def view_applicant_profile(
    student_id: int, db: Session = Depends(get_db), claims: dict = Depends(require_company)
):
    """Open a student's profile from an applicant list. Any authenticated
    company may view a student's public summary (mirrors the student
    directory search below)."""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.get("/applications/{application_id}/resume")
def preview_resume(
    application_id: int, db: Session = Depends(get_db), claims: dict = Depends(require_company)
):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.query(Job).filter(Job.id == application.job_id).first()
    if not job or job.company_id != int(claims["sub"]):
        raise HTTPException(status_code=403, detail="You do not own the job for this application")

    if not application.resume_path or not os.path.exists(application.resume_path):
        raise HTTPException(status_code=404, detail="Resume file not found on server")

    return FileResponse(application.resume_path, media_type="application/pdf")


@router.put("/applications/{application_id}/status", response_model=ApplicantOut)
def update_application_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_company),
):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    job = db.query(Job).filter(Job.id == application.job_id).first()
    if not job or job.company_id != int(claims["sub"]):
        raise HTTPException(status_code=403, detail="You do not own the job for this application")

    application.status = payload.status
    db.commit()
    db.refresh(application)

    student = db.query(Student).filter(Student.id == application.student_id).first()
    return ApplicantOut(
        application_id=application.id,
        student_id=student.id,
        student_name=student.name,
        student_email=student.email,
        college_name=student.college_name,
        status=application.status,
        applied_at=application.applied_at,
        resume_path=application.resume_path,
    )
