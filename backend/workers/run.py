"""Run one worker: WORKER_NAME=job-index-worker python -m backend.workers.run

Settings come from the environment (never from the image):
  WORKER_NAME        job-index-worker | notification-worker | event-worker
  KAFKA_BOOTSTRAP    for example p03-kafka:9092
  MONGO_URL          for example mongodb://p03-mongo:27017
  MONGO_DB           defaults to p03_handshake
"""

from __future__ import annotations

import logging
import os
import sys
import time

from backend.common.messaging import (
    ConfluentConsumerClient,
    ConfluentPublisher,
    MongoProcessedEventStore,
    run_consumer,
)
from backend.workers.handlers import WORKERS


logger = logging.getLogger("p03.worker")


def _with_demo_hooks(handler):
    """Failure-demo hooks, OFF unless DEMO_FAILURE_HOOKS=1 (scripts/kafka_failure_demo.sh).

    A job titled "DEMO-SLOW ..." sleeps DEMO_SLOW_SECONDS before its database write
    (a window to kill the pod in); "DEMO-FAIL ..." always raises (to show retries).
    """
    if os.environ.get("DEMO_FAILURE_HOOKS") != "1":
        return handler
    seconds = float(os.environ.get("DEMO_SLOW_SECONDS", "25"))

    def wrapped(envelope):
        title = str(envelope.payload.get("title", ""))
        if title.startswith("DEMO-FAIL"):
            raise RuntimeError("demo: simulated handler failure")
        if title.startswith("DEMO-SLOW"):
            logger.warning("demo: slow handler started event_id=%s", envelope.event_id)
            time.sleep(seconds)
        handler(envelope)

    return wrapped


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
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("MONGO_DB", "p03_handshake")]

    run_consumer(
        ConfluentConsumerClient(bootstrap, group_id=name, topic=topic),
        topic=topic,
        consumer=name,
        handler=_with_demo_hooks(lambda envelope: handler(envelope, db)),
        store=MongoProcessedEventStore(db["processed_events"]),
        publisher=ConfluentPublisher(bootstrap),
    )


if __name__ == "__main__":
    main()
