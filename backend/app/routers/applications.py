import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from backend.app.application_status import ApplicationStatus
from backend.app.config import settings
from backend.app.models import Application, Job, Student
from backend.app.routers.student_auth import get_current_student, get_db
from backend.app.schemas.application import ApplicationResponse


router = APIRouter(tags=["student applications"])

DUPLICATE_APPLICATION_DETAIL = (
    "You have already applied to this job."
)
MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024
UPLOAD_CHUNK_SIZE_BYTES = 64 * 1024


@dataclass(frozen=True)
class StoredResume:
    storage_key: str
    original_name: str
    size_bytes: int
    path: Path


def application_with_job_and_company():
    return selectinload(Application.job).selectinload(Job.company)


def sanitize_pdf_filename(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    cleaned = re.sub(r"[^\w .()\-]", "_", basename)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    stem = cleaned[:-4].rstrip(" .") if cleaned.lower().endswith(".pdf") else cleaned
    return f"{stem[:240] or 'resume'}.pdf"


def remove_file(path: Path | None) -> None:
    if path is None:
        return

    try:
        path.unlink()
    except FileNotFoundError:
        pass


def validate_pdf_parseability(path: Path) -> None:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Encrypted PDF resumes are not supported.",
            )
        if len(reader.pages) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Resume must be a readable PDF with at least one page.",
            )
    except HTTPException:
        raise
    except (PdfReadError, OSError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Resume must be a valid, readable PDF.",
        ) from exc


async def store_validated_resume(resume: UploadFile) -> StoredResume:
    filename = resume.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Resume filename must use the .pdf extension.",
        )

    if (resume.content_type or "").lower() != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Resume content type must be application/pdf.",
        )

    upload_dir = settings.resume_upload_dir.resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    final_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=upload_dir,
            prefix=".resume-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            size_bytes = 0
            signature = b""

            while chunk := await resume.read(UPLOAD_CHUNK_SIZE_BYTES):
                size_bytes += len(chunk)
                if size_bytes > MAX_RESUME_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Resume must be 5 MiB or smaller.",
                    )

                if len(signature) < 5:
                    signature += chunk[: 5 - len(signature)]
                temporary_file.write(chunk)

            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        if signature != b"%PDF-":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Resume content is not a PDF.",
            )

        validate_pdf_parseability(temporary_path)

        storage_key = f"{uuid4().hex}.pdf"
        final_path = upload_dir / storage_key
        os.replace(temporary_path, final_path)
        temporary_path = None

        return StoredResume(
            storage_key=storage_key,
            original_name=sanitize_pdf_filename(filename),
            size_bytes=size_bytes,
            path=final_path,
        )
    except Exception:
        remove_file(temporary_path)
        remove_file(final_path)
        raise


def get_stored_resume_path(storage_key: str) -> Path | None:
    upload_dir = settings.resume_upload_dir.resolve()
    resume_path = (upload_dir / storage_key).resolve()

    try:
        resume_path.relative_to(upload_dir)
    except ValueError:
        return None

    return resume_path


@router.post(
    "/jobs/{job_id}/applications",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_job(
    job_id: int,
    resume: UploadFile = File(...),
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    existing_application_id = db.scalar(
        select(Application.id).where(
            Application.student_id == current_student.id,
            Application.job_id == job_id,
        )
    )

    if existing_application_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_APPLICATION_DETAIL,
        )

    stored_resume = await store_validated_resume(resume)
    application = Application(
        student_id=current_student.id,
        job_id=job_id,
        resume_storage_key=stored_resume.storage_key,
        resume_original_name=stored_resume.original_name,
        resume_size_bytes=stored_resume.size_bytes,
    )

    try:
        db.add(application)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        remove_file(stored_resume.path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_APPLICATION_DETAIL,
        ) from exc
    except SQLAlchemyError:
        db.rollback()
        remove_file(stored_resume.path)
        raise

    statement = (
        select(Application)
        .where(Application.id == application.id)
        .options(application_with_job_and_company())
    )

    return db.scalar(statement)


@router.get(
    "/applications/me",
    response_model=list[ApplicationResponse],
)
def list_current_student_applications(
    status_filter: ApplicationStatus | None = Query(
        default=None,
        alias="status",
    ),
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    statement = select(Application).where(
        Application.student_id == current_student.id
    )
    if status_filter is not None:
        statement = statement.where(
            Application.status == status_filter.value
        )

    statement = statement.options(
        application_with_job_and_company()
    ).order_by(Application.applied_at.desc(), Application.id.desc())

    return db.scalars(statement).all()


@router.get("/applications/{application_id}/resume")
def get_current_student_resume(
    application_id: int,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    application = db.get(Application, application_id)
    if application is None or application.student_id != current_student.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    if (
        application.resume_storage_key is None
        or application.resume_original_name is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )

    resume_path = get_stored_resume_path(application.resume_storage_key)
    if resume_path is None or not resume_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )

    return FileResponse(
        path=resume_path,
        media_type="application/pdf",
        filename=application.resume_original_name,
        content_disposition_type="inline",
    )
