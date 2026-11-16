from fastapi.testclient import TestClient

from backend.services.application.main import app


client = TestClient(app)


def test_application_service_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "application",
        "pair": "03",
    }


def test_application_service_exposes_only_student_application_routes():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = set(response.json()["paths"])

    assert paths == {
        "/",
        "/health",
        "/jobs/{job_id}/applications",
        "/applications/me",
        "/applications/{application_id}/resume",
    }
