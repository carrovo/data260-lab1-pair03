from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Company, Student
from backend.app.routers.company_auth import (
    get_current_company,
    get_db,
)
from backend.app.schemas.student_auth import (
    StudentProfileResponse,
)


router = APIRouter(
    prefix="/api/companies/students",
    tags=["company students"],
)


@router.get(
    "",
    response_model=list[StudentProfileResponse],
)
def search_students(
    name: str | None = Query(default=None),
    college: str | None = Query(default=None),
    skill: str | None = Query(default=None),
    city: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_company: Company = Depends(
        get_current_company
    ),
):
    statement = select(Student)

    if name and name.strip():
        statement = statement.where(
            Student.full_name.ilike(
                f"%{name.strip()}%"
            )
        )

    if college and college.strip():
        statement = statement.where(
            Student.college_name.ilike(
                f"%{college.strip()}%"
            )
        )

    if skill and skill.strip():
        statement = statement.where(
            Student.skills.ilike(
                f"%{skill.strip()}%"
            )
        )

    if city and city.strip():
        statement = statement.where(
            Student.city.ilike(
                f"%{city.strip()}%"
            )
        )

    statement = (
        statement
        .order_by(Student.full_name.asc())
        .limit(100)
    )

    return list(db.scalars(statement).all())


@router.get(
    "/{student_id}/profile",
    response_model=StudentProfileResponse,
)
def get_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
    current_company: Company = Depends(
        get_current_company
    ),
):
    student = db.get(Student, student_id)

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found.",
        )

    return student