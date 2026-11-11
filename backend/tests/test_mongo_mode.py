"""The company and job routers with PERSISTENCE=mongo (in-memory MongoDB).

Companies and jobs live in Mongo; applications and students stay in SQL.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

mongomock = pytest.importorskip("mongomock")

from backend.app import repos  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.database import Base  # noqa: E402
from backend.app.models import Application, Company, Job, Student  # noqa: E402
from backend.app.routers import company_auth, jobs as public_jobs  # noqa: E402
from backend.app.routers.company_auth import router as auth_router  # noqa: E402
from backend.app.routers.company_jobs import router as company_jobs_router  # noqa: E402
from backend.app.routers.company_profile import router as profile_router  # noqa: E402
from backend.app.routers.jobs import router as public_jobs_router  # noqa: E402
from backend.common.mongo_store import CompanyStore, JobStore  # noqa: E402
from backend.common.tracing import TraceMiddleware  # noqa: E402

COMPANY = {
    "email": "recruiter@example.com",
    "password": "Password123",
    "name": "Example Analytics",
    "city": "San Jose",
    "description": "Analytics company",
    "contact_info": "recruiting@example.com",
}
JOB = {
    "title": "Data Intern",
    "description": "SQL and dashboards",
    "city": "San Jose",
    "category": "internship",
    "is_remote": False,
    "salary": "30.50",
}


@pytest.fixture
def mongo_context(monkeypatch):
    database = mongomock.MongoClient()["p03_test"]
    CompanyStore(database).ensure_indexes()
    JobStore(database).ensure_indexes()
    monkeypatch.setattr(settings, "persistence", "mongo")
    monkeypatch.setattr(repos, "get_mongo_database", lambda: database)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    app = FastAPI()
    app.add_middleware(TraceMiddleware, service="test")
    for router in (auth_router, profile_router, company_jobs_router, public_jobs_router):
        app.include_router(router)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[company_auth.get_db] = override_get_db
    app.dependency_overrides[public_jobs.get_db] = override_get_db

    with TestClient(app) as client:
        yield client, engine, database

    engine.dispose()


def signup(client, **overrides):
    return client.post("/api/companies/auth/signup", json={**COMPANY, **overrides})


def headers(client, **overrides):
    response = signup(client, **overrides)
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_signup_stores_the_company_in_mongo_not_sql(mongo_context):
    client, engine, database = mongo_context
    response = signup(client)

    assert response.status_code == 201
    body = response.json()
    assert body["company"]["id"] == 1
    assert body["company"]["name"] == "Example Analytics"
    assert "password_hash" not in body["company"]
    assert database["companies"].count_documents({}) == 1
    with Session(engine) as db:
        assert db.query(Company).count() == 0


def test_login_me_and_duplicate_signup(mongo_context):
    client, _, _ = mongo_context
    signup(client)

    assert signup(client).status_code == 409

    login = client.post(
        "/api/companies/auth/login",
        json={"email": COMPANY["email"], "password": COMPANY["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/companies/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == COMPANY["email"]

    bad = client.post(
        "/api/companies/auth/login",
        json={"email": COMPANY["email"], "password": "wrong-password"},
    )
    assert bad.status_code == 401


def test_profile_update(mongo_context):
    client, _, _ = mongo_context
    auth = headers(client)
    response = client.put("/api/companies/me", json={"name": "Renamed"}, headers=auth)
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    assert response.json()["city"] == "San Jose"
    assert client.get("/api/companies/me", headers=auth).json()["name"] == "Renamed"


def test_token_for_a_missing_company_is_rejected(mongo_context):
    client, _, database = mongo_context
    auth = headers(client)
    database["companies"].delete_many({})
    assert client.get("/api/companies/me", headers=auth).status_code == 401


def test_job_crud_in_mongo(mongo_context):
    client, engine, database = mongo_context
    auth = headers(client)

    created = client.post("/api/companies/jobs", json=JOB, headers=auth)
    assert created.status_code == 201
    job = created.json()
    assert job["id"] == 1 and job["company_id"] == 1
    assert job["company"]["name"] == "Example Analytics"
    assert job["category"] == "internship"
    assert float(job["salary"]) == 30.5
    assert database["jobs"].count_documents({}) == 1
    with Session(engine) as db:
        assert db.query(Job).count() == 0

    listed = client.get("/api/companies/jobs", headers=auth).json()
    assert [j["id"] for j in listed] == [1]

    updated = client.put("/api/companies/jobs/1", json={"title": "Senior Intern"}, headers=auth)
    assert updated.json()["title"] == "Senior Intern"
    assert client.get("/api/companies/jobs/1", headers=auth).json()["title"] == "Senior Intern"

    assert client.delete("/api/companies/jobs/1", headers=auth).status_code == 204
    assert client.get("/api/companies/jobs/1", headers=auth).status_code == 404


def test_a_company_cannot_touch_another_companys_job(mongo_context):
    client, _, _ = mongo_context
    owner = headers(client)
    other = headers(client, email="other@example.com", name="Other Co")
    client.post("/api/companies/jobs", json=JOB, headers=owner)

    assert client.get("/api/companies/jobs/1", headers=other).status_code == 404
    assert client.put("/api/companies/jobs/1", json={"title": "x"}, headers=other).status_code == 404
    assert client.delete("/api/companies/jobs/1", headers=other).status_code == 404
    assert client.get("/api/companies/jobs", headers=other).json() == []


def test_a_job_with_applications_cannot_be_deleted(mongo_context):
    client, engine, _ = mongo_context
    auth = headers(client)
    client.post("/api/companies/jobs", json=JOB, headers=auth)
    with Session(engine) as db:
        student = Student(email="s@example.com", password_hash="x", full_name="S", city="San Jose")
        db.add(student)
        db.commit()
        db.add(Application(student_id=student.id, job_id=1))
        db.commit()

    response = client.delete("/api/companies/jobs/1", headers=auth)
    assert response.status_code == 409
    assert client.get("/api/companies/jobs/1", headers=auth).status_code == 200


def test_public_job_list_search_and_detail(mongo_context):
    client, _, _ = mongo_context
    first = headers(client)
    second = headers(client, email="b@example.com", name="Fremont Robotics", city="Fremont")
    client.post("/api/companies/jobs", json=JOB, headers=first)
    client.post(
        "/api/companies/jobs",
        json={**JOB, "title": "Robot Tester", "description": "Hardware", "city": "Fremont"},
        headers=second,
    )

    everything = client.get("/jobs").json()
    assert [j["title"] for j in everything] == ["Robot Tester", "Data Intern"]  # newest first
    assert everything[0]["company"] == {"id": 2, "name": "Fremont Robotics", "city": "Fremont"}

    assert [j["title"] for j in client.get("/jobs", params={"keyword": "dashboards"}).json()] == ["Data Intern"]
    assert [j["title"] for j in client.get("/jobs", params={"keyword": "fremont robotics"}).json()] == ["Robot Tester"]
    assert [j["title"] for j in client.get("/jobs", params={"city": "fremont"}).json()] == ["Robot Tester"]
    assert len(client.get("/jobs", params={"limit": 1}).json()) == 1

    assert client.get("/jobs/1").json()["title"] == "Data Intern"
    assert client.get("/jobs/999").status_code == 404


def test_job_created_event_uses_the_mongo_ids(mongo_context, monkeypatch):
    from backend.app.routers import company_jobs

    sent = []
    monkeypatch.setattr(
        company_jobs, "publish_safely", lambda *a, **k: sent.append((a, k))
    )
    client, _, _ = mongo_context
    auth = headers(client)
    client.post("/api/companies/jobs", json=JOB, headers=auth)

    (args, kwargs), = sent
    assert args[0] == "job.created"
    assert args[1] == {"job_id": "1", "company_id": "1", "title": "Data Intern"}
    assert kwargs["key"] == "1"
