"""MongoDB stores for the company-owned collections (companies, jobs).

Ids are integers, so Mongo records stay compatible with the MySQL tables and
the JWT that refer to them. Records migrated from MySQL keep their old id; new
records take the next number from a counter. Routers talk to these classes
(through backend/app/repos.py), never to pymongo directly, so tests can pass a
mongomock database. Documents come back as objects with attribute access
(company.name), the same way the SQL models behave.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

DEFAULT_DB = "p03_handshake"


def next_id(database: Any, name: str) -> int:
    """Next integer id for a collection, from the counters collection."""
    from pymongo import ReturnDocument

    counter = database["counters"].find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(counter["seq"])


def raise_counter_to(database: Any, name: str, value: int) -> None:
    """After loading seed data with fixed ids, make new ids start above them."""
    database["counters"].update_one(
        {"_id": name}, {"$max": {"seq": int(value)}}, upsert=True
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_database() -> Any:
    """The real database, from MONGO_URL / MONGO_DB (imported lazily)."""
    from pymongo import MongoClient

    client = MongoClient(os.environ["MONGO_URL"])
    return client[os.environ.get("MONGO_DB", DEFAULT_DB)]


def _contains(text: str) -> dict[str, Any]:
    return {"$regex": re.escape(text), "$options": "i"}


def _aware(value: Any) -> Any:
    """MongoDB returns naive UTC datetimes; the API works with aware ones."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _clean(document: dict[str, Any] | None) -> SimpleNamespace | None:
    """Expose Mongo's _id as id and allow attribute access."""
    if document is None:
        return None
    result = {key: _aware(value) for key, value in document.items()}
    result["id"] = result.pop("_id")
    return SimpleNamespace(**result)


def _bson_value(value: Any) -> Any:
    return float(value) if isinstance(value, Decimal) else value


class CompanyStore:
    def __init__(self, database: Any) -> None:
        self._database = database
        self._collection = database["companies"]

    def ensure_indexes(self) -> None:
        self._collection.create_index("email", unique=True)

    def create(
        self,
        *,
        email: str,
        password_hash: str,
        name: str,
        city: str,
        description: str | None = None,
        contact_info: str | None = None,
        company_id: int | None = None,
        created_at: datetime | None = None,
    ) -> SimpleNamespace:
        document = {
            "_id": int(company_id) if company_id else next_id(self._database, "companies"),
            "email": email,
            "password_hash": password_hash,
            "name": name,
            "city": city,
            "description": description,
            "contact_info": contact_info,
            "profile_picture_storage_key": None,
            "created_at": created_at or utc_now(),
        }
        self._collection.insert_one(document)  # DuplicateKeyError on same email
        return _clean(document)

    def get(self, company_id: int) -> SimpleNamespace | None:
        return _clean(self._collection.find_one({"_id": int(company_id)}))

    def get_by_email(self, email: str) -> SimpleNamespace | None:
        return _clean(self._collection.find_one({"email": email}))

    def update(self, company_id: int, fields: dict[str, Any]) -> SimpleNamespace | None:
        self._collection.update_one({"_id": int(company_id)}, {"$set": fields})
        return self.get(company_id)

    def ids_with_name_containing(self, text: str) -> list[int]:
        cursor = self._collection.find({"name": _contains(text)}, {"_id": 1})
        return [row["_id"] for row in cursor]

    def get_many(self, company_ids: list[int]) -> dict[int, SimpleNamespace]:
        cursor = self._collection.find({"_id": {"$in": [int(i) for i in company_ids]}})
        return {row["_id"]: _clean(row) for row in cursor}


