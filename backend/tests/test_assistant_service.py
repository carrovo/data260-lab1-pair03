from fastapi.testclient import TestClient

from backend.services.assistant.main import app


client = TestClient(app)


def test_assistant_service_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "assistant",
        "pair": "03",
    }


def test_assistant_service_exposes_only_student_assistant_routes():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = set(response.json()["paths"])

    assert paths == {
        "/",
        "/health",
        "/assistant/chat",
    }
