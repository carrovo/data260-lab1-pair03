"""Publish events from a web request without ever breaking the request.

Services call publish_safely() after the database commit. If Kafka is not
configured (KAFKA_BOOTSTRAP unset, as in the unit tests and the single-process
app) it does nothing. If Kafka is configured but down, the failure is logged
and the user's request still succeeds.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .events import make_event
from .messaging import Publisher, publish_event

logger = logging.getLogger("p03.outgoing")

_publisher: Publisher | None = None
_initialised = False


def get_publisher() -> Publisher | None:
    global _publisher, _initialised
    if _initialised:
        return _publisher
    _initialised = True
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP")
    if not bootstrap:
        return None
    try:
        from .messaging import ConfluentPublisher

        _publisher = ConfluentPublisher(bootstrap, flush_timeout=0)
    except Exception:  # noqa: BLE001 - never fail a request over Kafka
        logger.exception("could not create the Kafka publisher")
        _publisher = None
    return _publisher


def set_publisher(publisher: Publisher | None) -> None:
    """For tests: install a fake publisher (or None)."""
    global _publisher, _initialised
    _publisher = publisher
    _initialised = True


def reset() -> None:
    global _publisher, _initialised
    _publisher = None
    _initialised = False


def publish_safely(
    event_type: str,
    payload: dict[str, Any],
    trace_id: str | None = None,
    key: str | None = None,
) -> bool:
    """Publish one event. Returns True if it was handed to Kafka."""
    publisher = get_publisher()
    if publisher is None:
        return False
    try:
        publish_event(publisher, make_event(event_type, payload, trace_id), key)
        return True
    except Exception:  # noqa: BLE001 - the request must still succeed
        logger.exception("could not publish %s", event_type)
        return False
