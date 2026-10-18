from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    city: str = Field(min_length=1, max_length=100)
    starts_at: datetime
    ends_at: datetime
    location: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    eligibility: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_date_order(self):
        if self.ends_at < self.starts_at:
            raise ValueError("ends_at must be on or after starts_at.")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    eligibility: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_date_order(self):
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at < self.starts_at
        ):
            raise ValueError("ends_at must be on or after starts_at.")
        return self


class EventCanonicalResponse(BaseModel):
    id: int
    company_id: int | None
    title: str
    description: str
    city: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    major: str | None
    eligibility: str | None
    company: CompanySummary | None

    model_config = ConfigDict(from_attributes=True)
