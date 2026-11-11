"""Static checks for the Kubernetes manifests in k8s/ (no cluster needed)."""

import json
from pathlib import Path

import pytest

from backend.common.events import TOPICS
from backend.workers.handlers import WORKERS

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
K8S = ROOT / "k8s"
CONTRACT = json.loads((ROOT / "contracts" / "services.json").read_text())
KUSTOMIZATION = yaml.safe_load((K8S / "kustomization.yaml").read_text())


def load_all():
    docs = []
    for name in KUSTOMIZATION["resources"]:
        for doc in yaml.safe_load_all((K8S / name).read_text()):
            if doc:
                docs.append((name, doc))
    return docs


DOCS = load_all()


def of_kind(*kinds):
    return [d for _, d in DOCS if d["kind"] in kinds]


def pod_spec(doc):
    return doc["spec"]["template"]["spec"]


def test_kustomization_lists_every_manifest_file():
    on_disk = {p.name for p in K8S.glob("*.yaml")} - {"kustomization.yaml"}
    assert on_disk == set(KUSTOMIZATION["resources"])
    assert KUSTOMIZATION["namespace"] == "p03"


def test_namespace_and_prefix():
    namespaces = of_kind("Namespace")
    assert [n["metadata"]["name"] for n in namespaces] == ["p03"]
    for _, doc in DOCS:
        name = doc["metadata"]["name"]
        assert name == "p03" or name.startswith("p03-"), name
        assert doc["metadata"].get("namespace", "p03") == "p03"


def test_no_secret_object_or_inline_secret_value():
    assert not of_kind("Secret"), "Secrets are created from .env.compose, never committed"
    for doc in of_kind("Deployment", "StatefulSet", "Job"):
        for c in pod_spec(doc)["containers"]:
            for env in c.get("env", []):
                if any(w in env["name"] for w in ("PASSWORD", "SECRET", "KEY")):
                    assert "valueFrom" in env, f"{doc['metadata']['name']}: {env['name']}"
                    ref = env["valueFrom"]["secretKeyRef"]
                    assert ref["name"] == "p03-secrets"


def test_every_image_has_an_explicit_tag_and_no_latest():
    for doc in of_kind("Deployment", "StatefulSet", "Job"):
        for c in pod_spec(doc)["containers"]:
            assert ":" in c["image"], c["image"]
            assert not c["image"].endswith(":latest"), c["image"]


def test_every_container_has_resource_requests_and_limits():
    for doc in of_kind("Deployment", "StatefulSet", "Job"):
        for c in pod_spec(doc)["containers"]:
            res = c["resources"]
            assert {"cpu", "memory"} <= set(res["requests"]), c["name"]
            assert {"cpu", "memory"} <= set(res["limits"]), c["name"]


def test_services_match_the_contract():
    contract = {
        f"{s['image']}": s["port"]
        for s in CONTRACT["services"]
        if s["name"]
        in {"company", "student", "job", "application", "event", "assistant"}
    }
    deployments = {
        d["metadata"]["name"]: d
        for d in of_kind("Deployment")
        if d["metadata"]["name"] in contract
    }
    services = {s["metadata"]["name"]: s for s in of_kind("Service")}
    assert set(deployments) == set(contract)
    for name, port in contract.items():
        container = pod_spec(deployments[name])["containers"][0]
        assert container["image"] == f"{name}:dev"
        assert container["ports"][0]["containerPort"] == port
        svc_port = services[name]["spec"]["ports"][0]
        assert svc_port["port"] == port and svc_port["targetPort"] == port
        for probe in ("readinessProbe", "livenessProbe"):
            assert container[probe]["httpGet"]["path"] == "/health"
        assert 9030 <= port <= 9039


def test_service_selectors_match_pod_labels():
    pods = {}
    for doc in of_kind("Deployment", "StatefulSet"):
        pods[doc["metadata"]["name"]] = doc["spec"]["template"]["metadata"]["labels"]
        match = doc["spec"]["selector"]["matchLabels"]
        assert match.items() <= doc["spec"]["template"]["metadata"]["labels"].items()
    for svc in of_kind("Service"):
        name = svc["metadata"]["name"]
        assert svc["spec"]["selector"].items() <= pods[name].items(), name


def test_statefulsets_point_at_their_service():
    services = {s["metadata"]["name"] for s in of_kind("Service")}
    for sts in of_kind("StatefulSet"):
        assert sts["spec"]["serviceName"] in services
        assert sts["spec"]["volumeClaimTemplates"], sts["metadata"]["name"]


