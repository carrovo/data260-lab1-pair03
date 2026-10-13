import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company
from app.schemas import CompanyProfileOut, CompanyProfileUpdate
from app.auth import require_company
from app.config import PROFILE_PIC_DIR, MAX_PROFILE_PIC_BYTES

router = APIRouter(prefix="/api/companies/me", tags=["company-profile"])

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg"}


def _get_company(db: Session, claims: dict) -> Company:
    company = db.query(Company).filter(Company.id == int(claims["sub"])).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("", response_model=CompanyProfileOut)
def get_profile(db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    return _get_company(db, claims)


@router.put("", response_model=CompanyProfileOut)
def update_profile(
    payload: CompanyProfileUpdate,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_company),
):
    company = _get_company(db, claims)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


@router.post("/picture", response_model=CompanyProfileOut)
def upload_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_company),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG or JPEG images are accepted")

    # Read into memory once so we can enforce a size cap before writing
    # anything to disk — a huge upload gets rejected, not partially saved.
    contents = file.file.read()
    if len(contents) > MAX_PROFILE_PIC_BYTES:
        max_mb = MAX_PROFILE_PIC_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Profile picture must be {max_mb} MB or smaller")

    company = _get_company(db, claims)
    os.makedirs(PROFILE_PIC_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] or ".png"
    filename = f"company_{company.id}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(PROFILE_PIC_DIR, filename)

    with open(path, "wb") as out:
        out.write(contents)

    company.profile_picture = path
    db.commit()
    db.refresh(company)
    return company


@router.get("/picture")
def get_profile_picture(db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    """Serves the logged-in company's own picture — fetched as a blob by the
    frontend (not a plain <img src>, since this is behind auth) and shown
    inline on the profile page."""
    company = _get_company(db, claims)
    if not company.profile_picture or not os.path.exists(company.profile_picture):
        raise HTTPException(status_code=404, detail="No profile picture uploaded yet")
    media_type = "image/jpeg" if company.profile_picture.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return FileResponse(company.profile_picture, media_type=media_type)
