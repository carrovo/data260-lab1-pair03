"""Response objects for tables that stay in MySQL but point at Mongo-owned rows.

Applications and registrations live in MySQL. The job or event they refer to may live in
MongoDB (PERSISTENCE=mongo), so SQL cannot join to it. These helpers load the MySQL rows
and attach the job or event (with its company) through the repositories, as objects the
existing response models read in the same way as the ORM objects.
"""

from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.repos import make_repos


def mongo_mode() -> bool:
    return settings.persistence == "mongo"


def application_views(db: Session, applications: list[Any]) -> list[SimpleNamespace]:
    jobs = make_repos(db).jobs.get_many([a.job_id for a in applications])
    return [
        SimpleNamespace(
            id=a.id,
            student_id=a.student_id,
            job_id=a.job_id,
            status=a.status,
            applied_at=a.applied_at,
            resume_original_name=a.resume_original_name,
            resume_size_bytes=a.resume_size_bytes,
            job=jobs[a.job_id],
        )
        for a in applications
        if a.job_id in jobs
    ]


def registration_views(db: Session, registrations: list[Any]) -> list[SimpleNamespace]:
    events = make_repos(db).events.get_many([r.event_id for r in registrations])
    return [
        SimpleNamespace(
            id=r.id,
            student_id=r.student_id,
            event_id=r.event_id,
            registered_at=r.registered_at,
            event=events[r.event_id],
        )
        for r in registrations
        if r.event_id in events
    ]
