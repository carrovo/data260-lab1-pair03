import json
from pathlib import Path

import pytest

from backend.common.events import TOPICS

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / "docker-compose.yml").read_text()
COMPOSE = yaml.safe_load(TEXT)
CONTRACT = json.loads((ROOT / "contracts" / "services.json").read_text())


def test_every_resource_carries_the_p03_prefix():
    assert COMPOSE["name"] == "p03"
    for name, service in COMPOSE["services"].items():
        assert name.startswith("p03-"), name
        if "container_name" in service:
            assert service["container_name"].startswith("p03-")
    assert all(v.startswith("p03-") for v in COMPOSE["volumes"])
    assert COMPOSE["networks"]["p03-net"]["name"].startswith("p03-")


def test_host_ports_stay_in_the_pair_block_and_match_the_contract():
    contract_ports = {s["name"]: s["port"] for s in CONTRACT["services"]}
    for name, service in COMPOSE["services"].items():
        for mapping in service.get("ports", []):
            host, container = str(mapping).split(":")
            assert 9030 <= int(host) <= 9039, (name, mapping)
    for short in (
        "company", "student", "job", "application", "event", "assistant"
    ):
        service = COMPOSE["services"][f"p03-{short}-service"]
        assert service["ports"] == [
            f"{contract_ports[short]}:{contract_ports[short]}"
        ]
    assert COMPOSE["services"]["p03-kafka"]["ports"] == [
        f"{contract_ports['kafka']}:{contract_ports['kafka']}"
    ]
    assert COMPOSE["services"]["p03-mongo"]["ports"] == [
        f"{contract_ports['mongo']}:27017"
    ]


def test_every_topic_and_its_dead_letter_topic_is_created():
    for topic in TOPICS:
        assert topic in TEXT
    assert "$$topic.dlq" in TEXT


def test_no_secret_value_is_written_into_the_file():
    for key in ("MYSQL_ROOT_PASSWORD", "MYSQL_PASSWORD", "JWT_SECRET_KEY"):
        for line in TEXT.splitlines():
            if line.strip().startswith(f"{key}:"):
                assert "${" in line, line


def test_every_worker_in_the_code_has_a_service():
    from backend.workers.handlers import WORKERS

    names = {
        service["environment"]["WORKER_NAME"]
        for service in COMPOSE["services"].values()
        if "WORKER_NAME" in service.get("environment", {})
    }
    assert names == set(WORKERS)


def test_every_service_build_points_at_an_existing_dockerfile():
    for name, service in COMPOSE["services"].items():
        build = service.get("build")
        if not build:
            continue
        dockerfile = ROOT / "backend" / build["dockerfile"]
        assert dockerfile.exists(), (name, dockerfile)


def test_env_example_contains_only_placeholders():
    """The committed template must never hold real passwords or keys."""
    template = (ROOT / ".env.compose.example").read_text()
    values = {
        line.split("=", 1)[0]: line.split("=", 1)[1].strip()
        for line in template.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    assert set(values) == {
        "MYSQL_ROOT_PASSWORD",
        "MYSQL_PASSWORD",
        "JWT_SECRET_KEY",
    }
    for key, value in values.items():
        assert value.startswith("change-me"), (
            f"{key} in .env.compose.example is not a placeholder; "
            "put real values in .env.compose (which Git ignores)"
        )


def test_application_and_company_share_the_uploads_volume():
    for name in ("p03-company-service", "p03-application-service"):
        volumes = COMPOSE["services"][name]["volumes"]
        assert "p03-uploads:/app/backend/uploads" in volumes


def test_assistant_can_reach_ollama_on_the_host():
    env = COMPOSE["services"]["p03-assistant-service"]["environment"]
    assert "OLLAMA_BASE_URL" in env
    assert "host.docker.internal" in env["OLLAMA_BASE_URL"]


def test_persistence_defaults_to_sql_and_mongo_uses_the_plan_database():
    env = COMPOSE["x-service-env"]
    assert env["PERSISTENCE"] == "${PERSISTENCE:-sql}"
    assert env["MONGO_DB"] == COMPOSE["x-worker-env"]["MONGO_DB"] == "p03_handshake"
    assert "backend.migrate_mongo_persistence" in COMPOSE["services"]["p03-db-init"]["command"]


def test_service_images_have_the_client_libraries_their_code_imports():
    """The unit tests use fakes, so a missing library only shows when the container runs."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "services"

    def packages(service):
        lines = (root / service / "requirements.txt").read_text().splitlines()
        return {line.split(">")[0].split("[")[0].strip().lower() for line in lines if line.strip()}

    # these services call publish_safely (Kafka producer)
    for service in ("company", "job", "application", "event"):
        assert "confluent-kafka" in packages(service), service
    # these read companies/jobs/events through the repositories (PERSISTENCE=mongo)
    for service in ("company", "job", "application", "event", "assistant"):
        assert "pymongo" in packages(service), service
