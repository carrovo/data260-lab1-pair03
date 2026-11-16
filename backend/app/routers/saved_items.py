"""Small student-owned facade over the existing saved-item stores."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pymongo.errors import DuplicateKeyError

from backend.app.config import settings
from backend.app.models import SavedItem
from backend.app.repos import get_mongo_database, make_repos
from backend.app.routers.student_auth import get_current_student, get_db
from backend.app.schemas.saved_item import SavedItemCreate, SavedItemResponse
from backend.common.mongo_store import SavedItemStore

router = APIRouter(prefix="/auth/saved-items", tags=["saved items"])


class SavedItemRequest(SavedItemCreate):
    model_config = ConfigDict(extra="forbid")
    job_id: int | None = Field(default=None, gt=0, strict=True)
    event_id: int | None = Field(default=None, gt=0, strict=True)


@router.get("", response_model=list[SavedItemResponse])
def list_saved(db: Session = Depends(get_db), student: Any = Depends(get_current_student)):
    if settings.persistence == "mongo":
        return SavedItemStore(get_mongo_database()).list_for_student(student.id)
    return db.scalars(select(SavedItem).where(SavedItem.student_id == student.id)
                      .order_by(SavedItem.saved_at.desc(), SavedItem.id.desc())).all()


@router.post("", response_model=list[SavedItemResponse])
def save(payload: SavedItemRequest, db: Session = Depends(get_db), student: Any = Depends(get_current_student)):
    repos = make_repos(db)
    item_id = payload.job_id if payload.item_type == "job" else payload.event_id
    target = repos.jobs if payload.item_type == "job" else repos.events
    if not target.get(item_id):
        raise HTTPException(404, "Opportunity not found.")
    if not repos.saved_items.exists(student.id, payload.item_type, item_id):
        try:
            repos.saved_items.create(student.id, payload.item_type, item_id)
        except (IntegrityError, DuplicateKeyError):
            db.rollback()  # A concurrent save has already established the desired state.
            if not repos.saved_items.exists(student.id, payload.item_type, item_id):
                raise
    return list_saved(db, student)


@router.delete("/{item_type}/{item_id}", status_code=204)
def unsave(item_type: Literal["job", "event"], item_id: int = Path(gt=0),
           db: Session = Depends(get_db), student: Any = Depends(get_current_student)):
    if settings.persistence == "mongo":
        SavedItemStore(get_mongo_database()).delete(student.id, item_type, item_id)
    else:
        column = SavedItem.job_id if item_type == "job" else SavedItem.event_id
        row = db.scalar(select(SavedItem).where(SavedItem.student_id == student.id, column == item_id))
        if row is not None:
            db.delete(row)
            db.commit()
    return Response(status_code=204)
