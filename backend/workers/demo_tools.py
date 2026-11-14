"""Helpers for the Kafka failure demos (scripts/kafka_failure_demo.sh).

Run inside a worker pod, which already has the Kafka and Mongo settings:
  python -m backend.workers.demo_tools publish <job_id> <title> [--twice]
  python -m backend.workers.demo_tools raw "<any text>"
  python -m backend.workers.demo_tools count <job_id> <event_id>
  python -m backend.workers.demo_tools dlq <text-to-find>
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid

from backend.common.events import dlq_topic, kafka_topic, make_event
from backend.common.messaging import ConfluentPublisher

TOPIC = "job.created"


def _bootstrap() -> str:
    return os.environ["KAFKA_BOOTSTRAP"]


def _db():
    from pymongo import MongoClient

    return MongoClient(os.environ["MONGO_URL"])[os.environ.get("MONGO_DB", "p03_handshake")]


def publish(job_id: str, title: str, twice: bool) -> None:
    envelope = make_event(
        TOPIC, {"job_id": job_id, "company_id": "demo", "title": title}
    )
    publisher = ConfluentPublisher(_bootstrap())
    for _ in range(2 if twice else 1):
        publisher.send(TOPIC, job_id, envelope.to_json())  # same key, same event_id
    print(envelope.event_id)


def raw(text: str) -> None:
    ConfluentPublisher(_bootstrap()).send(TOPIC, None, text)
    print("sent raw message")


def count(job_id: str, event_id: str) -> None:
    db = _db()
    print(
        f"job_index docs for {job_id}: {db['job_index'].count_documents({'_id': job_id})}; "
        f"processed_events for event {event_id}: "
        f"{db['processed_events'].count_documents({'event_id': event_id})}"
    )


def dlq(needle: str) -> None:
    from confluent_kafka import Consumer

    consumer = Consumer(
        {
            "bootstrap.servers": _bootstrap(),
            "group.id": "demo-reader-" + uuid.uuid4().hex[:8],
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([kafka_topic(dlq_topic(TOPIC))])
    deadline = time.time() + 15
    found = 0
    while time.time() < deadline:
        message = consumer.poll(1.0)
        if message is None or message.error():
            continue
        body = json.loads(message.value())
        if needle in body.get("original", ""):
            found += 1
            print(
                f"  DLQ: attempts={body['attempts']} error={body['error'][:90]} "
                f"original={body['original'][:70]}"
            )
    consumer.close()
    print(f"dead-letter messages matching '{needle}': {found}")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "publish":
        publish(args[0], args[1], "--twice" in args)
    elif cmd == "raw":
        raw(args[0])
    elif cmd == "count":
        count(args[0], args[1])
    elif cmd == "dlq":
        dlq(args[0])
    else:
        raise SystemExit(__doc__)
