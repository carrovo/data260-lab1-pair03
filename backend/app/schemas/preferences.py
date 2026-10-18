from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.job import JobCategory


class JobSearchPreferences(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    category: JobCategory | None = None
    city: str | None = Field(default=None, max_length=100)
    is_remote: bool | None = None
    skills: list[str] | None = None
    min_salary: Decimal | None = Field(default=None, ge=0)
    deadline_before: datetime | None = None


class EventSearchPreferences(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    major: str | None = Field(default=None, max_length=255)
    eligibility: str | None = Field(default=None, max_length=255)
    starts_after: datetime | None = None
    starts_before: datetime | None = None


class StudentPreferencesCreate(BaseModel):
    job_preferences: JobSearchPreferences | None = None
    event_preferences: EventSearchPreferences | None = None


class StudentPreferencesUpdate(StudentPreferencesCreate):
    pass


class StudentPreferencesResponse(StudentPreferencesCreate):
    student_id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
