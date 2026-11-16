from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.repos import make_repos
from backend.app.schemas.company import CompanyCreate, CompanyResponse
from backend.app.schemas.student_auth import StudentLoginRequest
from backend.app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(
    prefix="/api/companies/auth",
    tags=["company authentication"],
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_company(
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
        company_id, role = decode_access_token(credentials.credentials)
    except ValueError:
        raise unauthorized_error

    if role != "company":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Company access is required.",
        )

    company = make_repos(db).companies.get(company_id)

    if company is None:
        raise unauthorized_error

    return company


@router.post(
    "/signup",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    companies = make_repos(db).companies

    if companies.get_by_email(email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    company = companies.create(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        city=payload.city.strip(),
        description=payload.description,
        contact_info=payload.contact_info,
    )

    access_token = create_access_token(company.id, "company")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "company": CompanyResponse.model_validate(company),
    }


@router.post("/login", response_model=dict)
def login(
    payload: StudentLoginRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()

    company = make_repos(db).companies.get_by_email(email)

    if not company or not verify_password(
        payload.password,
        company.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(company.id, "company")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "company": CompanyResponse.model_validate(company),
    }


@router.get("/me", response_model=CompanyResponse)
def read_current_company(
    current_company: Any = Depends(get_current_company),
):
    return current_company


@router.post("/logout")
def logout():
    return {
        "detail": "Logged out. Discard the token client-side."
    }