from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.models import (
    Company,
    Event,
    Registration,
    Student,
)
from backend.app.routers.company_auth import (
    get_current_company,
    get_db,
)
from backend.app.schemas.event import (
    EventCanonicalResponse,
    EventCreate,
    EventUpdate,
)


router = APIRouter(
    prefix="/api/companies/events",
    tags=["company events"],
)


class RegisteredStudentResponse(BaseModel):
    student_id: int
    full_name: str
    email: str
    college_name: str | None
    major: str | None
    city: str
    skills: str | None
    registered_at: datetime


def _owned_event_or_404(
    db: Session,
    event_id: int,
    company_id: int,
) -> Event:
    statement = (
        select(Event)
        .where(
            Event.id == event_id,
            Event.company_id == company_id,
        )
        .options(selectinload(Event.company))
    )

    event = db.scalar(statement)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    return event


@router.post(
    "",
    response_model=EventCanonicalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    event = Event(
        company_id=current_company.id,
        **payload.model_dump(),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return _owned_event_or_404(
        db,
        event.id,
        current_company.id,
    )


@router.get(
    "",
    response_model=list[EventCanonicalResponse],
)
def list_company_events(
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    statement = (
        select(Event)
        .where(Event.company_id == current_company.id)
        .options(selectinload(Event.company))
        .order_by(Event.starts_at.asc(), Event.id.asc())
    )

    return list(db.scalars(statement).all())


@router.get(
    "/{event_id}",
    response_model=EventCanonicalResponse,
)
def get_company_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    return _owned_event_or_404(
        db,
        event_id,
        current_company.id,
    )


@router.put(
    "/{event_id}",
    response_model=EventCanonicalResponse,
)
def update_company_event(
    event_id: int,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    event = _owned_event_or_404(
        db,
        event_id,
        current_company.id,
    )

    update_data = payload.model_dump(exclude_unset=True)

    final_starts_at = update_data.get(
        "starts_at",
        event.starts_at,
    )
    final_ends_at = update_data.get(
        "ends_at",
        event.ends_at,
    )

    if final_ends_at < final_starts_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ends_at must be on or after starts_at.",
        )

    for field, value in update_data.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)

    return _owned_event_or_404(
        db,
        event.id,
        current_company.id,
    )


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_company_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    event = _owned_event_or_404(
        db,
        event_id,
        current_company.id,
    )

    if event.registrations:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete an event that already has registrations.",
        )

    try:
        db.delete(event)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event cannot be deleted because related records exist.",
        ) from exc

    return None


@router.get(
    "/{event_id}/registrants",
    response_model=list[RegisteredStudentResponse],
)
def list_event_registrants(
    event_id: int,
    db: Session = Depends(get_db),
    current_company: Company = Depends(get_current_company),
):
    event = _owned_event_or_404(
        db,
        event_id,
        current_company.id,
    )

    statement = (
        select(Registration, Student)
        .join(
            Student,
            Registration.student_id == Student.id,
        )
        .where(Registration.event_id == event.id)
        .order_by(
            Registration.registered_at.desc(),
            Registration.id.desc(),
        )
    )

    rows = db.execute(statement).all()

    return [
        RegisteredStudentResponse(
            student_id=student.id,
            full_name=student.full_name,
            email=student.email,
            college_name=student.college_name,
            major=student.major,
            city=student.city,
            skills=student.skills,
            registered_at=registration.registered_at,
        )
        for registration, student in rows
    ]