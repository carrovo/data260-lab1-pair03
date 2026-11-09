"""Kafka producer and consumer helpers shared by every Pair 03 service.

The processing rules live in plain Python so they can be tested without a
running Kafka broker:

  * a duplicate event is skipped (idempotency through processed_events)
  * the offset is committed only after the database write has succeeded
  * a failing message is retried a bounded number of times, then moved to
    the dead-letter topic so the pipeline keeps going

The real Kafka client (confluent-kafka) and MongoDB (pymongo) are imported
lazily inside the adapter classes at the bottom of this file.
"""

from __future__ import annotations

import enum
import json
import logging
import time
from typing import Any, Callable, Protocol

from .events import (
    EventEnvelope,
    build_dlq_message,
    dlq_topic,
    processed_event_record,
)

logger = logging.getLogger("p03.messaging")

MAX_ATTEMPTS = 3


class Outcome(str, enum.Enum):
    PROCESSED = "processed"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    DEAD_LETTERED = "dead_lettered"


class ProcessedEventStore(Protocol):
    def seen(self, event_id: str) -> bool: ...

    def mark(self, record: dict[str, Any]) -> None: ...


class Publisher(Protocol):
    def send(self, topic: str, key: str | None, value: str) -> None: ...


class ConsumerClient(Protocol):
    def poll(self) -> Any | None: ...

    def value(self, message: Any) -> str | bytes: ...

    def commit(self, message: Any) -> None: ...


# --------------------------------------------------------------------------
# producing
# --------------------------------------------------------------------------


def publish_event(
    publisher: Publisher, envelope: EventEnvelope, key: str | None = None
) -> None:
    """Publish one envelope to the topic named by its event_type."""
    publisher.send(envelope.event_type, key, envelope.to_json())
    logger.info(
        "published event_type=%s event_id=%s trace_id=%s",
        envelope.event_type,
        envelope.event_id,
        envelope.trace_id,
    )


# --------------------------------------------------------------------------
# consuming
# --------------------------------------------------------------------------


def process_message(
    raw: str | bytes,
    *,
    topic: str,
    consumer: str,
    handler: Callable[[EventEnvelope], None],
    store: ProcessedEventStore,
    publisher: Publisher,
    max_attempts: int = MAX_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> Outcome:
    """Handle one message and say what happened to it.

    The handler writes to the database and must be safe to run twice for the
    same event (use an upsert keyed by the business id). The event is marked
    processed only after the handler succeeds, so a crash between the two is
    repaired by redelivery, not by losing the event.
    """
    try:
        envelope = EventEnvelope.from_json(raw)
    except Exception as exc:  # noqa: BLE001 - any bad message is poison
        logger.warning("poison message topic=%s error=%s", topic, exc)
        _dead_letter(publisher, topic, raw, f"invalid message: {exc}", 0)
        return Outcome.DEAD_LETTERED

    if store.seen(envelope.event_id):
        logger.info(
            "duplicate skipped event_id=%s trace_id=%s",
            envelope.event_id,
            envelope.trace_id,
        )
        return Outcome.DUPLICATE_SKIPPED

    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            handler(envelope)
            store.mark(processed_event_record(envelope, consumer))
        except Exception as exc:  # noqa: BLE001 - retry any handler failure
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "attempt %d/%d failed event_id=%s trace_id=%s error=%s",
                attempt,
                max_attempts,
                envelope.event_id,
                envelope.trace_id,
                last_error,
            )
            if attempt < max_attempts:
                sleep(0.5 * attempt)
            continue
        logger.info(
            "processed event_id=%s trace_id=%s attempts=%d",
            envelope.event_id,
            envelope.trace_id,
            attempt,
        )
        return Outcome.PROCESSED

    _dead_letter(publisher, topic, raw, last_error, max_attempts)
    return Outcome.DEAD_LETTERED


def _dead_letter(
    publisher: Publisher,
    topic: str,
    raw: str | bytes,
    error: str,
    attempts: int,
) -> None:
    message = build_dlq_message(raw, error, attempts)
    publisher.send(dlq_topic(topic), None, json.dumps(message))
    logger.error("dead-lettered topic=%s error=%s", dlq_topic(topic), error)


def run_consumer(
    client: ConsumerClient,
    *,
    topic: str,
    consumer: str,
    handler: Callable[[EventEnvelope], None],
    store: ProcessedEventStore,
    publisher: Publisher,
    max_messages: int | None = None,
    max_attempts: int = MAX_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Poll, process, then commit. Returns how many messages it handled.

    The offset is committed only after process_message has finished, which
    means after the database write (or after the message reached the
    dead-letter topic). If the process dies before that, nothing is
    committed and Kafka delivers the message again after a restart.
    """
    handled = 0
    while max_messages is None or handled < max_messages:
        message = client.poll()
        if message is None:
            if max_messages is not None:
                break
            continue
        process_message(
            client.value(message),
            topic=topic,
            consumer=consumer,
            handler=handler,
            store=store,
            publisher=publisher,
            max_attempts=max_attempts,
            sleep=sleep,
        )
        client.commit(message)
        handled += 1
    return handled


# --------------------------------------------------------------------------
# adapters for the real systems (imported lazily; not covered by unit tests)
# --------------------------------------------------------------------------


class MongoProcessedEventStore:
    """processed_events collection; _id is the event_id."""

    def __init__(self, collection: Any) -> None:
        self._collection = collection

    def seen(self, event_id: str) -> bool:
        return self._collection.find_one({"_id": event_id}) is not None

    def mark(self, record: dict[str, Any]) -> None:
        from pymongo.errors import DuplicateKeyError

        try:
            self._collection.insert_one(record)
        except DuplicateKeyError:
            pass  # already recorded by an earlier delivery


class ConfluentPublisher:
    def __init__(self, bootstrap_servers: str) -> None:
        from confluent_kafka import Producer

        self._producer = Producer({"bootstrap.servers": bootstrap_servers})

    def send(self, topic: str, key: str | None, value: str) -> None:
        self._producer.produce(topic, key=key, value=value)
        self._producer.flush(10)


class ConfluentConsumerClient:
    def __init__(
        self, bootstrap_servers: str, group_id: str, topic: str
    ) -> None:
        from confluent_kafka import Consumer

        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "enable.auto.commit": False,  # commit only after the write
                "auto.offset.reset": "earliest",
            }
        )
        self._consumer.subscribe([topic])

    def poll(self) -> Any | None:
        message = self._consumer.poll(1.0)
        if message is None or message.error():
            return None
        return message

    def value(self, message: Any) -> str | bytes:
        return message.value()

    def commit(self, message: Any) -> None:
        self._consumer.commit(message=message, asynchronous=False)
