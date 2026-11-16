"""Provision every logical contract topic and DLQ through the shared prefix helper."""
import os

from backend.common.events import TOPICS, kafka_topic, dlq_topic


def topic_names():
    return [kafka_topic(name) for event in TOPICS for name in (event, dlq_topic(event))]


def main():
    from confluent_kafka import KafkaException, KafkaError
    from confluent_kafka.admin import AdminClient, NewTopic

    admin = AdminClient({"bootstrap.servers": os.environ["KAFKA_BOOTSTRAP"]})
    futures = admin.create_topics([NewTopic(name, 1, 1) for name in topic_names()])
    for name, future in futures.items():
        try:
            future.result(30)
        except KafkaException as exc:
            if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
                raise
        print(name)


if __name__ == "__main__":
    main()
