"""Run one worker: WORKER_NAME=job-index-worker python -m backend.workers.run

Settings come from the environment (never from the image):
  WORKER_NAME        job-index-worker | notification-worker | event-worker
  KAFKA_BOOTSTRAP    for example p03-kafka:9092
  MONGO_URL          for example mongodb://p03-mongo:27017
  MONGO_DB           defaults to p03
"""

from __future__ import annotations

import logging
import os
import sys

from backend.common.messaging import (
    ConfluentConsumerClient,
    ConfluentPublisher,
    MongoProcessedEventStore,
    run_consumer,
)
from backend.workers.handlers import WORKERS


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    name = os.environ.get("WORKER_NAME") or (
        sys.argv[1] if len(sys.argv) > 1 else ""
    )
    if name not in WORKERS:
        raise SystemExit(
            f"WORKER_NAME must be one of: {', '.join(sorted(WORKERS))}"
        )
    topic, handler = WORKERS[name]

    from pymongo import MongoClient

    bootstrap = os.environ["KAFKA_BOOTSTRAP"]
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("MONGO_DB", "p03")]

    run_consumer(
        ConfluentConsumerClient(bootstrap, group_id=name, topic=topic),
        topic=topic,
        consumer=name,
        handler=lambda envelope: handler(envelope, db),
        store=MongoProcessedEventStore(db["processed_events"]),
        publisher=ConfluentPublisher(bootstrap),
    )


if __name__ == "__main__":
    main()
