"""MongoDB stores for the company-owned collections (companies, jobs).

Documents use string ids. Records migrated from MySQL keep their old integer
id as a string ("7"); new records get a UUID string. Routers talk to these
classes, never to pymongo directly, so tests can pass a mongomock database.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

DEFAULT_DB = "p03_handshake"


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_database() -> Any:
    """The real database, from MONGO_URL / MONGO_DB (imported lazily)."""
    from pymongo import MongoClient

    client = MongoClient(os.environ["MONGO_URL"])
    return client[os.environ.get("MONGO_DB", DEFAULT_DB)]


def _contains(text: str) -> dict[str, Any]:
    return {"$regex": re.escape(text), "$options": "i"}


def _clean(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Expose Mongo's _id as id, the name the API and the frontend use."""
    if document is None:
        return None
    result = dict(document)
    result["id"] = result.pop("_id")
    return result


def _bson_value(value: Any) -> Any:
    return float(value) if isinstance(value, Decimal) else value


class CompanyStore:
    def __init__(self, database: Any) -> None:
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
        company_id: str | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        document = {
            "_id": company_id or new_id(),
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

    def get(self, company_id: str) -> dict[str, Any] | None:
        return _clean(self._collection.find_one({"_id": str(company_id)}))

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        return _clean(self._collection.find_one({"email": email}))

    def update(self, company_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        self._collection.update_one({"_id": str(company_id)}, {"$set": fields})
        return self.get(company_id)

    def ids_with_name_containing(self, text: str) -> list[str]:
        cursor = self._collection.find({"name": _contains(text)}, {"_id": 1})
        return [row["_id"] for row in cursor]

    def get_many(self, company_ids: list[str]) -> dict[str, dict[str, Any]]:
        cursor = self._collection.find({"_id": {"$in": [str(i) for i in company_ids]}})
        return {row["_id"]: _clean(row) for row in cursor}


class JobStore:
    def __init__(self, database: Any) -> None:
        self._collection = database["jobs"]

    def ensure_indexes(self) -> None:
        self._collection.create_index([("company_id", 1), ("created_at", -1)])
        self._collection.create_index([("created_at", -1)])

    def create(
        self,
        company_id: str,
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
        job_id: str | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        document = {
            "_id": job_id or new_id(),
            "company_id": str(company_id),
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

    def get(self, job_id: str) -> dict[str, Any] | None:
        return _clean(self._collection.find_one({"_id": str(job_id)}))

    def get_for_company(self, job_id: str, company_id: str) -> dict[str, Any] | None:
        """Ownership check: a company only sees its own job."""
        return _clean(
            self._collection.find_one(
                {"_id": str(job_id), "company_id": str(company_id)}
            )
        )

    def list_for_company(self, company_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find({"company_id": str(company_id)}).sort(
            [("created_at", -1), ("_id", -1)]
        )
        return [_clean(row) for row in cursor]

    def search(
        self,
        keyword: str = "",
        city: str = "",
        company_ids: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
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
            .limit(limit)
        )
        return [_clean(row) for row in cursor]
