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
    for short in ("company", "job", "event", "student"):
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


def test_every_service_build_points_at_an_existing_dockerfile_or_profile():
    for name, service in COMPOSE["services"].items():
        build = service.get("build")
        if not build:
            continue
        dockerfile = ROOT / "backend" / build["dockerfile"]
        if "full" in service.get("profiles", []):
            continue  # student Dockerfile arrives with the merge
        assert dockerfile.exists(), (name, dockerfile)
