from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event, EventRegistration, Student
from app.schemas import EventCreate, EventOut, RegisteredStudentOut
from app.auth import require_company

router = APIRouter(prefix="/api/companies/events", tags=["company-events"])


def _owned_event_or_404(db: Session, event_id: int, company_id: int) -> Event:
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.company_id != company_id:
        raise HTTPException(status_code=403, detail="This event belongs to another company")
    return event


@router.post("", response_model=EventOut, status_code=201)
def post_event(payload: EventCreate, db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    company_id = int(claims["sub"])
    event = Event(company_id=company_id, **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("", response_model=List[EventOut])
def list_owned_events(db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    company_id = int(claims["sub"])
    return db.query(Event).filter(Event.company_id == company_id).order_by(Event.date.asc()).all()


@router.get("/{event_id}/registrants", response_model=List[RegisteredStudentOut])
def list_registrants(event_id: int, db: Session = Depends(get_db), claims: dict = Depends(require_company)):
    event = _owned_event_or_404(db, event_id, int(claims["sub"]))
    rows = (
        db.query(EventRegistration, Student)
        .join(Student, EventRegistration.student_id == Student.id)
        .filter(EventRegistration.event_id == event.id)
        .order_by(EventRegistration.registered_at.desc())
        .all()
    )
    return [
        RegisteredStudentOut(
            student_id=student.id,
            name=student.name,
            email=student.email,
            college_name=student.college_name,
            registered_at=reg.registered_at,
        )
        for reg, student in rows
    ]
