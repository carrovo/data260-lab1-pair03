from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class JobCategory(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    ON_CAMPUS = "on_campus"
    INTERNSHIP = "internship"


class CompanySummary(BaseModel):
    id: int
    name: str
    city: str

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: int
    company_id: int
    title: str
    description: str
    city: str
    created_at: datetime
    company: CompanySummary

    model_config = ConfigDict(from_attributes=True)


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    city: str = Field(min_length=1, max_length=100)
    category: JobCategory
    location: str | None = Field(default=None, max_length=255)
    is_remote: bool = False
    salary: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    skills: str | None = None
    deadline: datetime | None = None


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    category: JobCategory | None = None
    location: str | None = Field(default=None, max_length=255)
    is_remote: bool | None = None
    salary: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    skills: str | None = None
    deadline: datetime | None = None


class JobCanonicalResponse(BaseModel):
    id: int
    company_id: int
    title: str
    description: str
    city: str
    category: JobCategory | None
    location: str | None
    is_remote: bool
    salary: Decimal | None
    skills: str | None
    deadline: datetime | None
    created_at: datetime
    company: CompanySummary

    model_config = ConfigDict(from_attributes=True)
