from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.schemas.job import CompanySummary


class EventResponse(BaseModel):
    id: int
    company_id: int | None
    title: str
    description: str
    city: str
    starts_at: datetime
    ends_at: datetime
    company: CompanySummary | None

    model_config = ConfigDict(from_attributes=True)


class RegistrationResponse(BaseModel):
    id: int
    student_id: int
    event_id: int
    registered_at: datetime
    event: EventResponse

    model_config = ConfigDict(from_attributes=True)
