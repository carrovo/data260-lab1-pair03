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

    assert paths == {
        "/",
        "/health",
        "/api/companies/applications/{application_id}/resume",
        "/api/companies/applications/{application_id}/status",
        "/api/companies/auth/login",
        "/api/companies/auth/logout",
        "/api/companies/auth/me",
        "/api/companies/auth/signup",
        "/api/companies/jobs/{job_id}/applicants",
        "/api/companies/me",
        "/api/companies/students",
        "/api/companies/students/{student_id}/profile",
    }
