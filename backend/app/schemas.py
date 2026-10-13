from datetime import datetime, timezone
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator

from app.models import JobCategory, ApplicationStatus
from app.config import CITY_SET


def _validate_city(value: Optional[str]) -> Optional[str]:
    """Shared city check — the lab spec requires every pair to use only
    their assigned CITY_SET for jobs/events/companies/students."""
    if value is None:
        return value

    if value not in CITY_SET:
        raise ValueError(f"city must be one of {CITY_SET}, got '{value}'")

    return value


def _normalize_datetime(value: datetime) -> datetime:
    """Convert timezone-aware datetimes to naive UTC.

    SQLAlchemy/MySQL DateTime fields in this project use timezone-naive
    datetime values, so browser/API timestamps containing timezone info
    are normalized before comparison and storage.
    """
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)

    return value


def _validate_future_optional_datetime(
    value: Optional[datetime],
) -> Optional[datetime]:
    """Validate an optional datetime such as a job deadline.

    None is allowed. Timezone-aware values are converted to naive UTC
    before comparison.
    """
    if value is None:
        return value

    value = _normalize_datetime(value)

    if value < datetime.utcnow():
        raise ValueError("deadline must be in the future")

    return value


# -------------------------------------------------------------------
# Auth
# -------------------------------------------------------------------

class CompanySignup(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    location: str

    _validate_location = field_validator("location")(_validate_city)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "company"


# -------------------------------------------------------------------
# Company profile
# -------------------------------------------------------------------

class CompanyProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    location: Optional[str] = None
    description: Optional[str] = None
    contact_info: Optional[str] = None
    profile_picture: Optional[str] = None


class CompanyProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    location: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    contact_info: Optional[str] = Field(default=None, max_length=255)

    _validate_location = field_validator("location")(_validate_city)


# -------------------------------------------------------------------
# Jobs
# -------------------------------------------------------------------

class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    category: JobCategory
    city: str
    location: Optional[str] = None
    salary: Optional[float] = Field(default=None, ge=0)
    skills: Optional[str] = None
    deadline: Optional[datetime] = None

    _validate_city = field_validator("city")(_validate_city)
    _validate_deadline = field_validator("deadline")(
        _validate_future_optional_datetime
    )


class JobUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[JobCategory] = None
    city: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[float] = Field(default=None, ge=0)
    skills: Optional[str] = None
    deadline: Optional[datetime] = None

    _validate_city = field_validator("city")(_validate_city)
    _validate_deadline = field_validator("deadline")(
        _validate_future_optional_datetime
    )


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str
    description: Optional[str] = None
    category: JobCategory
    city: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[float] = None
    skills: Optional[str] = None
    posting_date: datetime
    deadline: Optional[datetime] = None


# -------------------------------------------------------------------
# Applications
# -------------------------------------------------------------------

class ApplicantOut(BaseModel):
    application_id: int
    student_id: int
    student_name: str
    student_email: EmailStr
    college_name: Optional[str] = None
    status: ApplicationStatus
    applied_at: datetime
    resume_path: Optional[str] = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


# -------------------------------------------------------------------
# Events
# -------------------------------------------------------------------

class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    date: datetime
    time: Optional[str] = None
    location: Optional[str] = None
    city: str
    eligibility: Optional[str] = None

    _validate_city = field_validator("city")(_validate_city)

    @field_validator("date")
    @classmethod
    def date_must_be_future(cls, value: datetime) -> datetime:
        value = _normalize_datetime(value)

        if value < datetime.utcnow():
            raise ValueError("event date must be in the future")

        return value


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    description: Optional[str] = None
    date: datetime
    time: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    eligibility: Optional[str] = None


class RegisteredStudentOut(BaseModel):
    student_id: int
    name: str
    email: EmailStr
    college_name: Optional[str] = None
    registered_at: datetime


# -------------------------------------------------------------------
# Students — company-side search/view
# -------------------------------------------------------------------

class StudentSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    college_name: Optional[str] = None
    major: Optional[str] = None
    city: Optional[str] = None
    skills: Optional[str] = None


# -------------------------------------------------------------------
# AI assistant chat
# -------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    student_id: Optional[int] = None
    conversation: Optional[List[dict]] = None
    auto_approve: bool = False


class ChatResponse(BaseModel):
    reply: str
    conversation: List[dict]
    tool_calls: int