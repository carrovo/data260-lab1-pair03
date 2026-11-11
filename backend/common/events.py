"""Kafka event contract shared by every Pair 03 service and worker.

Every message on every topic is one EventEnvelope serialised as JSON.
See contracts/README.md for the rules this module enforces.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator


TRACE_HEADER = "X-Trace-Id"

# topic -> who publishes it, who consumes it, and the payload keys it must carry
TOPICS: dict[str, dict[str, Any]] = {
    "application.created": {
        "producer": "application",
        "consumer": "application-worker",
        "required": ["application_id", "student_id", "job_id"],
    },
    "application.updated": {
        "producer": "application",
        "consumer": "application-worker",
        "required": ["application_id", "student_id", "job_id"],
    },
    "application.status_changed": {
        "producer": "company",
        "consumer": "notification-worker",
        "required": [
            "application_id",
            "student_id",
            "job_id",
            "old_status",
            "new_status",
        ],
    },
    "event.registration_created": {
        "producer": "event",
        "consumer": "event-worker",
        "required": ["registration_id", "student_id", "event_id"],
    },
    "job.created": {
        "producer": "job",
        "consumer": "job-index-worker",
        "required": ["job_id", "company_id", "title"],
    },
}


def dlq_topic(topic: str) -> str:
    """Dead-letter topic for a topic: one per topic, suffix .dlq."""
    return f"{topic}.dlq"


def new_trace_id() -> str:
    return uuid.uuid4().hex


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    trace_id: str
    occurred_at: str = Field(default_factory=_utc_now_iso)
    producer: str
    payload: dict[str, Any]

    @model_validator(mode="after")
    def _check_contract(self) -> "EventEnvelope":
        spec = TOPICS.get(self.event_type)
        if spec is None:
            raise ValueError(f"Unknown event_type: {self.event_type}")
        if self.producer != spec["producer"]:
            raise ValueError(
                f"{self.event_type} must be produced by "
                f"{spec['producer']}, not {self.producer}"
            )
        missing = [k for k in spec["required"] if k not in self.payload]
        if missing:
            raise ValueError(
                f"{self.event_type} payload is missing: {', '.join(missing)}"
            )
        return self

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str | bytes) -> "EventEnvelope":
        return cls.model_validate(json.loads(raw))


def make_event(
    event_type: str,
    payload: dict[str, Any],
    trace_id: str | None = None,
) -> EventEnvelope:
    """Build a valid envelope. The producer comes from the topic table."""
    spec = TOPICS.get(event_type)
    if spec is None:
        raise ValueError(f"Unknown event_type: {event_type}")
    return EventEnvelope(
        event_type=event_type,
        trace_id=trace_id or new_trace_id(),
        producer=spec["producer"],
        payload=payload,
    )


def processed_event_key(consumer: str, event_id: str) -> str:
    """Idempotency key: one entry per (consumer, event)."""
    return f"{consumer}:{event_id}"


def processed_event_record(
    envelope: EventEnvelope, consumer: str
) -> dict[str, Any]:
    """Document written to the processed_events collection.

    _id is "<consumer>:<event_id>", so inserting the same event twice for
    the same consumer fails on the unique primary key (the idempotency
    guarantee), while a different consumer can still process the event.
    """
    return {
        "_id": processed_event_key(consumer, envelope.event_id),
        "event_id": envelope.event_id,
        "event_type": envelope.event_type,
        "consumer": consumer,
        "trace_id": envelope.trace_id,
        "processed_at": _utc_now_iso(),
    }


def build_dlq_message(
    raw_message: str | bytes, error: str, attempts: int
) -> dict[str, Any]:
    """Wrap a message that could not be processed for the .dlq topic."""
    original = raw_message.decode("utf-8", "replace") if isinstance(
        raw_message, bytes
    ) else raw_message
    return {
        "original": original,
        "error": error,
        "attempts": attempts,
        "failed_at": _utc_now_iso(),
    }
