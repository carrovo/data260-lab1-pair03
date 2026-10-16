from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models import Company, Job
from backend.app.routers import jobs as jobs_router


@pytest.fixture
def job_test_context(auth_test_context):
    client, engine = auth_test_context

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[jobs_router.get_db] = override_get_db

    try:
        yield client, engine
    finally:
        app.dependency_overrides.pop(jobs_router.get_db, None)


def seed_job_catalog(engine):
    base_time = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)

    with Session(engine) as db:
        talentbridge = Company(
            email="jobs.talentbridge@example.com",
            password_hash="private-talentbridge-password-hash",
            name="TalentBridge Labs",
            city="San Jose",
            created_at=base_time,
        )
        greenwave = Company(
            email="jobs.greenwave@example.com",
            password_hash="private-greenwave-password-hash",
            name="GreenWave Analytics",
            city="Santa Clara",
            created_at=base_time,
        )
        fremont_robotics = Company(
            email="jobs.robotics@example.com",
            password_hash="private-robotics-password-hash",
            name="Fremont Robotics",
            city="Fremont",
            created_at=base_time,
        )
        db.add_all([talentbridge, greenwave, fremont_robotics])
        db.flush()

        data_analyst = Job(
            company_id=talentbridge.id,
            title="Data Analyst Intern",
            description="Build dashboards and analyze customer data.",
            city="San Jose",
            created_at=base_time,
        )
        backend_engineer = Job(
            company_id=talentbridge.id,
            title="Backend Engineering Intern",
            description="Build Python APIs for internal career tools.",
            city="San Jose",
            created_at=base_time,
        )
        sustainability_researcher = Job(
            company_id=greenwave.id,
            title="Sustainability Research Assistant",
            description="Analyze climate metrics and prepare reports.",
            city="Santa Clara",
            created_at=base_time + timedelta(days=1),
        )
        robotics_technician = Job(
            company_id=fremont_robotics.id,
            title="Robotics Technician",
            description="Maintain field robots and validate sensor data.",
            city="Fremont",
            created_at=base_time + timedelta(days=2),
        )
        db.add_all(
            [
                data_analyst,
                backend_engineer,
                sustainability_researcher,
                robotics_technician,
            ]
        )
        db.flush()

        job_ids = {
            "data_analyst": data_analyst.id,
            "backend_engineer": backend_engineer.id,
            "sustainability_researcher": sustainability_researcher.id,
            "robotics_technician": robotics_technician.id,
        }
        db.commit()

    return job_ids


def test_job_list_is_public_and_returns_expected_contract(job_test_context):
    client, engine = job_test_context
    job_ids = seed_job_catalog(engine)

    response = client.get("/jobs")

    assert response.status_code == 200
    jobs = response.json()
    assert {job["id"] for job in jobs} == set(job_ids.values())
    assert all(
        set(job) == {
            "id",
            "company_id",
            "title",
            "description",
            "city",
            "created_at",
            "company",
        }
        for job in jobs
    )


@pytest.mark.parametrize(
    ("keyword", "expected_job_key"),
    [
        ("Data Analyst", "data_analyst"),
        ("Python APIs", "backend_engineer"),
        ("GreenWave", "sustainability_researcher"),
    ],
)
def test_job_keyword_searches_title_description_and_company_name(
    job_test_context,
    keyword,
    expected_job_key,
):
    client, engine = job_test_context
    job_ids = seed_job_catalog(engine)

    response = client.get("/jobs", params={"keyword": keyword})

    assert response.status_code == 200
    assert [job["id"] for job in response.json()] == [
        job_ids[expected_job_key]
    ]


def test_job_list_filters_by_city(job_test_context):
    client, engine = job_test_context
    job_ids = seed_job_catalog(engine)

    response = client.get("/jobs", params={"city": "San Jose"})

    assert response.status_code == 200
    assert [job["id"] for job in response.json()] == [
        job_ids["backend_engineer"],
        job_ids["data_analyst"],
    ]


