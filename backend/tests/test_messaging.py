import json

import pytest

from backend.common.events import make_event
from backend.common.messaging import (
    Outcome,
    process_message,
    publish_event,
    run_consumer,
)

TOPIC = "job.created"
CONSUMER = "job-index-worker"


class WorkerCrash(BaseException):
    """Stands in for a killed worker: not an Exception, so it is not retried."""


class FakeStore:
    def __init__(self):
        self.ids = set()

    def seen(self, event_id):
        return event_id in self.ids

    def mark(self, record):
        self.ids.add(record["_id"])


class FakePublisher:
    def __init__(self):
        self.sent = []

    def send(self, topic, key, value):
        self.sent.append((topic, key, value))


class FakeBroker:
    """A topic log plus the committed offset, shared across restarts."""

    def __init__(self, values):
        self.log = list(values)
        self.committed = 0
        self.calls = []


class FakeClient:
    def __init__(self, broker):
        self.broker = broker
        self.position = broker.committed

    def poll(self):
        if self.position >= len(self.broker.log):
            return None
        message = (self.position, self.broker.log[self.position])
        self.position += 1
        return message

    def value(self, message):
        return message[1]

    def commit(self, message):
        self.broker.committed = message[0] + 1
        self.broker.calls.append("commit")


def job_event(job_id="7"):
    return make_event(
        TOPIC, {"job_id": job_id, "company_id": "2", "title": "Intern"}
    )


def run(raw, handler, store, publisher, **kwargs):
    return process_message(
        raw,
        topic=TOPIC,
        consumer=CONSUMER,
        handler=handler,
        store=store,
        publisher=publisher,
        sleep=lambda _seconds: None,
        **kwargs,
    )


def test_a_good_message_is_processed_and_recorded():
    rows, store, publisher = {}, FakeStore(), FakePublisher()
    envelope = job_event()

    outcome = run(
        envelope.to_json(),
        lambda e: rows.update({e.payload["job_id"]: e.payload}),
        store,
        publisher,
    )

    assert outcome == Outcome.PROCESSED
    assert list(rows) == ["7"]
    assert envelope.event_id in store.ids
    assert publisher.sent == []


def test_failure_case_1_same_event_twice_is_stored_once():
    rows, store, publisher = [], FakeStore(), FakePublisher()
    raw = job_event().to_json()

    first = run(raw, lambda e: rows.append(e.payload["job_id"]), store, publisher)
    second = run(raw, lambda e: rows.append(e.payload["job_id"]), store, publisher)

    assert first == Outcome.PROCESSED
    assert second == Outcome.DUPLICATE_SKIPPED
    assert rows == ["7"]


def test_failure_case_2_killed_worker_reprocesses_without_duplicates():
    rows = {}
    store, publisher = FakeStore(), FakePublisher()
    broker = FakeBroker([job_event().to_json()])
    crash = {"armed": True}

    def handler(envelope):
        if crash["armed"]:
            crash["armed"] = False
            raise WorkerCrash()  # killed before the database write
        rows[envelope.payload["job_id"]] = envelope.payload
        broker.calls.append("write")

    with pytest.raises(WorkerCrash):
        run_consumer(
            FakeClient(broker),
            topic=TOPIC,
            consumer=CONSUMER,
            handler=handler,
            store=store,
            publisher=publisher,
            max_messages=1,
        )

    assert broker.committed == 0  # nothing committed, so nothing is lost
    assert rows == {}

    # restart: Kafka delivers the same message again
    handled = run_consumer(
        FakeClient(broker),
        topic=TOPIC,
        consumer=CONSUMER,
        handler=handler,
        store=store,
        publisher=publisher,
        max_messages=1,
    )

    assert handled == 1
    assert broker.committed == 1
    assert list(rows) == ["7"]


def test_offset_is_committed_only_after_the_database_write():
    store, publisher = FakeStore(), FakePublisher()
    broker = FakeBroker([job_event().to_json()])

    run_consumer(
        FakeClient(broker),
        topic=TOPIC,
        consumer=CONSUMER,
        handler=lambda e: broker.calls.append("write"),
        store=store,
        publisher=publisher,
        max_messages=1,
    )

    assert broker.calls == ["write", "commit"]


def test_failure_case_3_poison_message_goes_to_dead_letter_and_pipeline_continues():
    rows, store, publisher = [], FakeStore(), FakePublisher()
    poison = job_event(job_id="bad").to_json()
    good = job_event(job_id="8").to_json()
    attempts = {"count": 0}

    def handler(envelope):
        if envelope.payload["job_id"] == "bad":
            attempts["count"] += 1
            raise ValueError("cannot index this job")
        rows.append(envelope.payload["job_id"])

    broker = FakeBroker([poison, good])
    run_consumer(
        FakeClient(broker),
        topic=TOPIC,
        consumer=CONSUMER,
        handler=handler,
        store=store,
        publisher=publisher,
        max_messages=2,
        sleep=lambda _seconds: None,
    )

    assert attempts["count"] == 3  # bounded retries
    assert rows == ["8"]  # the next message was still processed
    assert broker.committed == 2
    topic, key, value = publisher.sent[0]
    assert topic == "job.created.dlq"
    dead = json.loads(value)
    assert dead["attempts"] == 3
    assert "cannot index this job" in dead["error"]
    assert json.loads(dead["original"])["payload"]["job_id"] == "bad"


def test_a_failure_that_clears_on_retry_is_not_dead_lettered():
    store, publisher = FakeStore(), FakePublisher()
    attempts = {"count": 0}

    def handler(envelope):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ConnectionError("database not ready")

    outcome = run(job_event().to_json(), handler, store, publisher)

    assert outcome == Outcome.PROCESSED
    assert attempts["count"] == 2
    assert publisher.sent == []


def test_unreadable_message_is_dead_lettered_without_calling_the_handler():
    store, publisher = FakeStore(), FakePublisher()
    called = []

    outcome = run("{not json", lambda e: called.append(e), store, publisher)

    assert outcome == Outcome.DEAD_LETTERED
    assert called == []
    assert publisher.sent[0][0] == "job.created.dlq"


def test_publish_event_sends_json_to_the_topic_named_by_the_event_type():
    publisher = FakePublisher()
    envelope = job_event()

    publish_event(publisher, envelope, key="7")

    topic, key, value = publisher.sent[0]
    assert (topic, key) == ("job.created", "7")
    assert json.loads(value)["event_id"] == envelope.event_id
