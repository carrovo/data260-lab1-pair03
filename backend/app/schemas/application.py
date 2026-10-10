from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.application_status import ApplicationStatus
from backend.app.schemas.job import CompanySummary


class ApplicationJobSummary(BaseModel):
    id: int
    title: str
    city: str
    company: CompanySummary

    model_config = ConfigDict(from_attributes=True)


class ApplicationResponse(BaseModel):
    id: int
    student_id: int
    job_id: int
    status: ApplicationStatus
    applied_at: datetime
    resume_original_name: str | None
    resume_size_bytes: int | None
    job: ApplicationJobSummary

    model_config = ConfigDict(from_attributes=True)
