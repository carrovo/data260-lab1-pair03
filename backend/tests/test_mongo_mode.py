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
from backend.app.models import Application, Company, Event, Job, Student  # noqa: E402
from backend.app.routers import company_auth, events as public_events, jobs as public_jobs  # noqa: E402
from backend.app.routers.company_events import router as company_events_router  # noqa: E402
from backend.app.routers.events import router as public_events_router  # noqa: E402
from backend.app.routers.company_auth import router as auth_router  # noqa: E402
from backend.app.routers.company_jobs import router as company_jobs_router  # noqa: E402
from backend.app.routers.company_profile import router as profile_router  # noqa: E402
from backend.app.routers.jobs import router as public_jobs_router  # noqa: E402
from backend.common.mongo_store import CompanyStore, EventStore, JobStore  # noqa: E402
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
    EventStore(database).ensure_indexes()
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
    for router in (
        auth_router,
        profile_router,
        company_jobs_router,
        public_jobs_router,
        company_events_router,
        public_events_router,
    ):
        app.include_router(router)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[company_auth.get_db] = override_get_db
    app.dependency_overrides[public_jobs.get_db] = override_get_db
    app.dependency_overrides[public_events.get_db] = override_get_db

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


# ---------------------------------------------------------------- seed data


def test_seed_loads_companies_and_jobs_into_mongo_and_is_idempotent(monkeypatch):
    from io import StringIO

    from backend.seed_final_data import (
        COMPANY_COUNT,
        DEFAULT_BASE_DATE,
        EVENT_COUNT,
        JOB_COUNT,
        DEMO_COMPANY_EMAIL,
        DEMO_MATCH_JOB_TITLE,
        seed_final_data,
    )

    database = mongomock.MongoClient()["p03_seed"]
    monkeypatch.setattr(settings, "persistence", "mongo")
    monkeypatch.setattr(repos, "get_mongo_database", lambda: database)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def run():
        with Session(engine) as session:
            return seed_final_data(
                session, base_date=DEFAULT_BASE_DATE, output=StringIO()
            )

    summary = run()
    assert (summary.companies, summary.jobs) == (COMPANY_COUNT, JOB_COUNT)
    assert database["companies"].count_documents({}) == COMPANY_COUNT
    assert database["jobs"].count_documents({}) == JOB_COUNT
    assert database["events"].count_documents({}) == EVENT_COUNT
    with Session(engine) as db:
        assert db.query(Company).count() == 0
        assert db.query(Event).count() == 0
        assert db.query(Job).count() == 0
        assert db.query(Application).count() == summary.applications

    demo = database["companies"].find_one({"email": DEMO_COMPANY_EMAIL})
    assert demo["_id"] == 1
    assert database["jobs"].find_one({"title": DEMO_MATCH_JOB_TITLE})["company_id"] == 1

    run()  # a second run changes nothing
    assert database["events"].count_documents({}) == EVENT_COUNT
    assert database["companies"].count_documents({}) == COMPANY_COUNT
    assert database["jobs"].count_documents({}) == JOB_COUNT

    # the seeded demo company can log in through the Mongo-backed router
    app = FastAPI()
    app.include_router(auth_router)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[company_auth.get_db] = override_get_db
    from backend.seed_final_data import DEMO_PASSWORD

    with TestClient(app) as client:
        login = client.post(
            "/api/companies/auth/login",
            json={"email": DEMO_COMPANY_EMAIL, "password": DEMO_PASSWORD},
        )
        assert login.status_code == 200
        assert login.json()["company"]["id"] == 1
    engine.dispose()


# ------------------------------------------------------- MySQL FK migration


def test_foreign_keys_into_companies_and_jobs_are_found():
    from sqlalchemy import inspect

    from backend.migrate_mongo_persistence import drop_foreign_keys, foreign_keys_to

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    found = {(table, referred) for table, _name, referred in foreign_keys_to(inspect(engine))}
    assert ("applications", "jobs") in found
    assert ("saved_items", "jobs") in found
    assert ("events", "companies") in found
    assert ("jobs", "companies") in found
    assert not any(table in {"students"} for table, _ in found)

    # SQLite cannot drop constraints, so the function only reports them
    assert drop_foreign_keys(engine)
    engine.dispose()


def test_mysql_drop_statements_use_the_constraint_names(monkeypatch):
    from backend import migrate_mongo_persistence as migration

    executed = []

    class FakeConnection:
        def execute(self, statement):
            executed.append(str(statement))

    class FakeBegin:
        def __enter__(self):
            return FakeConnection()

        def __exit__(self, *args):
            return False

    class FakeEngine:
        dialect = type("D", (), {"name": "mysql"})()

        def begin(self):
            return FakeBegin()

    monkeypatch.setattr(
        migration, "inspect", lambda engine: object()
    )
    monkeypatch.setattr(
        migration,
        "foreign_keys_to",
        lambda inspector, tables=migration.MONGO_OWNED_TABLES: [
            ("applications", "applications_ibfk_2", "jobs"),
            ("events", "events_ibfk_1", "companies"),
        ],
    )

    migration.drop_foreign_keys(FakeEngine())

    assert executed == [
        "ALTER TABLE `applications` DROP FOREIGN KEY `applications_ibfk_2`",
        "ALTER TABLE `events` DROP FOREIGN KEY `events_ibfk_1`",
    ]


