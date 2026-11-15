from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.repos import make_repos
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
) -> Any:
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

    repos = make_repos(db)

    # Mongo mode: a token signed out through /auth/logout is refused.
    if repos.sessions.is_revoked(credentials.credentials):
        raise unauthorized_error

    student = repos.students.get(student_id)

    if student is None:
        raise unauthorized_error

    return student


def _start_session(repos: Any, student_id: int, token: str, action: str) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    repos.sessions.start(student_id, token, expires_at)
    repos.activity.record(student_id, action)

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

    repos = make_repos(db)
    existing_student = repos.students.get_by_email(email)

    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    student = repos.students.create(
        email=email,
        password_hash=hash_password(signup_data.password),
        full_name=signup_data.full_name.strip(),
        city=signup_data.city.strip(),
    )

    access_token = create_access_token(student.id, "student")
    _start_session(repos, student.id, access_token, "signup")

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

    repos = make_repos(db)
    student = repos.students.get_by_email(email)

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
    _start_session(repos, student.id, access_token, "login")

    return StudentTokenResponse(
        access_token=access_token,
        student=StudentResponse.model_validate(student),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_student: Any = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Sign out: revoke this token's session (Mongo mode; a no-op for SQL)."""
    repos = make_repos(db)
    repos.sessions.revoke(credentials.credentials)
    repos.activity.record(current_student.id, "logout")


@router.get(
    "/me",
    response_model=StudentResponse,
)
def read_current_student(
    current_student: Any = Depends(get_current_student),
):
    return current_student