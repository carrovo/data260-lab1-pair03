"""Synthetic evidence: real publisher -> Kafka -> production consumer -> Mongo.

Uses a dedicated database and topic namespace. Never clears existing databases.
Run in the worker image with current source mounted, or a prepared virtualenv.
"""
import argparse
import json
import os
from pathlib import Path
import re
import time
from uuid import uuid4

from backend.common.assistant_memory import EVENT, MemoryStore, seed_demo
from backend.common.events import make_event, kafka_topic, dlq_topic
from backend.common.messaging import (
    DeliveryConfirmedPublisher, ConfluentConsumerClient, MongoProcessedEventStore,
    publish_event, run_consumer,
)
from backend.workers.handlers import WORKERS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed-only", action="store_true", help="Idempotently seed Mongo without Kafka")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,40}", args.label):
        parser.error("label must be 1-40 lowercase letters, digits or hyphens")
    from pymongo import MongoClient

    database_name = "p03_memory_demo_" + args.label.replace("-", "_")
    os.environ["KAFKA_TOPIC_PREFIX"] = f"p03.memorydemo-{args.label}."
    mongo = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000)
    db = mongo[database_name]
    store = MemoryStore(db)
    before = seed_demo(db)
    if args.seed_only:
        print(json.dumps({"database": database_name, "entry_count": len(before), "seed": "idempotent"}))
        mongo.close()
        return
    output = args.output_dir / "memory-evidence.json"
    if output.exists():
        mongo.close()
        raise RuntimeError("Evidence file exists; choose a new output directory")
    from confluent_kafka.admin import AdminClient, NewTopic

    bootstrap = os.environ["KAFKA_BOOTSTRAP"]
    admin = AdminClient({"bootstrap.servers": bootstrap})
    for topic in (kafka_topic(EVENT), kafka_topic(dlq_topic(EVENT))):
        future = admin.create_topics([NewTopic(topic, 1, 1)])[topic]
        try:
            future.result(10)
        except Exception as exc:
            if "TOPIC_ALREADY_EXISTS" not in str(exc):
                raise
    event = make_event(EVENT, {"student_id": "pair03-memory-demo"}, "memory-demo-" + uuid4().hex)
    publisher = DeliveryConfirmedPublisher(bootstrap)
    consumer = ConfluentConsumerClient(bootstrap, "memory-demo-" + uuid4().hex, EVENT)
    processed = MongoProcessedEventStore(db.processed_events)
    publish_event(publisher, event, "pair03-memory-demo")
    deadline = time.monotonic() + 45
    key = "assistant-memory-worker:" + event.event_id
    try:
        while not processed.seen(key) and time.monotonic() < deadline:
            run_consumer(
                consumer, consumer="assistant-memory-worker",
                handler=lambda e: WORKERS["assistant-memory-worker"][e.event_type](e, db),
                store=processed, publisher=publisher, max_messages=1,
            )
        if not processed.seen(key):
            raise RuntimeError("Consumer completion not observed within 45 seconds")
        after = store.entries("pair03-memory-demo")
        evidence = {
            "verification": "real Kafka and Mongo; deterministic consolidation, no live model",
            "database": database_name, "physical_topic": kafka_topic(EVENT),
            "event_id": event.event_id, "trace_id": event.trace_id,
            "before_count": len(before), "before_entries": before,
            "after_count": len(after), "after_entries": after,
            "consumer_completion": db.processed_events.find_one({"_id": key}),
            "decisions": store.document("pair03-memory-demo")["last_consolidation"]["decisions"],
            "explanation": "topic-00 retains corrected-0 dated February 1 over January 1 original-0; duplicates merge. Unrelated topics 03-29 remain.",
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / "memory-evidence.json"
        if output.exists():
            raise RuntimeError("Evidence file exists; choose a new output directory")
        output.write_text(json.dumps(evidence, indent=2, default=str) + "\n")
        assert len(after) == 30 and len(before) in {30, 63}
        print(json.dumps({k: evidence[k] for k in
                          ("database", "physical_topic", "event_id", "trace_id", "before_count", "after_count")}))
        print(f"Evidence: {output}")
    finally:
        consumer._consumer.close()
        mongo.close()


if __name__ == "__main__":
    main()
