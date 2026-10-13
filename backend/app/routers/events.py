from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Event, Registration, Student
from backend.app.routers.student_auth import get_current_student, get_db
from backend.app.schemas.event import EventResponse, RegistrationResponse


router = APIRouter(tags=["student events and registrations"])

DUPLICATE_REGISTRATION_DETAIL = (
    "You are already registered for this event."
)


def event_with_company():
    return selectinload(Event.company)


def registration_with_event_and_company():
    return selectinload(Registration.event).selectinload(Event.company)


@router.get(
    "/events",
    response_model=list[EventResponse],
)
def list_upcoming_events(
    keyword: str | None = Query(
        default=None,
        max_length=100,
    ),
    db: Session = Depends(get_db),
):
    statement = (
        select(Event)
        .where(Event.starts_at >= func.now())
        .options(event_with_company())
    )

    if keyword and keyword.strip():
        title_pattern = f"%{keyword.strip()}%"
        statement = statement.where(Event.title.ilike(title_pattern))

    statement = statement.order_by(Event.starts_at.asc(), Event.id.asc())

    return db.scalars(statement).all()


@router.get(
    "/events/{event_id}",
    response_model=EventResponse,
)
def get_event(
    event_id: int = Path(ge=1),
    db: Session = Depends(get_db),
):
    statement = (
        select(Event)
        .where(Event.id == event_id)
        .options(event_with_company())
    )
    event = db.scalar(statement)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    return event


@router.post(
    "/events/{event_id}/registrations",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_for_event(
    event_id: int = Path(ge=1),
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    existing_registration_id = db.scalar(
        select(Registration.id).where(
            Registration.student_id == current_student.id,
            Registration.event_id == event_id,
        )
    )
    if existing_registration_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_REGISTRATION_DETAIL,
        )

    registration = Registration(
        student_id=current_student.id,
        event_id=event_id,
    )
    db.add(registration)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=DUPLICATE_REGISTRATION_DETAIL,
        ) from exc

    statement = (
        select(Registration)
        .where(Registration.id == registration.id)
        .options(registration_with_event_and_company())
    )

    return db.scalar(statement)


@router.get(
    "/registrations/me",
    response_model=list[RegistrationResponse],
)
def list_current_student_registrations(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    statement = (
        select(Registration)
        .join(Registration.event)
        .where(Registration.student_id == current_student.id)
        .options(registration_with_event_and_company())
        .order_by(Event.starts_at.asc(), Registration.id.asc())
    )

    return db.scalars(statement).all()
