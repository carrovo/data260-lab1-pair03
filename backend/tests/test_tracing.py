"""Trace id: read or created per request, echoed, logged and put on events."""

import importlib
import json
import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common import outgoing
from backend.common.events import TRACE_HEADER
from backend.common.tracing import (
    TraceMiddleware,
    clean_trace_id,
    get_trace_id,
)

HEX32 = re.compile(r"^[0-9a-f]{32}$")


class FakePublisher:
    def __init__(self):
        self.sent = []

    def send(self, topic, key, value):
        self.sent.append((topic, key, value))


def make_app():
    app = FastAPI()
    app.add_middleware(TraceMiddleware, service="test")

    @app.get("/who")
    def who():
        return {"trace_id": get_trace_id()}

    @app.post("/publish")
    def publish():
        outgoing.publish_safely(
            "job.created", {"job_id": "1", "company_id": "2", "title": "T"}
        )
        return {"trace_id": get_trace_id()}

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    return app


@pytest.fixture(autouse=True)
def _reset_outgoing():
    outgoing.reset()
    yield
    outgoing.reset()


def test_client_trace_id_is_used_and_echoed():
    client = TestClient(make_app())
    response = client.get("/who", headers={TRACE_HEADER: "trace-abc"})
    assert response.json() == {"trace_id": "trace-abc"}
    assert response.headers[TRACE_HEADER] == "trace-abc"


def test_missing_trace_id_is_generated_and_echoed():
    client = TestClient(make_app())
    response = client.get("/who")
    generated = response.json()["trace_id"]
    assert HEX32.match(generated)
    assert response.headers[TRACE_HEADER] == generated


@pytest.mark.parametrize("bad", ["has space", "x" * 65, "semi;colon", "a/b"])
def test_unsafe_trace_id_is_replaced(bad):
    assert HEX32.match(clean_trace_id(bad))
    assert clean_trace_id("ok-1.2_3") == "ok-1.2_3"
    assert HEX32.match(clean_trace_id(None))


def test_each_request_gets_its_own_trace_id():
    client = TestClient(make_app())
    first = client.get("/who").json()["trace_id"]
    second = client.get("/who").json()["trace_id"]
    assert first != second
    assert get_trace_id() is None  # nothing leaks out of a request


def test_published_event_carries_the_request_trace_id():
    publisher = FakePublisher()
    outgoing.set_publisher(publisher)
    client = TestClient(make_app())
    response = client.post("/publish", headers={TRACE_HEADER: "trace-xyz"})
    assert response.headers[TRACE_HEADER] == "trace-xyz"
    topic, _, value = publisher.sent[0]
    assert topic == "job.created"
    assert json.loads(value)["trace_id"] == "trace-xyz"


def test_published_event_uses_the_generated_id_when_none_is_sent():
    publisher = FakePublisher()
    outgoing.set_publisher(publisher)
    client = TestClient(make_app())
    response = client.post("/publish")
    event = json.loads(publisher.sent[0][2])
    assert event["trace_id"] == response.headers[TRACE_HEADER]


def test_access_log_line_contains_the_trace_id(caplog):
    client = TestClient(make_app())
    logger = logging.getLogger("p03.http")
    logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger="p03.http"):
            client.get("/who", headers={TRACE_HEADER: "trace-log"})
    finally:
        logger.removeHandler(caplog.handler)
    lines = [r.getMessage() for r in caplog.records if r.name == "p03.http"]
    assert any(
        "trace_id=trace-log" in line
        and "method=GET" in line
        and "path=/who" in line
        and "status=200" in line
        and "service=test" in line
        for line in lines
    )


def test_failed_request_is_logged_with_status_500(caplog):
    client = TestClient(make_app(), raise_server_exceptions=False)
    logger = logging.getLogger("p03.http")
    logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger="p03.http"):
            response = client.get("/boom", headers={TRACE_HEADER: "trace-500"})
    finally:
        logger.removeHandler(caplog.handler)
    assert response.status_code == 500
    lines = [r.getMessage() for r in caplog.records if r.name == "p03.http"]
    assert any("trace_id=trace-500" in l and "status=500" in l for l in lines)


@pytest.mark.parametrize(
    "module",
    [
        "backend.app.main",
        "backend.services.company.main",
        "backend.services.job.main",
        "backend.services.event.main",
    ],
)
def test_every_service_app_has_tracing(module):
    app = importlib.import_module(module).app
    assert any(m.cls is TraceMiddleware for m in app.user_middleware)
    response = TestClient(app).get("/health", headers={TRACE_HEADER: "t-1"})
    assert response.headers[TRACE_HEADER] == "t-1"
