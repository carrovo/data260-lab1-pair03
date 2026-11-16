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
        inserted = key not in self.docs
        document = self.docs.setdefault(key, {"_id": key})
        if inserted:
            document.update(update.get("$setOnInsert", {}))
        document.update(update["$set"])


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


def deliver(worker, envelope, db, store=None, publisher=None):
    handlers = WORKERS[worker]
    return process_message(
        envelope.to_json(),
        topic=envelope.event_type,
        consumer=worker,
        handler=lambda e: handlers[e.event_type](e, db),
        store=store or FakeStore(),
        publisher=publisher or FakePublisher(),
        sleep=lambda _s: None,
    )


def test_every_worker_listens_to_the_topic_the_contract_assigns_it():
    assert {name for name in WORKERS} == {
        spec["consumer"]
        for spec in TOPICS.values()
        if spec["consumer"] in WORKERS
    }
    for name, handlers in WORKERS.items():
        for topic in handlers:
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


def application_event(event_type, *, trace_id=None):
    kwargs = {}
    if trace_id is not None:
        kwargs["trace_id"] = trace_id
    return make_event(
        event_type,
        {"application_id": 41, "student_id": 9, "job_id": 7},
        **kwargs,
    )


def test_application_created_writes_one_string_keyed_document():
    db = FakeDb()
    event = application_event("application.created", trace_id="trace-created")

    assert deliver("application-worker", event, db) == Outcome.PROCESSED

    assert list(db["applications"].docs) == ["41"]
    document = db["applications"].docs["41"]
    assert document == {
        "_id": "41",
        "student_id": "9",
        "job_id": "7",
        "created_at": event.occurred_at,
        "updated_at": event.occurred_at,
        "trace_id": "trace-created",
        "last_event_id": event.event_id,
        "last_event_type": "application.created",
    }


def test_application_event_reprocessing_is_idempotent():
    db, store = FakeDb(), FakeStore()
    event = application_event("application.created")

    first = deliver("application-worker", event, db, store)
    second = deliver("application-worker", event, db, store)

    assert (first, second) == (Outcome.PROCESSED, Outcome.DUPLICATE_SKIPPED)
    assert list(db["applications"].docs) == ["41"]
    assert store.ids == {f"application-worker:{event.event_id}"}


def test_application_updated_refreshes_the_existing_document():
    db = FakeDb()
    created = application_event("application.created", trace_id="trace-created")
    updated = application_event("application.updated", trace_id="trace-updated")

    deliver("application-worker", created, db)
    deliver("application-worker", updated, db)

    assert list(db["applications"].docs) == ["41"]
    document = db["applications"].docs["41"]
    assert document["created_at"] == created.occurred_at
    assert document["updated_at"] == updated.occurred_at
    assert document["trace_id"] == "trace-updated"
    assert document["last_event_id"] == updated.event_id
    assert document["last_event_type"] == "application.updated"


def test_failed_application_write_is_retried_and_not_marked_processed():
    class FailingCollection:
        def __init__(self):
            self.attempts = 0

        def update_one(self, *_args, **_kwargs):
            self.attempts += 1
            raise ConnectionError("Mongo is unavailable")

    db, store, publisher = FakeDb(), FakeStore(), FakePublisher()
    db["applications"] = FailingCollection()
    event = application_event("application.created")

    outcome = deliver(
        "application-worker", event, db, store, publisher=publisher
    )

    assert outcome == Outcome.DEAD_LETTERED
    assert db["applications"].attempts == 3
    assert store.ids == set()
    assert publisher.sent[0][0] == "application.created.dlq"
    dead_letter = json.loads(publisher.sent[0][2])
    assert dead_letter["attempts"] == 3
    assert "Mongo is unavailable" in dead_letter["error"]
