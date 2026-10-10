from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Student
from backend.app.security import verify_password


SIGNUP_DATA = {
    "email": "student@example.com",
    "password": "Password123",
    "full_name": "Test Student",
    "city": "San Jose",
}


def signup(client, **overrides):
    signup_data = {**SIGNUP_DATA, **overrides}
    return client.post("/auth/signup", json=signup_data)


def test_signup_returns_student_and_working_access_token(
    auth_test_context,
):
    client, engine = auth_test_context

    response = signup(client, email="Student@Example.com")

    assert response.status_code == 201
    response_data = response.json()
    assert response_data["token_type"] == "bearer"
    assert response_data["access_token"]
    assert response_data["student"] == {
        "id": response_data["student"]["id"],
        "email": "student@example.com",
        "full_name": "Test Student",
        "city": "San Jose",
    }
    assert "password" not in response_data
    assert "password_hash" not in response_data["student"]

    token = response_data["access_token"]
    profile_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json() == response_data["student"]

    with Session(engine) as db:
        student = db.scalar(
            select(Student).where(Student.email == "student@example.com")
        )

    assert student is not None
    assert student.password_hash != SIGNUP_DATA["password"]
    assert verify_password(SIGNUP_DATA["password"], student.password_hash)


def test_login_accepts_valid_credentials_and_rejects_invalid_ones(
    auth_test_context,
):
    client, _ = auth_test_context
    signup(client)

    valid_response = client.post(
        "/auth/login",
        json={
            "email": SIGNUP_DATA["email"],
            "password": SIGNUP_DATA["password"],
        },
    )
    invalid_response = client.post(
        "/auth/login",
        json={
            "email": SIGNUP_DATA["email"],
            "password": "incorrect-password",
        },
    )

    assert valid_response.status_code == 200
    assert valid_response.json()["student"]["full_name"] == "Test Student"
    assert valid_response.json()["access_token"]
    assert invalid_response.status_code == 401
    assert invalid_response.json() == {
        "detail": "Incorrect email or password."
    }


def test_me_rejects_missing_and_invalid_tokens(auth_test_context):
    client, _ = auth_test_context

    missing_response = client.get("/auth/me")
    invalid_response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert missing_response.status_code == 401
    assert invalid_response.status_code == 401


def test_signup_rejects_duplicate_email(auth_test_context):
    client, _ = auth_test_context

    first_response = signup(client)
    duplicate_response = signup(client, email="STUDENT@example.com")

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "An account with this email already exists."
    }


def test_signup_keeps_minimum_password_requirement(auth_test_context):
    client, _ = auth_test_context

    response = signup(client, password="short7")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "password"]


def test_signup_rejects_password_over_72_utf8_bytes(auth_test_context):
    client, _ = auth_test_context

    response = signup(client, password="🔐" * 19)

    assert response.status_code == 422
    assert "Password must not exceed 72 UTF-8 bytes." in str(
        response.json()["detail"]
    )


def test_login_rejects_password_over_72_utf8_bytes(auth_test_context):
    client, _ = auth_test_context

    response = client.post(
        "/auth/login",
        json={
            "email": SIGNUP_DATA["email"],
            "password": "🔐" * 19,
        },
    )

    assert response.status_code == 422
    assert "Password must not exceed 72 UTF-8 bytes." in str(
        response.json()["detail"]
    )
