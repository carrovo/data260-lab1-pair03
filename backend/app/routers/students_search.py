from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student
from app.schemas import StudentSummaryOut
from app.auth import require_company

router = APIRouter(prefix="/api/companies/students", tags=["company-students"])


@router.get("", response_model=List[StudentSummaryOut])
def search_students(
    name: Optional[str] = Query(None),
    college: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_company),
):
    query = db.query(Student)
    if name:
        query = query.filter(Student.name.ilike(f"%{name}%"))
    if college:
        query = query.filter(Student.college_name.ilike(f"%{college}%"))
    if skill:
        query = query.filter(Student.skills.ilike(f"%{skill}%"))
    return query.order_by(Student.name.asc()).limit(100).all()
