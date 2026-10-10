from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
    status: str
    applied_at: datetime
    job: ApplicationJobSummary

    model_config = ConfigDict(from_attributes=True)
