import json
import re
from pathlib import Path

import pytest

from backend.common.events import (
    TOPICS,
    EventEnvelope,
    build_dlq_message,
    dlq_topic,
    make_event,
    processed_event_record,
)

ROOT = Path(__file__).resolve().parents[2]
SERVICES = json.loads((ROOT / "contracts" / "services.json").read_text())


def test_ports_are_unique_and_inside_the_pair_block():
    ports = [s["port"] for s in SERVICES["services"]]

    assert len(ports) == len(set(ports))
    assert all(9030 <= port <= 9039 for port in ports)


def test_image_names_use_the_pair_prefix():
    assert all(s["image"].startswith("p03-") for s in SERVICES["services"])


@pytest.mark.parametrize(
    "service", [s for s in SERVICES["services"] if s["status"] == "ready"]
)
def test_dockerfile_port_matches_the_contract(service):
    dockerfile = ROOT / "backend" / "services" / service["name"] / "Dockerfile"
    if not dockerfile.exists():
        pytest.skip(f"{service['name']} Dockerfile is on another branch")

    text = dockerfile.read_text()
    ports = set(re.findall(r"EXPOSE (\d+)", text))
    ports |= set(re.findall(r"127\.0\.0\.1:(\d+)/health", text))
    ports |= set(re.findall(r'"--port", "(\d+)"', text))

    assert ports == {str(service["port"])}


@pytest.mark.parametrize("topic", sorted(TOPICS))
def test_every_example_is_a_valid_envelope(topic):
    raw = (ROOT / "contracts" / "examples" / f"{topic}.json").read_text()

    envelope = EventEnvelope.from_json(raw)

    assert envelope.event_type == topic
    assert envelope.producer == TOPICS[topic]["producer"]


def test_make_event_fills_id_trace_and_time():
    envelope = make_event(
        "job.created", {"job_id": "7", "company_id": "2", "title": "Intern"}
    )

    assert envelope.event_id and envelope.trace_id and envelope.occurred_at
    assert envelope.producer == "job"


def test_make_event_keeps_a_given_trace_id():
    envelope = make_event(
        "job.created",
        {"job_id": "7", "company_id": "2", "title": "Intern"},
        trace_id="abc123",
    )

    assert envelope.trace_id == "abc123"


def test_envelope_round_trips_through_json():
    envelope = make_event(
        "event.registration_created",
        {"registration_id": "1", "student_id": "2", "event_id": "3"},
    )

    assert EventEnvelope.from_json(envelope.to_json()) == envelope


def test_unknown_topic_is_rejected():
    with pytest.raises(ValueError):
        make_event("job.deleted", {})


def test_missing_payload_key_is_rejected():
    with pytest.raises(ValueError):
        make_event("job.created", {"job_id": "7"})


def test_wrong_producer_is_rejected():
    with pytest.raises(ValueError):
        EventEnvelope(
            event_type="job.created",
            trace_id="t",
            producer="company",
            payload={"job_id": "1", "company_id": "1", "title": "x"},
        )


def test_dead_letter_topic_name():
    assert dlq_topic("job.created") == "job.created.dlq"


def test_processed_event_record_uses_consumer_and_event_id_as_key():
    envelope = make_event(
        "job.created", {"job_id": "7", "company_id": "2", "title": "Intern"}
    )

    record = processed_event_record(envelope, "job-index-worker")

    assert record["_id"] == f"job-index-worker:{envelope.event_id}"
    assert record["event_id"] == envelope.event_id
    other = processed_event_record(envelope, "notification-worker")
    assert other["_id"] != record["_id"]
    assert record["consumer"] == "job-index-worker"


def test_dead_letter_message_keeps_original_and_reason():
    message = build_dlq_message('{"bad": true}', "invalid payload", 3)

    assert message["original"] == '{"bad": true}'
    assert message["error"] == "invalid payload"
    assert message["attempts"] == 3
