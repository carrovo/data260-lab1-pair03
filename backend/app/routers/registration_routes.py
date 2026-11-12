"""Student event registration (register for an event, list my registrations).

Split out of events.py so the Event service can load the event routes and the
registration routes as two routers.
"""

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Event, Registration, Student
from backend.app.persistence_views import mongo_mode, registration_views
from backend.app.repos import make_repos
from backend.app.routers.student_auth import get_current_student, get_db
from backend.app.schemas.event import RegistrationResponse
from backend.common.outgoing import publish_safely


router = APIRouter(tags=["student event registrations"])

DUPLICATE_REGISTRATION_DETAIL = (
    "You are already registered for this event."
)


def registration_with_event_and_company():
    return selectinload(Registration.event).selectinload(Event.company)


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
    event = (
        make_repos(db).events.get(event_id)
        if mongo_mode()
        else db.get(Event, event_id)
    )
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

    publish_safely(
        "event.registration_created",
        {
            "registration_id": str(registration.id),
            "student_id": str(registration.student_id),
            "event_id": str(registration.event_id),
        },
        key=str(registration.id),
    )

    if mongo_mode():
        return registration_views(db, [registration])[0]

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
    if mongo_mode():
        rows = list(
            db.scalars(
                select(Registration).where(
                    Registration.student_id == current_student.id
                )
            ).all()
        )
        views = registration_views(db, rows)
        return sorted(views, key=lambda v: (v.event.starts_at, v.id))

    statement = (
        select(Registration)
        .join(Registration.event)
        .where(Registration.student_id == current_student.id)
        .options(registration_with_event_and_company())
        .order_by(Event.starts_at.asc(), Registration.id.asc())
    )

    return db.scalars(statement).all()
