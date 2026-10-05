from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models import Student
from backend.app.schemas.student_auth import (
    StudentLoginRequest,
    StudentResponse,
    StudentSignupRequest,
    StudentTokenResponse,
)
from backend.app.security import (
    create_access_token,
    hash_password,
    verify_password,
)


router = APIRouter(
    prefix="/auth",
    tags=["student authentication"],
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "/signup",
    response_model=StudentTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    signup_data: StudentSignupRequest,
    db: Session = Depends(get_db),
):
    email = str(signup_data.email).strip().lower()

    existing_student = db.scalar(
        select(Student).where(Student.email == email)
    )

    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    student = Student(
        email=email,
        password_hash=hash_password(signup_data.password),
        full_name=signup_data.full_name.strip(),
        city=signup_data.city.strip(),
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    access_token = create_access_token(student.id, "student")

    return StudentTokenResponse(
        access_token=access_token,
        student=StudentResponse.model_validate(student),
    )


@router.post(
    "/login",
    response_model=StudentTokenResponse,
)
def login(
    login_data: StudentLoginRequest,
    db: Session = Depends(get_db),
):
    email = str(login_data.email).strip().lower()

    student = db.scalar(
        select(Student).where(Student.email == email)
    )

    if not student or not verify_password(
        login_data.password,
        student.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(student.id, "student")

    return StudentTokenResponse(
        access_token=access_token,
        student=StudentResponse.model_validate(student),
    )