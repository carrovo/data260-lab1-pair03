from datetime import datetime

from pydantic import BaseModel, ConfigDict


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