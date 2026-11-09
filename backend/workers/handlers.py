"""What each Pair 03 worker does with its events.

Each handler takes the validated envelope and a database object that behaves
like a pymongo Database (db["collection"].update_one(...)). Every write is an
upsert keyed by a business id, so running the same event twice leaves the
same data: Kafka may deliver a message again after a crash.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from backend.common.events import TOPICS, EventEnvelope


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def handle_job_created(envelope: EventEnvelope, db: Any) -> None:
    """job.created -> job_index: one search-index entry per job."""
    payload = envelope.payload
    db["job_index"].update_one(
        {"_id": str(payload["job_id"])},
        {
            "$set": {
                "company_id": str(payload["company_id"]),
                "title": payload["title"],
                "indexed_at": _now(),
                "trace_id": envelope.trace_id,
            }
        },
        upsert=True,
    )


def handle_application_status_changed(
    envelope: EventEnvelope, db: Any
) -> None:
    """application.status_changed -> notifications: tell the student."""
    payload = envelope.payload
    message = (
        f"Your application status changed from {payload['old_status']} "
        f"to {payload['new_status']}."
    )
    db["notifications"].update_one(
        {"_id": envelope.event_id},  # one notification per event
        {
            "$set": {
                "student_id": str(payload["student_id"]),
                "application_id": str(payload["application_id"]),
                "job_id": str(payload["job_id"]),
                "message": message,
                "read": False,
                "created_at": _now(),
                "trace_id": envelope.trace_id,
            }
        },
        upsert=True,
    )


def handle_event_registration_created(
    envelope: EventEnvelope, db: Any
) -> None:
    """event.registration_created -> registrations."""
    payload = envelope.payload
    db["registrations"].update_one(
        {"_id": str(payload["registration_id"])},
        {
            "$set": {
                "student_id": str(payload["student_id"]),
                "event_id": str(payload["event_id"]),
                "registered_at": envelope.occurred_at,
                "trace_id": envelope.trace_id,
            }
        },
        upsert=True,
    )


# worker name -> (topic, handler)
WORKERS: dict[str, tuple[str, Callable[[EventEnvelope, Any], None]]] = {
    "job-index-worker": ("job.created", handle_job_created),
    "notification-worker": (
        "application.status_changed",
        handle_application_status_changed,
    ),
    "event-worker": (
        "event.registration_created",
        handle_event_registration_created,
    ),
}

assert all(TOPICS[topic]["consumer"] == name for name, (topic, _) in WORKERS.items())
