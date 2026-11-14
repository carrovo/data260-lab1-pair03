"""CompanyStore / JobStore against an in-memory Mongo (mongomock)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

mongomock = pytest.importorskip("mongomock")

from backend.common.mongo_store import (  # noqa: E402
    CompanyStore,
    JobStore,
    next_id,
    raise_counter_to,
)


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


def test_ids_are_sequential_integers_and_id_replaces__id(stores):
    companies, _ = stores
    first = make_company(companies)
    second = make_company(companies, name="Beta", email="b@example.com")
    assert (first.id, second.id) == (1, 2)
    assert not hasattr(first, "_id")
    assert companies.get(first.id).name == "Acme"
    assert companies.get("1").name == "Acme"  # text ids from a URL also work


def test_migrated_records_keep_their_id_and_the_counter_moves_above_them():
    database = mongomock.MongoClient()["p03_test"]
    companies, jobs = CompanyStore(database), JobStore(database)
    company = make_company(companies, company_id=50)
    job = jobs.create(company.id, title="T", description="D", city="Fremont", job_id=300)
    assert (company.id, job.id) == (50, 300)

    raise_counter_to(database, "companies", 50)
    raise_counter_to(database, "jobs", 300)
    assert make_company(companies, email="n@example.com").id == 51
    assert jobs.create(company.id, title="N", description="D", city="X").id == 301


def test_raise_counter_never_lowers_it():
    database = mongomock.MongoClient()["p03_test"]
    raise_counter_to(database, "jobs", 10)
    raise_counter_to(database, "jobs", 3)
    assert next_id(database, "jobs") == 11


def test_email_is_unique(stores):
    companies, _ = stores
    make_company(companies)
    with pytest.raises(Exception):
        make_company(companies, name="Other")
    assert companies.get_by_email("a@example.com").name == "Acme"
    assert companies.get_by_email("none@example.com") is None


def test_update_changes_only_the_given_fields(stores):
    companies, _ = stores
    company = make_company(companies)
    updated = companies.update(company.id, {"name": "New", "description": "x"})
    assert updated.name == "New" and updated.city == "San Jose"


def test_a_company_only_sees_its_own_jobs(stores):
    companies, jobs = stores
    first = make_company(companies)
    second = make_company(companies, name="Beta", email="b@example.com")
    job = jobs.create(first.id, title="Intern", description="D", city="Fremont")

    assert jobs.get_for_company(job.id, first.id).title == "Intern"
    assert jobs.get_for_company(job.id, second.id) is None
    assert [j.id for j in jobs.list_for_company(first.id)] == [job.id]
    assert jobs.list_for_company(second.id) == []


def test_job_update_and_delete(stores):
    companies, jobs = stores
    company = make_company(companies)
    job = jobs.create(company.id, title="Old", description="D", city="Fremont")
    assert jobs.update(job.id, {"title": "New", "salary": Decimal("10.5")}).title == "New"
    assert jobs.get(job.id).salary == 10.5
    jobs.delete(job.id)
    assert jobs.get(job.id) is None


def test_jobs_are_listed_newest_first(stores):
    companies, jobs = stores
    company = make_company(companies)
    base = datetime(2030, 1, 15, tzinfo=timezone.utc)
    for index in range(3):
        jobs.create(
            company.id, title=f"J{index}", description="D", city="Fremont",
            created_at=base + timedelta(days=index),
        )
    assert [j.title for j in jobs.list_for_company(company.id)] == ["J2", "J1", "J0"]


def test_search_matches_title_description_city_and_company_name(stores):
    companies, jobs = stores
    acme = make_company(companies, name="Acme Robotics")
    beta = make_company(companies, name="Beta", email="b@example.com")
    jobs.create(acme.id, title="Data Intern", description="SQL work", city="San Jose")
    jobs.create(beta.id, title="Designer", description="Figma and data", city="Fremont")
    jobs.create(beta.id, title="Cook", description="Kitchen", city="Santa Clara")

    def titles(**kw):
        return sorted(j.title for j in jobs.search(**kw))

    assert titles(keyword="data") == ["Data Intern", "Designer"]
    assert titles(city="fremont") == ["Designer"]
    assert titles(keyword="data", city="san jose") == ["Data Intern"]
    ids = companies.ids_with_name_containing("robotics")
    assert titles(keyword="robotics", company_ids=ids) == ["Data Intern"]
    assert titles() == ["Cook", "Data Intern", "Designer"]


def test_search_paging(stores):
    companies, jobs = stores
    company = make_company(companies)
    for index in range(5):
        jobs.create(company.id, title=f"J{index}", description="D", city="X")
    assert len(jobs.search(limit=2)) == 2
    assert len(jobs.search(limit=10, offset=3)) == 2


def test_search_text_is_not_treated_as_a_regex(stores):
    companies, jobs = stores
    company = make_company(companies)
    jobs.create(company.id, title="C++ Dev", description="D", city="Fremont")
    jobs.create(company.id, title="Cook", description="D", city="Fremont")
    assert [j.title for j in jobs.search(keyword="C++")] == ["C++ Dev"]
    assert jobs.search(keyword=".*") == []


def test_decimal_salary_is_stored_as_a_number(stores):
    companies, jobs = stores
    company = make_company(companies)
    job = jobs.create(
        company.id, title="T", description="D", city="Fremont", salary=Decimal("85000.50")
    )
    assert jobs.get(job.id).salary == 85000.5


def test_event_store_crud_ordering_and_aware_datetimes(stores):
    from datetime import datetime, timedelta, timezone

    from backend.common.mongo_store import EventStore

    companies, _ = stores
    company = make_company(companies)
    events = EventStore(companies._collection.database)
    now = datetime.now(timezone.utc)
    late = events.create(company.id, title="Late", description="D", city="X",
                         starts_at=now + timedelta(days=5), ends_at=now + timedelta(days=5, hours=1))
    early = events.create(company.id, title="Early", description="D", city="X",
                          starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=1))
    past = events.create(company.id, title="Past", description="D", city="X",
                         starts_at=now - timedelta(days=1), ends_at=now)

    assert [e.title for e in events.list_for_company(company.id)] == ["Past", "Early", "Late"]
    assert [e.title for e in events.list_upcoming()] == ["Early", "Late"]
    assert [e.title for e in events.list_upcoming("lat")] == ["Late"]
    assert events.get(early.id).starts_at.tzinfo is not None
    assert events.get_for_company(early.id, company.id + 99) is None
    assert set(events.get_many([early.id, late.id, 999])) == {early.id, late.id}
    assert events.update(past.id, {"title": "Gone"}).title == "Gone"
    events.delete(past.id)
    assert events.get(past.id) is None
