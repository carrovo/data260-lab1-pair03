import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret")

from backend.app.config import settings  # noqa: E402
from backend.app.database import Base  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.routers import student_auth  # noqa: E402


@pytest.fixture
def auth_test_context(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "resume_upload_dir", tmp_path / "resumes")
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[student_auth.get_db] = override_get_db

    with TestClient(app) as client:
        yield client, engine

    app.dependency_overrides.clear()
    engine.dispose()
