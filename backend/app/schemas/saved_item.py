from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class SavedItemCreate(BaseModel):
    item_type: Literal["job", "event"]
    job_id: int | None = None
    event_id: int | None = None

    @model_validator(mode="after")
    def validate_target(self):
        has_job = self.job_id is not None
        has_event = self.event_id is not None

        if has_job == has_event:
            raise ValueError("Exactly one of job_id or event_id is required.")
        if self.item_type == "job" and not has_job:
            raise ValueError("item_type job requires job_id.")
        if self.item_type == "event" and not has_event:
            raise ValueError("item_type event requires event_id.")
        return self


class SavedItemResponse(SavedItemCreate):
    id: int
    student_id: int
    saved_at: datetime

    model_config = ConfigDict(from_attributes=True)
