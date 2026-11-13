"""Physical Kafka topics carry the p03. prefix; everything else keeps using the
plain event_type, so only the Kafka adapters may add it."""
import sys
import types

import pytest

from backend.common import messaging
from backend.common.events import TOPICS, dlq_topic, kafka_topic


def test_topics_get_the_p03_prefix_by_default(monkeypatch):
    monkeypatch.delenv("KAFKA_TOPIC_PREFIX", raising=False)
    assert kafka_topic("job.created") == "p03.job.created"
    assert kafka_topic(dlq_topic("job.created")) == "p03.job.created.dlq"
    assert all(kafka_topic(t).startswith("p03.") for t in TOPICS)


def test_prefix_can_be_overridden_or_removed(monkeypatch):
    monkeypatch.setenv("KAFKA_TOPIC_PREFIX", "")
    assert kafka_topic("job.created") == "job.created"
    monkeypatch.setenv("KAFKA_TOPIC_PREFIX", "team9.")
    assert kafka_topic("job.created") == "team9.job.created"


@pytest.fixture
def fake_confluent(monkeypatch):
    calls = {"produce": [], "subscribe": []}

    class Producer:
        def __init__(self, conf):
            pass

        def produce(self, topic, key=None, value=None, on_delivery=None):
            calls["produce"].append(topic)

        def poll(self, timeout):
            pass

        def flush(self, timeout):
            pass

    class Consumer:
        def __init__(self, conf):
            pass

        def subscribe(self, topics):
            calls["subscribe"].append(topics)

    module = types.SimpleNamespace(Producer=Producer, Consumer=Consumer)
    monkeypatch.setitem(sys.modules, "confluent_kafka", module)
    monkeypatch.delenv("KAFKA_TOPIC_PREFIX", raising=False)
    return calls


def test_producer_and_dead_letters_use_prefixed_topics(fake_confluent):
    publisher = messaging.ConfluentPublisher("kafka:9092", flush_timeout=0)
    publisher.send("application.created", "1", "{}")
    publisher.send(dlq_topic("application.created"), None, "{}")
    assert fake_confluent["produce"] == [
        "p03.application.created",
        "p03.application.created.dlq",
    ]


def test_consumer_subscribes_to_the_prefixed_topic(fake_confluent):
    messaging.ConfluentConsumerClient(
        "kafka:9092", group_id="job-index-worker", topic="job.created"
    )
    assert fake_confluent["subscribe"] == [["p03.job.created"]]
