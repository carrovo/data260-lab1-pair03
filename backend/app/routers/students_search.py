from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from backend.app.models import Company
from backend.app.repos import make_repos
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
    return make_repos(db).students.search(
        name=name,
        college=college,
        skill=skill,
        city=city,
        limit=100,
    )


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
    student = make_repos(db).students.get(student_id)

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found.",
        )

    return student