class JobStore:
    def __init__(self, database: Any) -> None:
        self._database = database
        self._collection = database["jobs"]

    def ensure_indexes(self) -> None:
        self._collection.create_index([("company_id", 1), ("created_at", -1)])
        self._collection.create_index([("created_at", -1)])

    def create(
        self,
        company_id: int,
        *,
        title: str,
        description: str,
        city: str,
        category: str | None = None,
        location: str | None = None,
        is_remote: bool = False,
        salary: Any = None,
        skills: str | None = None,
        deadline: datetime | None = None,
        job_id: int | None = None,
        created_at: datetime | None = None,
    ) -> SimpleNamespace:
        document = {
            "_id": int(job_id) if job_id else next_id(self._database, "jobs"),
            "company_id": int(company_id),
            "title": title,
            "description": description,
            "city": city,
            "category": category,
            "location": location,
            "is_remote": is_remote,
            "salary": _bson_value(salary),
            "skills": skills,
            "deadline": deadline,
            "created_at": created_at or utc_now(),
        }
        self._collection.insert_one(document)
        return _clean(document)

    def get(self, job_id: int) -> SimpleNamespace | None:
        return _clean(self._collection.find_one({"_id": int(job_id)}))

    def get_many(self, job_ids: list[int]) -> dict[int, SimpleNamespace]:
        cursor = self._collection.find({"_id": {"$in": [int(i) for i in job_ids]}})
        return {row["_id"]: _clean(row) for row in cursor}

    def search_advanced(
        self,
        *,
        title: str | None = None,
        company_ids: list[int] | None = None,
        category: str | None = None,
        city: str | None = None,
        is_remote: bool | None = None,
        min_salary: Any = None,
        skills: list[str] | None = None,
        deadline_before: datetime | None = None,
        limit: int = 10,
    ) -> list[SimpleNamespace]:
        """The assistant's job search: every given filter must match."""
        conditions: list[dict[str, Any]] = []
        if title:
            conditions.append({"title": _contains(title)})
        if company_ids is not None:
            conditions.append({"company_id": {"$in": list(company_ids)}})
        if category:
            conditions.append({"category": category})
        if city:
            conditions.append({"city": _contains(city)})
        if is_remote is not None:
            conditions.append({"is_remote": bool(is_remote)})
        if min_salary is not None:
            conditions.append({"salary": {"$gte": float(min_salary)}})
        for skill in skills or []:
            conditions.append({"skills": _contains(skill)})
        if deadline_before is not None:
            conditions.append({"deadline": {"$lte": _aware(deadline_before)}})
        query = {"$and": conditions} if conditions else {}
        cursor = (
            self._collection.find(query)
            .sort([("created_at", -1), ("_id", -1)])
            .limit(limit)
        )
        return [_clean(row) for row in cursor]

    def get_for_company(self, job_id: int, company_id: int) -> SimpleNamespace | None:
        """Ownership check: a company only sees its own job."""
        return _clean(
            self._collection.find_one(
                {"_id": int(job_id), "company_id": int(company_id)}
            )
        )

    def get_by_title(self, title: str) -> SimpleNamespace | None:
        return _clean(self._collection.find_one({"title": title}))

    def update(self, job_id: int, fields: dict[str, Any]) -> SimpleNamespace | None:
        fields = {k: _bson_value(v) for k, v in fields.items()}
        self._collection.update_one({"_id": int(job_id)}, {"$set": fields})
        return self.get(job_id)

    def delete(self, job_id: int) -> None:
        self._collection.delete_one({"_id": int(job_id)})

    def list_for_company(self, company_id: int) -> list[SimpleNamespace]:
        cursor = self._collection.find({"company_id": int(company_id)}).sort(
            [("created_at", -1), ("_id", -1)]
        )
        return [_clean(row) for row in cursor]

    def search(
        self,
        keyword: str = "",
        city: str = "",
        company_ids: list[int] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SimpleNamespace]:
        """Keyword matches title, description or (via company_ids) company name."""
        query: dict[str, Any] = {}
        if keyword:
            conditions: list[dict[str, Any]] = [
                {"title": _contains(keyword)},
                {"description": _contains(keyword)},
            ]
            if company_ids:
                conditions.append({"company_id": {"$in": list(company_ids)}})
            query["$or"] = conditions
        if city:
            query["city"] = _contains(city)
        cursor = (
            self._collection.find(query)
            .sort([("created_at", -1), ("_id", -1)])
            .skip(offset)
            .limit(limit)
        )
        return [_clean(row) for row in cursor]


