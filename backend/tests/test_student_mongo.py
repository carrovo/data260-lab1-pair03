"""The student side with PERSISTENCE=mongo (in-memory MongoDB), and the SQL default.

Students, preferences, saved items, sessions and activity logs live in MongoDB;
the API responses and the JWT claims are the same as in SQL mode.
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
from backend.app.models import SavedItem, Student, StudentPreferences  # noqa: E402
from backend.app.routers import company_auth, student_auth  # noqa: E402
from backend.app.routers.company_auth import router as company_auth_router  # noqa: E402
from backend.app.routers.students_search import router as search_router  # noqa: E402
from backend.app.security import decode_access_token  # noqa: E402
from backend.common.mongo_store import (  # noqa: E402
    ActivityLogStore,
    SavedItemStore,
    SessionStore,
    StudentStore,
)
from backend.common.tracing import TraceMiddleware  # noqa: E402
from backend.migrate_student_data import copy_students_to_mongo  # noqa: E402

SIGNUP = {
    "email": "Sam@Example.com",
    "password": "Password123",
    "full_name": "Sam Student",
    "city": "San Jose",
}


def build_client(persistence, monkeypatch):
    database = mongomock.MongoClient()["p03_student_test"]
    StudentStore(database).ensure_indexes()
    SavedItemStore(database).ensure_indexes()
    SessionStore(database).ensure_indexes()
    ActivityLogStore(database).ensure_indexes()
    monkeypatch.setattr(settings, "persistence", persistence)
    monkeypatch.setattr(repos, "get_mongo_database", lambda: database)

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    app = FastAPI()
    app.add_middleware(TraceMiddleware, service="test")
    app.include_router(student_auth.router)
    app.include_router(company_auth_router)
    app.include_router(search_router)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[student_auth.get_db] = override_get_db
    app.dependency_overrides[company_auth.get_db] = override_get_db
    return app, engine, database


@pytest.fixture
def mongo_student(monkeypatch):
    app, engine, database = build_client("mongo", monkeypatch)
    with TestClient(app) as client:
        yield client, engine, database
    engine.dispose()


@pytest.fixture
def sql_student(monkeypatch):
    app, engine, database = build_client("sql", monkeypatch)
    with TestClient(app) as client:
        yield client, engine, database
    engine.dispose()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_signup_stores_student_in_mongo_with_unchanged_response_and_jwt(mongo_student):
    client, engine, database = mongo_student
    response = client.post("/auth/signup", json=SIGNUP)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"access_token", "token_type", "student"}
    assert body["token_type"] == "bearer"
    assert set(body["student"]) == {"id", "email", "full_name", "city"}
    assert body["student"]["email"] == "sam@example.com"
    assert "password_hash" not in body["student"]
    # JWT claims: subject and role only, as before
    assert decode_access_token(body["access_token"]) == (body["student"]["id"], "student")

    assert database["students"].count_documents({}) == 1
    with Session(engine) as db:
        assert db.query(Student).count() == 0


def test_login_me_duplicate_and_bad_password(mongo_student):
    client, _, _ = mongo_student
    client.post("/auth/signup", json=SIGNUP)
    assert client.post("/auth/signup", json=SIGNUP).status_code == 409

    login = client.post("/auth/login", json={"email": "sam@example.com", "password": "Password123"})
    assert login.status_code == 200
    me = client.get("/auth/me", headers=auth(login.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["full_name"] == "Sam Student"

    bad = client.post("/auth/login", json={"email": "sam@example.com", "password": "wrong-password"})
    assert bad.status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_sessions_expire_by_index_and_logout_revokes_the_token(mongo_student):
    client, _, database = mongo_student
    token = client.post("/auth/signup", json=SIGNUP).json()["access_token"]

    sessions = list(database["sessions"].find())
    assert len(sessions) == 1
    assert sessions[0]["_id"] == SessionStore.token_id(token)  # a hash, not the token
    assert token not in str(sessions[0])
    assert sessions[0]["revoked"] is False
    assert any(
        index.get("expireAfterSeconds") == 0
        for index in database["sessions"].index_information().values()
    )

    assert client.get("/auth/me", headers=auth(token)).status_code == 200
    assert client.post("/auth/logout", headers=auth(token)).status_code == 204
    assert client.get("/auth/me", headers=auth(token)).status_code == 401

    # signing in again issues a fresh, usable token
    again = client.post("/auth/login", json={"email": "sam@example.com", "password": "Password123"})
    assert client.get("/auth/me", headers=auth(again.json()["access_token"])).status_code == 200


def test_activity_log_records_sign_in_and_sign_out(mongo_student):
    client, _, database = mongo_student
    signup = client.post("/auth/signup", json=SIGNUP).json()
    student_id = signup["student"]["id"]
    login = client.post("/auth/login", json={"email": "sam@example.com", "password": "Password123"})
    client.post("/auth/logout", headers=auth(login.json()["access_token"]))

    actions = [row["action"] for row in database["activity_logs"].find().sort("_id", 1)]
    assert actions == ["signup", "login", "logout"]
    recent = ActivityLogStore(database).list_for_student(student_id)
    assert [row.action for row in recent] == ["logout", "login", "signup"]


def test_company_student_search_reads_mongo(mongo_student):
    client, _, database = mongo_student
    store = StudentStore(database)
    store.create(email="a@example.com", password_hash="x", full_name="Ada Lovelace",
                 city="San Jose", college_name="SJSU", skills="Python, SQL")
    store.create(email="b@example.com", password_hash="x", full_name="Bo Chen",
                 city="Fremont", college_name="Stanford", skills="Java")
    company = client.post(
        "/api/companies/auth/signup",
        json={"email": "c@example.com", "password": "Password123", "name": "Co", "city": "SJ"},
    ).json()
    headers = auth(company["access_token"])

    everyone = client.get("/api/companies/students", headers=headers)
    assert [s["full_name"] for s in everyone.json()] == ["Ada Lovelace", "Bo Chen"]
    by_skill = client.get("/api/companies/students?skill=sql", headers=headers)
    assert [s["full_name"] for s in by_skill.json()] == ["Ada Lovelace"]
    both = client.get("/api/companies/students?college=stan&city=fremont", headers=headers)
    assert [s["full_name"] for s in both.json()] == ["Bo Chen"]
    profile = client.get("/api/companies/students/1/profile", headers=headers)
    assert profile.json()["college_name"] == "SJSU"
    assert client.get("/api/companies/students/99/profile", headers=headers).status_code == 404


def test_saved_items_are_unique_per_student_and_target(mongo_student):
    _, _, database = mongo_student
    store = SavedItemStore(database)
    first = store.create(1, "job", 5)
    assert (first.job_id, first.event_id) == (5, None)
    assert store.create(1, "event", 5).event_id == 5  # same number, other type: allowed
    with pytest.raises(Exception) as error:
        store.create(1, "job", 5)
    assert type(error.value).__name__ == "DuplicateKeyError"
    assert [item.item_type for item in store.list_for_student(1)] == ["event", "job"]


def test_copy_students_to_mongo_keeps_ids_and_is_repeatable(mongo_student):
    _, engine, database = mongo_student
    with Session(engine) as db:
        student = Student(email="m@example.com", password_hash="h", full_name="Mia", city="SJ")
        db.add(student)
        db.commit()
        student_id = student.id
        db.add(StudentPreferences(student_id=student_id, job_preferences={"city": "SJ"}))
        db.add(SavedItem(student_id=student_id, item_type="job", job_id=7))
        db.commit()

        first = copy_students_to_mongo(db, database)
        second = copy_students_to_mongo(db, database)

    assert first == second == {"students": 1, "student_preferences": 1, "saved_items": 1}
    assert database["students"].find_one()["_id"] == student_id
    assert database["student_preferences"].find_one()["job_preferences"] == {"city": "SJ"}
    assert SavedItemStore(database).get(student_id, "job", 7) is not None
    # a student created afterwards gets an id above the copied ones
    assert StudentStore(database).create(
        email="n@example.com", password_hash="h", full_name="N", city="SJ"
    ).id > student_id


def test_sql_default_keeps_students_in_mysql_and_logout_is_a_noop(sql_student):
    client, engine, database = sql_student
    token = client.post("/auth/signup", json=SIGNUP).json()["access_token"]

    with Session(engine) as db:
        assert db.query(Student).count() == 1
    assert database["students"].count_documents({}) == 0
    assert database["sessions"].count_documents({}) == 0
    assert database["activity_logs"].count_documents({}) == 0

    assert client.post("/auth/logout", headers=auth(token)).status_code == 204
    assert client.get("/auth/me", headers=auth(token)).status_code == 200  # stateless JWT