def test_job_list_combines_keyword_and_city_filters(job_test_context):
    client, engine = job_test_context
    job_ids = seed_job_catalog(engine)

    response = client.get(
        "/jobs",
        params={"keyword": "intern", "city": "San Jose"},
    )

    assert response.status_code == 200
    assert [job["id"] for job in response.json()] == [
        job_ids["backend_engineer"],
        job_ids["data_analyst"],
    ]


def test_job_filters_are_case_insensitive(job_test_context):
    client, engine = job_test_context
    job_ids = seed_job_catalog(engine)

    response = client.get(
        "/jobs",
        params={"keyword": "rObOtIcS", "city": "fReMoNt"},
    )

    assert response.status_code == 200
    assert [job["id"] for job in response.json()] == [
        job_ids["robotics_technician"]
    ]


def test_job_list_has_stable_newest_first_order(job_test_context):
    client, engine = job_test_context
    job_ids = seed_job_catalog(engine)

    response = client.get("/jobs")

    assert response.status_code == 200
    assert [job["id"] for job in response.json()] == [
        job_ids["robotics_technician"],
        job_ids["sustainability_researcher"],
        job_ids["backend_engineer"],
        job_ids["data_analyst"],
    ]


@pytest.mark.parametrize("invalid_limit", [0, 101])
def test_job_list_validates_limit(job_test_context, invalid_limit):
    client, _ = job_test_context

    response = client.get("/jobs", params={"limit": invalid_limit})

    assert response.status_code == 422


def test_job_list_validates_offset(job_test_context):
    client, _ = job_test_context

    response = client.get("/jobs", params={"offset": -1})

    assert response.status_code == 422


def test_job_list_applies_limit_and_offset(job_test_context):
    client, engine = job_test_context
    job_ids = seed_job_catalog(engine)

    first_page = client.get("/jobs", params={"limit": 2, "offset": 0})
    second_page = client.get("/jobs", params={"limit": 2, "offset": 2})

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert [job["id"] for job in first_page.json()] == [
        job_ids["robotics_technician"],
        job_ids["sustainability_researcher"],
    ]
    assert [job["id"] for job in second_page.json()] == [
        job_ids["backend_engineer"],
        job_ids["data_analyst"],
    ]


def test_job_list_returns_empty_list_for_no_matches(job_test_context):
    client, engine = job_test_context
    seed_job_catalog(engine)

    response = client.get(
        "/jobs",
        params={"keyword": "quantum agriculture", "city": "San Jose"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_job_detail_is_public_and_includes_company(job_test_context):
    client, engine = job_test_context
    job_ids = seed_job_catalog(engine)

    response = client.get(f"/jobs/{job_ids['data_analyst']}")

    assert response.status_code == 200
    assert response.json() == {
        "id": job_ids["data_analyst"],
        "company_id": response.json()["company"]["id"],
        "title": "Data Analyst Intern",
        "description": "Build dashboards and analyze customer data.",
        "city": "San Jose",
        "created_at": response.json()["created_at"],
        "company": {
            "id": response.json()["company"]["id"],
            "name": "TalentBridge Labs",
            "city": "San Jose",
        },
    }


def test_jobs_do_not_expose_private_company_fields(job_test_context):
    client, engine = job_test_context
    job_ids = seed_job_catalog(engine)

    list_response = client.get("/jobs")
    detail_response = client.get(f"/jobs/{job_ids['data_analyst']}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200

    for job in [*list_response.json(), detail_response.json()]:
        assert set(job["company"]) == {"id", "name", "city"}
        assert "email" not in job["company"]
        assert "password_hash" not in job["company"]

    assert "private-" not in list_response.text
    assert "private-" not in detail_response.text


def test_unknown_job_detail_returns_404(job_test_context):
    client, engine = job_test_context
    seed_job_catalog(engine)

    response = client.get("/jobs/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found."}
