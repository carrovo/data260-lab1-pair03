from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.repos import make_repos
from backend.app.routers.company_auth import (
    get_current_company,
    get_db,
)
from backend.app.schemas.company import (
    CompanyResponse,
    CompanyUpdate,
)

router = APIRouter(
    prefix="/api/companies/me",
    tags=["company profile"],
)


@router.get("", response_model=CompanyResponse)
def get_profile(
    current_company: Any = Depends(get_current_company),
):
    return current_company


@router.put("", response_model=CompanyResponse)
def update_profile(
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    current_company: Any = Depends(get_current_company),
):
    update_data = payload.model_dump(exclude_unset=True)

    return make_repos(db).companies.update(current_company, update_data)