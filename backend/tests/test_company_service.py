from fastapi.testclient import TestClient

from backend.services.company.main import app


client = TestClient(app)


def test_company_service_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "company",
        "pair": "03",
    }


def test_company_service_exposes_only_company_routes():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = set(response.json()["paths"])

    assert "/health" in paths
    # Student-side and assistant routes belong to other services.
    assert not any(p.startswith("/student") for p in paths)
    assert not any(p.startswith("/assistant") for p in paths)
