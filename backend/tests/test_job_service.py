from fastapi.testclient import TestClient

from backend.services.job.main import app


client = TestClient(app)


def test_job_service_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "job",
        "pair": "03",
    }


def test_job_service_exposes_only_job_routes():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = set(response.json()["paths"])

    assert paths == {
        "/",
        "/health",
        "/api/companies/jobs",
        "/api/companies/jobs/{job_id}",
        "/jobs",
        "/jobs/{job_id}",
    }