def test_kafka_service_lets_the_broker_find_itself_while_starting():
    svc = next(s for s in of_kind("Service") if s["metadata"]["name"] == "p03-kafka")
    assert svc["spec"]["clusterIP"] == "None"
    assert svc["spec"]["publishNotReadyAddresses"] is True
    kafka = next(s for s in of_kind("StatefulSet") if s["metadata"]["name"] == "p03-kafka")
    env = {e["name"]: e.get("value") for e in pod_spec(kafka)["containers"][0]["env"]}
    assert env["KAFKA_ADVERTISED_LISTENERS"] == "INTERNAL://p03-kafka:9092"
    assert env["KAFKA_CONTROLLER_QUORUM_VOTERS"] == "1@p03-kafka:9093"


def test_config_points_at_the_in_cluster_services():
    config = next(d for d in of_kind("ConfigMap"))["data"]
    assert config == {
        "KAFKA_BOOTSTRAP": "p03-kafka:9092",
        "MONGO_URL": "mongodb://p03-mongo:27017",
        "MONGO_DB": "p03",
    }
    names = {s["metadata"]["name"] for s in of_kind("Service")}
    assert {"p03-kafka", "p03-mongo", "p03-mysql"} <= names


def test_every_worker_in_the_code_has_a_deployment():
    deployed = {}
    for doc in of_kind("Deployment"):
        env = {e["name"]: e.get("value") for e in pod_spec(doc)["containers"][0].get("env", [])}
        if "WORKER_NAME" in env:
            deployed[env["WORKER_NAME"]] = doc["metadata"]["name"]
    assert set(deployed) == set(WORKERS)
    for worker, name in deployed.items():
        assert name == f"p03-{worker}"


def test_kafka_init_creates_every_topic_and_its_dlq():
    job = next(d for d in of_kind("Job") if d["metadata"]["name"] == "p03-kafka-init")
    script = pod_spec(job)["containers"][0]["args"][0]
    for topic in TOPICS:
        assert topic in script, topic
    assert "$topic.dlq" in script


def test_db_init_runs_schema_then_both_migrations():
    job = next(d for d in of_kind("Job") if d["metadata"]["name"] == "p03-db-init")
    script = pod_spec(job)["containers"][0]["args"][0]
    order = [
        script.index("backend.create_schema"),
        script.index("backend.migrate_application_resumes"),
        script.index("backend.migrate_canonical_schema"),
    ]
    assert order == sorted(order)


def test_scripts_do_not_use_kubernetes_variable_syntax_by_accident():
    """Kubernetes expands $(NAME) in command/args; only DATABASE_URL may use it."""
    for doc in of_kind("Job", "Deployment"):
        for c in pod_spec(doc)["containers"]:
            for part in c.get("command", []) + c.get("args", []):
                assert "$(" not in part, f"{doc['metadata']['name']}: {part[:60]}"


def test_optional_seed_job_is_valid_and_not_in_the_default_deploy():
    seed = yaml.safe_load((K8S / "optional" / "seed-job.yaml").read_text())
    assert seed["kind"] == "Job"
    assert seed["metadata"] == {
        **seed["metadata"],
        "name": "p03-seed",
        "namespace": "p03",
    }
    container = pod_spec(seed)["containers"][0]
    assert container["image"] == "p03-company-service:dev"
    assert container["command"] == ["python", "-m", "backend.seed_final_data"]
    for env in container["env"]:
        if any(w in env["name"] for w in ("PASSWORD", "SECRET", "KEY")):
            assert "valueFrom" in env
    assert "optional" not in " ".join(KUSTOMIZATION["resources"])


def test_company_and_application_share_the_uploads_claim():
    claim = next(
        d for d in of_kind("PersistentVolumeClaim")
        if d["metadata"]["name"] == "p03-uploads"
    )
    assert claim["spec"]["accessModes"] == ["ReadWriteOnce"]
    deployments = {d["metadata"]["name"]: d for d in of_kind("Deployment")}
    for name in ("p03-company-service", "p03-application-service"):
        volumes = pod_spec(deployments[name])["volumes"]
        assert {"name": "uploads", "persistentVolumeClaim": {"claimName": "p03-uploads"}} in volumes


def test_assistant_points_at_ollama_on_the_host():
    deployment = next(
        d for d in of_kind("Deployment")
        if d["metadata"]["name"] == "p03-assistant-service"
    )
    env = {e["name"]: e.get("value") for e in pod_spec(deployment)["containers"][0]["env"]}
    assert "host.docker.internal" in env["OLLAMA_BASE_URL"]