class EventStore:
    def __init__(self, database: Any) -> None:
        self._database = database
        self._collection = database["events"]

    def ensure_indexes(self) -> None:
        self._collection.create_index([("company_id", 1), ("starts_at", 1)])
        self._collection.create_index([("starts_at", 1)])

    def create(
        self,
        company_id: int | None,
        *,
        title: str,
        description: str,
        city: str,
        starts_at: datetime,
        ends_at: datetime,
        location: str | None = None,
        major: str | None = None,
        eligibility: str | None = None,
        event_id: int | None = None,
    ) -> SimpleNamespace:
        document = {
            "_id": int(event_id) if event_id else next_id(self._database, "events"),
            "company_id": int(company_id) if company_id is not None else None,
            "title": title,
            "description": description,
            "city": city,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "location": location,
            "major": major,
            "eligibility": eligibility,
        }
        self._collection.insert_one(document)
        return _clean(document)

    def get(self, event_id: int) -> SimpleNamespace | None:
        return _clean(self._collection.find_one({"_id": int(event_id)}))

    def get_by_title(self, title: str) -> SimpleNamespace | None:
        return _clean(self._collection.find_one({"title": title}))

    def get_for_company(self, event_id: int, company_id: int) -> SimpleNamespace | None:
        return _clean(
            self._collection.find_one(
                {"_id": int(event_id), "company_id": int(company_id)}
            )
        )

    def get_many(self, event_ids: list[int]) -> dict[int, SimpleNamespace]:
        cursor = self._collection.find({"_id": {"$in": [int(i) for i in event_ids]}})
        return {row["_id"]: _clean(row) for row in cursor}

    def update(self, event_id: int, fields: dict[str, Any]) -> SimpleNamespace | None:
        self._collection.update_one({"_id": int(event_id)}, {"$set": fields})
        return self.get(event_id)

    def delete(self, event_id: int) -> None:
        self._collection.delete_one({"_id": int(event_id)})

    def list_for_company(self, company_id: int) -> list[SimpleNamespace]:
        cursor = self._collection.find({"company_id": int(company_id)}).sort(
            [("starts_at", 1), ("_id", 1)]
        )
        return [_clean(row) for row in cursor]

    def search_advanced(
        self,
        *,
        name: str | None = None,
        city: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        major: str | None = None,
        eligibility: str | None = None,
        limit: int = 10,
    ) -> list[SimpleNamespace]:
        """The assistant's event search: every given filter must match."""
        conditions: list[dict[str, Any]] = []
        if name:
            conditions.append({"title": _contains(name)})
        if city:
            conditions.append({"city": _contains(city)})
        if start is not None:
            conditions.append({"starts_at": {"$gte": _aware(start)}})
        if end is not None:
            conditions.append({"starts_at": {"$lte": _aware(end)}})
        if major:
            conditions.append({"major": _contains(major)})
        if eligibility:
            conditions.append({"eligibility": _contains(eligibility)})
        query = {"$and": conditions} if conditions else {}
        cursor = (
            self._collection.find(query)
            .sort([("starts_at", 1), ("_id", 1)])
            .limit(limit)
        )
        return [_clean(row) for row in cursor]

    def list_upcoming(self, keyword: str = "", now: datetime | None = None) -> list[SimpleNamespace]:
        query: dict[str, Any] = {"starts_at": {"$gte": now or utc_now()}}
        if keyword:
            query["title"] = _contains(keyword)
        cursor = self._collection.find(query).sort([("starts_at", 1), ("_id", 1)])
        return [_clean(row) for row in cursor]
