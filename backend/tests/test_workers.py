import json

from backend.common.events import TOPICS, make_event
from backend.common.messaging import Outcome, process_message
from backend.workers.handlers import WORKERS


class FakeCollection:
    def __init__(self):
        self.docs = {}

    def update_one(self, filter, update, upsert=False):
        key = filter["_id"]
        if key not in self.docs and not upsert:
            return
        self.docs.setdefault(key, {"_id": key}).update(update["$set"])


class FakeDb(dict):
    def __missing__(self, name):
        self[name] = FakeCollection()
        return self[name]


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


def deliver(worker, envelope, db, store=None):
    topic, handler = WORKERS[worker]
    return process_message(
        envelope.to_json(),
        topic=topic,
        consumer=worker,
        handler=lambda e: handler(e, db),
        store=store or FakeStore(),
        publisher=FakePublisher(),
        sleep=lambda _s: None,
    )


def test_every_worker_listens_to_the_topic_the_contract_assigns_it():
    assert {name for name in WORKERS} == {
        spec["consumer"]
        for spec in TOPICS.values()
        if spec["consumer"] in WORKERS
    }
    for name, (topic, _handler) in WORKERS.items():
        assert TOPICS[topic]["consumer"] == name


def test_job_index_worker_indexes_the_job():
    db = FakeDb()
    event = make_event(
        "job.created", {"job_id": 7, "company_id": 2, "title": "Data Intern"}
    )

    assert deliver("job-index-worker", event, db) == Outcome.PROCESSED

    entry = db["job_index"].docs["7"]
    assert entry["title"] == "Data Intern"
    assert entry["company_id"] == "2"
    assert entry["trace_id"] == event.trace_id


def test_notification_worker_creates_one_notification_per_event():
    db = FakeDb()
    event = make_event(
        "application.status_changed",
        {
            "application_id": "5",
            "student_id": "9",
            "job_id": "7",
            "old_status": "Pending",
            "new_status": "Reviewed",
        },
    )

    deliver("notification-worker", event, db)
    deliver("notification-worker", event, db, store=FakeStore())  # redelivered

    assert list(db["notifications"].docs) == [event.event_id]
    note = db["notifications"].docs[event.event_id]
    assert note["student_id"] == "9"
    assert note["read"] is False
    assert "Pending" in note["message"] and "Reviewed" in note["message"]


def test_event_worker_writes_the_registration_once():
    db = FakeDb()
    event = make_event(
        "event.registration_created",
        {"registration_id": "11", "student_id": "9", "event_id": "3"},
    )

    deliver("event-worker", event, db)
    deliver("event-worker", event, db, store=FakeStore())

    assert list(db["registrations"].docs) == ["11"]
    assert db["registrations"].docs["11"]["event_id"] == "3"


def test_the_same_event_delivered_twice_is_skipped_by_the_store():
    db, store = FakeDb(), FakeStore()
    event = make_event(
        "job.created", {"job_id": "1", "company_id": "1", "title": "x"}
    )

    first = deliver("job-index-worker", event, db, store)
    second = deliver("job-index-worker", event, db, store)

    assert (first, second) == (Outcome.PROCESSED, Outcome.DUPLICATE_SKIPPED)
