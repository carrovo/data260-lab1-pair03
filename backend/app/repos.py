"""Data access for the company-owned records (companies and jobs).

Routers call make_repos(db) and never touch SQLAlchemy or pymongo for these
records directly. settings.persistence picks the backend:

  "sql"   the SQLAlchemy models in app/models.py (default; the unit tests)
  "mongo" the MongoDB collections in common/mongo_store.py (Compose/Kubernetes)

Both backends return objects with the same attributes (company.name,
job.company.name ...), so response models work unchanged. Applications,
students and saved items stay in MySQL; code that needs a job or company for
them asks these repositories instead of joining tables.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.config import settings
from backend.app.models import Company, Job
from backend.common.mongo_store import CompanyStore, JobStore


_database: Any = None


def get_mongo_database() -> Any:
    """The MongoDB database (one shared client). Tests replace this function."""
    global _database
    if _database is None:
        from pymongo import MongoClient

        url = settings.mongo_url
        if not url:
            raise RuntimeError("MONGO_URL is not set but PERSISTENCE=mongo")
        database = MongoClient(url)[settings.mongo_db]
        CompanyStore(database).ensure_indexes()
        JobStore(database).ensure_indexes()
        _database = database
    return _database


# --------------------------------------------------------------------- SQL


class SqlCompanyRepo:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, **fields: Any) -> Company:
        company = Company(**fields)
        self._db.add(company)
        self._db.commit()
        self._db.refresh(company)
        return company

    def get(self, company_id: int) -> Company | None:
        return self._db.get(Company, int(company_id))

    def get_by_email(self, email: str) -> Company | None:
        return self._db.scalar(select(Company).where(Company.email == email))

    def update(self, company: Company, data: dict[str, Any]) -> Company:
        for field, value in data.items():
            setattr(company, field, value)
        self._db.add(company)
        self._db.commit()
        self._db.refresh(company)
        return company

    def get_many(self, company_ids: list[int]) -> dict[int, Company]:
        if not company_ids:
            return {}
        rows = self._db.scalars(
            select(Company).where(Company.id.in_([int(i) for i in company_ids]))
        ).all()
        return {row.id: row for row in rows}


class SqlJobRepo:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, company_id: int, data: dict[str, Any]) -> Job:
        job = Job(company_id=company_id, **data)
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return self.get(job.id)

    def get(self, job_id: int) -> Job | None:
        return self._db.scalar(
            select(Job).where(Job.id == int(job_id)).options(selectinload(Job.company))
        )

    def get_for_company(self, job_id: int, company_id: int) -> Job | None:
        return self._db.scalar(
            select(Job)
            .where(Job.id == int(job_id), Job.company_id == int(company_id))
            .options(selectinload(Job.company))
        )

    def list_for_company(self, company_id: int) -> list[Job]:
        statement = (
            select(Job)
            .where(Job.company_id == int(company_id))
            .options(selectinload(Job.company))
            .order_by(Job.created_at.desc(), Job.id.desc())
        )
        return list(self._db.scalars(statement).all())

    def search(
        self, keyword: str = "", city: str = "", limit: int = 50, offset: int = 0
    ) -> list[Job]:
        statement = select(Job).join(Job.company).options(selectinload(Job.company))
        if keyword:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    Job.title.ilike(pattern),
                    Job.description.ilike(pattern),
                    Company.name.ilike(pattern),
                )
            )
        if city:
            statement = statement.where(Job.city.ilike(f"%{city}%"))
        statement = (
            statement.order_by(Job.created_at.desc(), Job.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self._db.scalars(statement).all())

    def update(self, job: Job, data: dict[str, Any]) -> Job:
        for field, value in data.items():
            setattr(job, field, value)
        self._db.commit()
        self._db.refresh(job)
        return self.get(job.id)

    def delete(self, job: Job) -> None:
        self._db.delete(job)
        self._db.commit()


# ------------------------------------------------------------------- Mongo


class MongoCompanyRepo:
    def __init__(self, store: CompanyStore) -> None:
        self._store = store

    def create(self, **fields: Any) -> SimpleNamespace:
        return self._store.create(**fields)

    def get(self, company_id: int) -> SimpleNamespace | None:
        return self._store.get(company_id)

    def get_by_email(self, email: str) -> SimpleNamespace | None:
        return self._store.get_by_email(email)

    def update(self, company: SimpleNamespace, data: dict[str, Any]) -> SimpleNamespace:
        return self._store.update(company.id, data)

    def get_many(self, company_ids: list[int]) -> dict[int, SimpleNamespace]:
        return self._store.get_many(company_ids)

    def ids_with_name_containing(self, text: str) -> list[int]:
        return self._store.ids_with_name_containing(text)


class MongoJobRepo:
    def __init__(self, jobs: JobStore, companies: CompanyStore) -> None:
        self._jobs = jobs
        self._companies = companies

    def _with_company(self, job: SimpleNamespace | None) -> SimpleNamespace | None:
        if job is not None:
            job.company = self._companies.get(job.company_id)
        return job

    def _with_companies(self, jobs: list[SimpleNamespace]) -> list[SimpleNamespace]:
        by_id = self._companies.get_many(list({job.company_id for job in jobs}))
        for job in jobs:
            job.company = by_id.get(job.company_id)
        return [job for job in jobs if job.company is not None]

    def create(self, company_id: int, data: dict[str, Any]) -> SimpleNamespace:
        job = self._jobs.create(company_id, **data)
        return self._with_company(job)

    def get(self, job_id: int) -> SimpleNamespace | None:
        return self._with_company(self._jobs.get(job_id))

    def get_for_company(self, job_id: int, company_id: int) -> SimpleNamespace | None:
        return self._with_company(self._jobs.get_for_company(job_id, company_id))

    def list_for_company(self, company_id: int) -> list[SimpleNamespace]:
        return self._with_companies(self._jobs.list_for_company(company_id))

    def search(
        self, keyword: str = "", city: str = "", limit: int = 50, offset: int = 0
    ) -> list[SimpleNamespace]:
        company_ids = self._companies.ids_with_name_containing(keyword) if keyword else None
        jobs = self._jobs.search(
            keyword=keyword, city=city, company_ids=company_ids, limit=limit, offset=offset
        )
        return self._with_companies(jobs)

    def update(self, job: SimpleNamespace, data: dict[str, Any]) -> SimpleNamespace:
        return self._with_company(self._jobs.update(job.id, data))

    def delete(self, job: SimpleNamespace) -> None:
        self._jobs.delete(job.id)


class Repos:
    """The repositories for one request."""

    def __init__(self, companies: Any, jobs: Any) -> None:
        self.companies = companies
        self.jobs = jobs


def make_repos(db: Session) -> Repos:
    if settings.persistence == "mongo":
        database = get_mongo_database()
        company_store, job_store = CompanyStore(database), JobStore(database)
        return Repos(
            MongoCompanyRepo(company_store), MongoJobRepo(job_store, company_store)
        )
    return Repos(SqlCompanyRepo(db), SqlJobRepo(db))
