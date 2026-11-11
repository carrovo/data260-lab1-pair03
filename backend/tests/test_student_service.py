from fastapi.testclient import TestClient

from backend.services.student.main import app


client = TestClient(app)


def test_student_service_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "student",
        "pair": "03",
    }


def test_student_service_exposes_only_student_routes():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = set(response.json()["paths"])

    assert paths == {
        "/",
        "/health",
        "/auth/signup",
        "/auth/login",
        "/auth/me",
    }
