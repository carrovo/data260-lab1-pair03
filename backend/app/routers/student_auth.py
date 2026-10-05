from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
    decode_access_token,
    hash_password,
    verify_password,
)


router = APIRouter(
    prefix="/auth",
    tags=["student authentication"],
)
bearer_scheme = HTTPBearer(auto_error=False)

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()

def get_current_student(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Student:
    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized_error

    try:
        student_id, role = decode_access_token(
            credentials.credentials
        )
    except ValueError:
        raise unauthorized_error

    if role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access is required.",
        )

    student = db.get(Student, student_id)

    if student is None:
        raise unauthorized_error

    return student

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

@router.get(
    "/me",
    response_model=StudentResponse,
)
def read_current_student(
    current_student: Student = Depends(get_current_student),
):
    return current_student