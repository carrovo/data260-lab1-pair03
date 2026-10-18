from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Company, Student
from backend.app.routers.company_auth import (
    get_current_company,
    get_db,
)
from backend.app.schemas.student_auth import StudentProfileResponse

router = APIRouter(
    prefix="/api/companies/students",
    tags=["company students"],
)


@router.get(
    "",
    response_model=List[StudentProfileResponse],
)
def search_students(
    name: str | None = Query(default=None),
    college: str | None = Query(default=None),
    skill: str | None = Query(default=None),
    city: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    statement = select(Student)

    if name:
        statement = statement.where(
            Student.full_name.ilike(f"%{name.strip()}%")
        )

    if college:
        statement = statement.where(
            Student.college_name.ilike(
                f"%{college.strip()}%"
            )
        )

    if skill:
        statement = statement.where(
            Student.skills.ilike(f"%{skill.strip()}%")
        )

    if city:
        statement = statement.where(
            Student.city.ilike(f"%{city.strip()}%")
        )

    statement = (
        statement
        .order_by(Student.full_name.asc())
        .limit(100)
    )

    return list(db.scalars(statement).all())