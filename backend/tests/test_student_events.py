from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import Company, Event, Registration, Student
from backend.app.routers.events import register_for_event


def signup_student(
    client,
    email="event-student@example.com",
    full_name="Event Student",
):
    response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "Password123",
            "full_name": full_name,
            "city": "San Jose",
        },
    )
    assert response.status_code == 201
    return response.json()


def authorization_headers(auth_response):
    return {
        "Authorization": f"Bearer {auth_response['access_token']}"
    }


def create_event(
    engine,
    *,
    title="Career Fair",
    city="San Jose",
    starts_at=None,
    company_email="event-company@example.com",
    company_name="Event Company",
    with_company=True,
):
    event_start = starts_at or datetime.now(UTC) + timedelta(days=1)

    with Session(engine) as db:
        company_id = None
        if with_company:
            company = Company(
                email=company_email,
                password_hash="not-used-in-event-tests",
                name=company_name,
                city=city,
            )
            db.add(company)
            db.flush()
            company_id = company.id

        event = Event(
            company_id=company_id,
            title=title,
            description=f"Details for {title}.",
            city=city,
            starts_at=event_start,
            ends_at=event_start + timedelta(hours=2),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event.id


def test_event_listing_returns_upcoming_events_in_increasing_date_order(
    auth_test_context,
):
    client, engine = auth_test_context
    now = datetime.now(UTC)
    later_event_id = create_event(
        engine,
        title="Career Fair",
        starts_at=now + timedelta(days=3),
    )
    earlier_event_id = create_event(
        engine,
        title="Resume Workshop",
        starts_at=now + timedelta(days=1),
        company_email="workshop-company@example.com",
        company_name="Workshop Company",
    )
    create_event(
        engine,
        title="Past Event",
        starts_at=now - timedelta(days=2),
        company_email="past-company@example.com",
    )

    response = client.get("/events")

    assert response.status_code == 200
    events = response.json()
    assert [event["id"] for event in events] == [
        earlier_event_id,
        later_event_id,
    ]
    assert events[0]["company"] == {
        "id": events[0]["company_id"],
        "name": "Workshop Company",
        "city": "San Jose",
    }
    assert all(event["starts_at"] for event in events)
    assert all(event["ends_at"] for event in events)


def test_event_listing_searches_by_event_name_and_validates_query(
    auth_test_context,
):
    client, engine = auth_test_context
    create_event(engine, title="Career Networking Night")
    create_event(
        engine,
        title="Technical Interview Workshop",
        company_email="technical-company@example.com",
    )

    search_response = client.get("/events?keyword=networking")
    invalid_response = client.get(f"/events?keyword={'x' * 101}")

    assert search_response.status_code == 200
    assert [event["title"] for event in search_response.json()] == [
        "Career Networking Night"
    ]
    assert invalid_response.status_code == 422


def test_event_detail_includes_optional_company_information(
    auth_test_context,
):
    client, engine = auth_test_context
    event_id = create_event(
        engine,
        title="Student Meetup",
        city="Fremont",
        with_company=False,
    )

    response = client.get(f"/events/{event_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": event_id,
        "company_id": None,
        "title": "Student Meetup",
        "description": "Details for Student Meetup.",
        "city": "Fremont",
        "starts_at": response.json()["starts_at"],
        "ends_at": response.json()["ends_at"],
        "company": None,
    }


def test_missing_event_detail_returns_404(auth_test_context):
    client, _ = auth_test_context

    response = client.get("/events/999999")
    invalid_id_response = client.get("/events/0")

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found."}
    assert invalid_id_response.status_code == 422


def test_authenticated_student_can_register_for_event(auth_test_context):
    client, engine = auth_test_context
    event_id = create_event(engine)
    auth_response = signup_student(client)

    response = client.post(
        f"/events/{event_id}/registrations",
        headers=authorization_headers(auth_response),
    )

    assert response.status_code == 201
    registration = response.json()
    assert registration["student_id"] == auth_response["student"]["id"]
    assert registration["event_id"] == event_id
    assert registration["registered_at"]
    assert registration["event"]["title"] == "Career Fair"
    assert registration["event"]["company"]["name"] == "Event Company"
    assert "student" not in registration
    assert "password_hash" not in str(registration)


def test_registration_is_linked_only_to_authenticated_student(
    auth_test_context,
):
    client, engine = auth_test_context
    event_id = create_event(engine)
    auth_response = signup_student(client)
    student_id = auth_response["student"]["id"]

    response = client.post(
        f"/events/{event_id}/registrations",
        headers=authorization_headers(auth_response),
        json={"student_id": student_id + 1000},
    )

    assert response.status_code == 201

    with Session(engine) as db:
        registration = db.scalar(select(Registration))

    assert registration is not None
    assert registration.student_id == student_id
    assert registration.event_id == event_id


def test_registration_endpoints_require_authentication(auth_test_context):
    client, engine = auth_test_context
    event_id = create_event(engine)

    registration_response = client.post(
        f"/events/{event_id}/registrations"
    )
    history_response = client.get("/registrations/me")

    assert registration_response.status_code == 401
    assert history_response.status_code == 401


def test_registering_for_missing_event_returns_404(auth_test_context):
    client, _ = auth_test_context
    auth_response = signup_student(client)

    response = client.post(
        "/events/999999/registrations",
        headers=authorization_headers(auth_response),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found."}


def test_duplicate_registration_returns_409(auth_test_context):
    client, engine = auth_test_context
    event_id = create_event(engine)
    auth_response = signup_student(client)
    headers = authorization_headers(auth_response)

    first_response = client.post(
        f"/events/{event_id}/registrations",
        headers=headers,
    )
    duplicate_response = client.post(
        f"/events/{event_id}/registrations",
        headers=headers,
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "You are already registered for this event."
    }

    with Session(engine) as db:
        registration_count = db.scalar(
            select(func.count()).select_from(Registration)
        )

    assert registration_count == 1


def test_registration_history_is_ordered_and_private(auth_test_context):
    client, engine = auth_test_context
    now = datetime.now(UTC)
    later_event_id = create_event(
        engine,
        title="Later Event",
        starts_at=now + timedelta(days=4),
    )
    earlier_event_id = create_event(
        engine,
        title="Earlier Event",
        starts_at=now + timedelta(days=2),
        company_email="earlier-company@example.com",
        company_name="Earlier Company",
        city="Santa Clara",
    )
    private_event_id = create_event(
        engine,
        title="Other Student Event",
        starts_at=now + timedelta(days=1),
        company_email="private-event-company@example.com",
    )
    first_student = signup_student(client)
    second_student = signup_student(
        client,
        email="other-event-student@example.com",
        full_name="Other Event Student",
    )
    first_headers = authorization_headers(first_student)
    second_headers = authorization_headers(second_student)

    client.post(
        f"/events/{later_event_id}/registrations",
        headers=first_headers,
    )
    client.post(
        f"/events/{earlier_event_id}/registrations",
        headers=first_headers,
    )
    client.post(
        f"/events/{private_event_id}/registrations",
        headers=second_headers,
    )

    first_history_response = client.get(
        "/registrations/me",
        headers=first_headers,
    )
    second_history_response = client.get(
        "/registrations/me",
        headers=second_headers,
    )

    assert first_history_response.status_code == 200
    first_history = first_history_response.json()
    assert [item["event_id"] for item in first_history] == [
        earlier_event_id,
        later_event_id,
    ]
    assert first_history[0]["event"]["company"] == {
        "id": first_history[0]["event"]["company_id"],
        "name": "Earlier Company",
        "city": "Santa Clara",
    }
    assert [item["event_id"] for item in second_history_response.json()] == [
        private_event_id
    ]


def test_integrity_error_rolls_back_and_returns_registration_conflict(
    auth_test_context,
    monkeypatch,
):
    client, engine = auth_test_context
    event_id = create_event(engine)
    auth_response = signup_student(client)
    student_id = auth_response["student"]["id"]

    with Session(engine) as db:
        student = db.get(Student, student_id)
        original_rollback = db.rollback
        rollback_called = False

        def fail_commit():
            raise IntegrityError(
                "INSERT INTO registrations",
                {},
                Exception("duplicate registration"),
            )

        def track_rollback():
            nonlocal rollback_called
            rollback_called = True
            original_rollback()

        monkeypatch.setattr(db, "commit", fail_commit)
        monkeypatch.setattr(db, "rollback", track_rollback)

        with pytest.raises(HTTPException) as exc_info:
            register_for_event(
                event_id=event_id,
                current_student=student,
                db=db,
            )

    assert rollback_called
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == (
        "You are already registered for this event."
    )