# ------------------------------------------------ applicants (SQL + Mongo)


def test_company_applicant_flow_with_jobs_in_mongo(mongo_context, monkeypatch):
    from backend.app.routers import company_applications
    from backend.app.routers.company_applications import (
        router as company_applications_router,
    )

    client, engine, _ = mongo_context
    client.app.include_router(company_applications_router)
    sent = []
    monkeypatch.setattr(
        company_applications, "publish_safely", lambda *a, **k: sent.append((a, k))
    )

    owner = headers(client)
    other = headers(client, email="other@example.com", name="Other Co")
    client.post("/api/companies/jobs", json=JOB, headers=owner)  # job 1 (Mongo)

    with Session(engine) as db:
        student = Student(
            email="s@example.com", password_hash="x", full_name="Sam Student",
            city="San Jose", major="Data Science",
        )
        db.add(student)
        db.commit()
        application = Application(student_id=student.id, job_id=1)
        db.add(application)
        db.commit()
        application_id = application.id

    listed = client.get("/api/companies/jobs/1/applicants", headers=owner)
    assert listed.status_code == 200
    assert [a["student_name"] for a in listed.json()] == ["Sam Student"]

    assert client.get("/api/companies/jobs/1/applicants", headers=other).status_code == 403
    assert client.get("/api/companies/jobs/99/applicants", headers=owner).status_code == 404

    changed = client.put(
        f"/api/companies/applications/{application_id}/status",
        json={"status": "Reviewed"},
        headers=owner,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "Reviewed"
    (args, _kwargs), = sent
    assert args[0] == "application.status_changed"
    assert args[1]["job_id"] == "1"

    blocked = client.put(
        f"/api/companies/applications/{application_id}/status",
        json={"status": "Declined"},
        headers=other,
    )
    assert blocked.status_code == 403


def _event_payload(**overrides):
    from datetime import datetime, timedelta, timezone

    start = datetime.now(timezone.utc) + timedelta(days=10)
    base = {
        "title": "Data Career Fair",
        "description": "Meet recruiters",
        "city": "San Jose",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=3)).isoformat(),
    }
    return {**base, **overrides}


def test_event_crud_and_public_listing_in_mongo(mongo_context):
    client, engine, database = mongo_context
    token = signup(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/companies/events", json=_event_payload(), headers=headers)
    assert created.status_code == 201
    event = created.json()
    assert event["company"]["name"] == COMPANY["name"]
    assert database["events"].count_documents({}) == 1

    assert [e["id"] for e in client.get("/api/companies/events", headers=headers).json()] == [event["id"]]
    assert client.get(f"/api/companies/events/{event['id']}", headers=headers).status_code == 200

    updated = client.put(
        f"/api/companies/events/{event['id']}", json={"title": "Renamed"}, headers=headers
    )
    assert updated.status_code == 200 and updated.json()["title"] == "Renamed"

    bad = client.put(
        f"/api/companies/events/{event['id']}",
        json={"ends_at": "2000-01-01T00:00:00+00:00"},
        headers=headers,
    )
    assert bad.status_code == 422

    assert [e["title"] for e in client.get("/events", params={"keyword": "renam"}).json()] == ["Renamed"]
    assert client.get("/events", params={"keyword": "zzz"}).json() == []
    assert client.get(f"/events/{event['id']}").json()["company"]["name"] == COMPANY["name"]
    assert client.get("/events/999").status_code == 404

    assert client.delete(f"/api/companies/events/{event['id']}", headers=headers).status_code == 204
    assert database["events"].count_documents({}) == 0


def test_event_ownership_and_registration_guard_in_mongo(mongo_context):
    from backend.app.models import Registration

    client, engine, database = mongo_context
    owner = {"Authorization": "Bearer " + signup(client).json()["access_token"]}
    other = {
        "Authorization": "Bearer "
        + signup(client, email="other@example.com", name="Other Co").json()["access_token"]
    }
    event = client.post("/api/companies/events", json=_event_payload(), headers=owner).json()

    assert client.get(f"/api/companies/events/{event['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/companies/events/{event['id']}", headers=other).status_code == 404

    with Session(engine) as db:
        student = Student(
            email="s@example.com", password_hash="x", full_name="S", city="San Jose"
        )
        db.add(student)
        db.commit()
        db.add(Registration(student_id=student.id, event_id=event["id"]))
        db.commit()

    assert client.delete(f"/api/companies/events/{event['id']}", headers=owner).status_code == 409
    registrants = client.get(f"/api/companies/events/{event['id']}/registrants", headers=owner)
    assert registrants.status_code == 200
    assert [r["email"] for r in registrants.json()] == ["s@example.com"]
