"""CompanyStore / JobStore against an in-memory Mongo (mongomock)."""

from datetime import datetime, timedelta, timezone

import pytest

mongomock = pytest.importorskip("mongomock")

from backend.common.mongo_store import CompanyStore, JobStore, new_id  # noqa: E402


@pytest.fixture()
def stores():
    database = mongomock.MongoClient()["p03_test"]
    companies, jobs = CompanyStore(database), JobStore(database)
    companies.ensure_indexes()
    jobs.ensure_indexes()
    return companies, jobs


def make_company(companies, name="Acme", email="a@example.com", **extra):
    return companies.create(
        email=email, password_hash="hash", name=name, city="San Jose", **extra
    )


def test_company_ids_are_uuid_strings_and_id_replaces__id(stores):
    companies, _ = stores
    company = make_company(companies)
    assert isinstance(company["id"], str) and len(company["id"]) == 36
    assert "_id" not in company
    assert companies.get(company["id"])["name"] == "Acme"


def test_migrated_ids_keep_their_old_integer_as_a_string(stores):
    companies, jobs = stores
    company = make_company(companies, company_id="7")
    job = jobs.create(company["id"], title="T", description="D", city="Fremont", job_id="12")
    assert company["id"] == "7" and job["id"] == "12"
    assert companies.get(7)["id"] == "7"  # integer lookups still work


def test_email_is_unique(stores):
    companies, _ = stores
    make_company(companies)
    with pytest.raises(Exception):
        make_company(companies, name="Other")
    assert companies.get_by_email("a@example.com")["name"] == "Acme"
    assert companies.get_by_email("none@example.com") is None


def test_update_changes_only_the_given_fields(stores):
    companies, _ = stores
    company = make_company(companies)
    updated = companies.update(company["id"], {"name": "New", "description": "x"})
    assert updated["name"] == "New" and updated["city"] == "San Jose"


def test_a_company_only_sees_its_own_jobs(stores):
    companies, jobs = stores
    first = make_company(companies)
    second = make_company(companies, name="Beta", email="b@example.com")
    job = jobs.create(first["id"], title="Intern", description="D", city="Fremont")

    assert jobs.get_for_company(job["id"], first["id"])["title"] == "Intern"
    assert jobs.get_for_company(job["id"], second["id"]) is None
    assert [j["id"] for j in jobs.list_for_company(first["id"])] == [job["id"]]
    assert jobs.list_for_company(second["id"]) == []


def test_jobs_are_listed_newest_first(stores):
    companies, jobs = stores
    company = make_company(companies)
    base = datetime(2030, 1, 15, tzinfo=timezone.utc)
    for index in range(3):
        jobs.create(
            company["id"], title=f"J{index}", description="D", city="Fremont",
            created_at=base + timedelta(days=index),
        )
    assert [j["title"] for j in jobs.list_for_company(company["id"])] == ["J2", "J1", "J0"]


def test_search_matches_title_description_city_and_company_name(stores):
    companies, jobs = stores
    acme = make_company(companies, name="Acme Robotics")
    beta = make_company(companies, name="Beta", email="b@example.com")
    jobs.create(acme["id"], title="Data Intern", description="SQL work", city="San Jose")
    jobs.create(beta["id"], title="Designer", description="Figma and data", city="Fremont")
    jobs.create(beta["id"], title="Cook", description="Kitchen", city="Santa Clara")

    def titles(**kw):
        return sorted(j["title"] for j in jobs.search(**kw))

    assert titles(keyword="data") == ["Data Intern", "Designer"]
    assert titles(city="fremont") == ["Designer"]
    assert titles(keyword="data", city="san jose") == ["Data Intern"]
    ids = companies.ids_with_name_containing("robotics")
    assert titles(keyword="robotics", company_ids=ids) == ["Data Intern"]
    assert titles() == ["Cook", "Data Intern", "Designer"]


def test_search_text_is_not_treated_as_a_regex(stores):
    companies, jobs = stores
    company = make_company(companies)
    jobs.create(company["id"], title="C++ Dev", description="D", city="Fremont")
    jobs.create(company["id"], title="Cook", description="D", city="Fremont")
    assert [j["title"] for j in jobs.search(keyword="C++")] == ["C++ Dev"]
    assert jobs.search(keyword=".*") == []


def test_decimal_salary_is_stored_as_a_number(stores):
    from decimal import Decimal

    companies, jobs = stores
    company = make_company(companies)
    job = jobs.create(
        company["id"], title="T", description="D", city="Fremont", salary=Decimal("85000.50")
    )
    assert jobs.get(job["id"])["salary"] == 85000.5


def test_new_ids_are_unique():
    assert new_id() != new_id()
