from fastapi.testclient import TestClient

from backend.services.event.main import app


client = TestClient(app)


def test_event_service_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "event",
        "pair": "03",
    }


def test_event_service_exposes_only_event_routes():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = set(response.json()["paths"])

    assert paths == {
        "/",
        "/health",
        "/api/companies/events",
        "/api/companies/events/{event_id}",
        "/api/companies/events/{event_id}/registrants",
        "/events",
        "/events/{event_id}",
        "/events/{event_id}/registrations",
        "/registrations/me",
    }
