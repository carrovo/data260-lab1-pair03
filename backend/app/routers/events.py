from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from backend.app.repos import make_repos
from backend.app.routers.student_auth import get_db
from backend.app.schemas.event import EventResponse


router = APIRouter(tags=["events"])


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
    return make_repos(db).events.list_upcoming(
        keyword.strip() if keyword else ""
    )


@router.get(
    "/events/{event_id}",
    response_model=EventResponse,
)
def get_event(
    event_id: int = Path(ge=1),
    db: Session = Depends(get_db),
):
    event = make_repos(db).events.get(event_id)

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    return event
