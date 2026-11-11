from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.app.models import Event
from backend.app.routers.student_auth import get_db
from backend.app.schemas.event import EventResponse


router = APIRouter(tags=["events"])


def event_with_company():
    return selectinload(Event.company)


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
