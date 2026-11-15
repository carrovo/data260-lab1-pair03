"""MongoDB stores for the company-owned collections (companies, jobs).

Ids are integers, so Mongo records stay compatible with the MySQL tables and
the JWT that refer to them. Records migrated from MySQL keep their old id; new
records take the next number from a counter. Routers talk to these classes
(through backend/app/repos.py), never to pymongo directly, so tests can pass a
mongomock database. Documents come back as objects with attribute access
(company.name), the same way the SQL models behave.
"""

from __future__ import annotations

import hashlib
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


# ---------------------------------------------------------------- student side
# Students, their preferences and saved items, sign-in sessions and the
# activity log. Applications, registrations and resumes stay in MySQL and refer
# to students by id only (the MySQL foreign key to students is dropped in
# mongo mode by backend/migrate_mongo_persistence.py).


class StudentStore:
    def __init__(self, database: Any) -> None:
        self._database = database
        self._collection = database["students"]

    def ensure_indexes(self) -> None:
        self._collection.create_index("email", unique=True)

    def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        city: str,
        college_name: str | None = None,
        major: str | None = None,
        state: str | None = None,
        skills: str | None = None,
        student_id: int | None = None,
        created_at: datetime | None = None,
    ) -> SimpleNamespace:
        document = {
            "_id": int(student_id) if student_id else next_id(self._database, "students"),
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "city": city,
            "college_name": college_name,
            "major": major,
            "state": state,
            "skills": skills,
            "created_at": created_at or utc_now(),
        }
        self._collection.insert_one(document)  # DuplicateKeyError on same email
        return _clean(document)

    def get(self, student_id: int) -> SimpleNamespace | None:
        return _clean(self._collection.find_one({"_id": int(student_id)}))

    def get_by_email(self, email: str) -> SimpleNamespace | None:
        return _clean(self._collection.find_one({"email": email}))

    def get_many(self, student_ids: list[int]) -> dict[int, SimpleNamespace]:
        if not student_ids:
            return {}
        cursor = self._collection.find({"_id": {"$in": [int(i) for i in student_ids]}})
        return {row["_id"]: _clean(row) for row in cursor}

    def search(
        self,
        *,
        name: str | None = None,
        college: str | None = None,
        skill: str | None = None,
        city: str | None = None,
        limit: int = 100,
    ) -> list[SimpleNamespace]:
        """Company-side student search: every given filter must match."""
        conditions: list[dict[str, Any]] = []
        for field, value in (
            ("full_name", name),
            ("college_name", college),
            ("skills", skill),
            ("city", city),
        ):
            if value and value.strip():
                conditions.append({field: _contains(value.strip())})
        query = {"$and": conditions} if conditions else {}
        cursor = self._collection.find(query).sort([("full_name", 1), ("_id", 1)]).limit(limit)
        return [_clean(row) for row in cursor]


class StudentPreferencesStore:
    def __init__(self, database: Any) -> None:
        self._collection = database["student_preferences"]

    def get(self, student_id: int) -> SimpleNamespace | None:
        document = self._collection.find_one({"_id": int(student_id)})
        if document is None:
            return None
        result = _clean(document)
        result.student_id = result.id
        return result

    def upsert(
        self,
        student_id: int,
        *,
        job_preferences: dict[str, Any] | None = None,
        event_preferences: dict[str, Any] | None = None,
    ) -> SimpleNamespace:
        self._collection.update_one(
            {"_id": int(student_id)},
            {
                "$set": {
                    "job_preferences": job_preferences,
                    "event_preferences": event_preferences,
                    "updated_at": utc_now(),
                }
            },
            upsert=True,
        )
        return self.get(student_id)


class SavedItemStore:
    def __init__(self, database: Any) -> None:
        self._database = database
        self._collection = database["saved_items"]

    def ensure_indexes(self) -> None:
        # one saved row per student and target; replaces the MySQL unique keys
        self._collection.create_index(
            [("student_id", 1), ("item_type", 1), ("item_id", 1)], unique=True
        )

    @staticmethod
    def _view(document: dict[str, Any] | None) -> SimpleNamespace | None:
        if document is None:
            return None
        result = _clean(document)
        result.job_id = result.item_id if result.item_type == "job" else None
        result.event_id = result.item_id if result.item_type == "event" else None
        return result

    def get(self, student_id: int, item_type: str, item_id: int) -> SimpleNamespace | None:
        return self._view(
            self._collection.find_one(
                {"student_id": int(student_id), "item_type": item_type, "item_id": int(item_id)}
            )
        )

    def create(self, student_id: int, item_type: str, item_id: int) -> SimpleNamespace:
        document = {
            "_id": next_id(self._database, "saved_items"),
            "student_id": int(student_id),
            "item_type": item_type,
            "item_id": int(item_id),
            "saved_at": utc_now(),
        }
        self._collection.insert_one(document)  # DuplicateKeyError if already saved
        return self._view(document)

    def list_for_student(self, student_id: int) -> list[SimpleNamespace]:
        cursor = self._collection.find({"student_id": int(student_id)}).sort(
            [("saved_at", -1), ("_id", -1)]
        )
        return [self._view(row) for row in cursor]

    def delete(self, student_id: int, item_type: str, item_id: int) -> None:
        self._collection.delete_one(
            {"student_id": int(student_id), "item_type": item_type, "item_id": int(item_id)}
        )


class SessionStore:
    """One document per issued access token (a SHA-256 hash, never the token).

    The JWT stays self-contained and its claims are unchanged; the session
    record adds sign-out: a token whose session was revoked is refused. A
    TTL index removes the record when the token itself would have expired.
    """

    def __init__(self, database: Any) -> None:
        self._collection = database["sessions"]

    def ensure_indexes(self) -> None:
        self._collection.create_index("expires_at", expireAfterSeconds=0)
        self._collection.create_index("student_id")

    @staticmethod
    def token_id(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def start(self, student_id: int, token: str, expires_at: datetime) -> None:
        self._collection.update_one(
            {"_id": self.token_id(token)},
            {
                "$set": {
                    "student_id": int(student_id),
                    "created_at": utc_now(),
                    "expires_at": expires_at,
                    "revoked": False,
                }
            },
            upsert=True,
        )

    def is_revoked(self, token: str) -> bool:
        document = self._collection.find_one({"_id": self.token_id(token)})
        return bool(document and document.get("revoked"))

    def revoke(self, token: str) -> bool:
        result = self._collection.update_one(
            {"_id": self.token_id(token)}, {"$set": {"revoked": True}}
        )
        return result.matched_count > 0

    def list_for_student(self, student_id: int) -> list[SimpleNamespace]:
        cursor = self._collection.find({"student_id": int(student_id)}).sort("created_at", -1)
        return [_clean(row) for row in cursor]


class ActivityLogStore:
    """Append-only record of what a student did (sign up, sign in, save, apply, register)."""

    def __init__(self, database: Any) -> None:
        self._database = database
        self._collection = database["activity_logs"]

    def ensure_indexes(self) -> None:
        self._collection.create_index([("student_id", 1), ("at", -1)])

    def record(
        self, student_id: int, action: str, detail: dict[str, Any] | None = None
    ) -> None:
        self._collection.insert_one(
            {
                "_id": next_id(self._database, "activity_logs"),
                "student_id": int(student_id),
                "action": action,
                "detail": detail or {},
                "at": utc_now(),
            }
        )

    def list_for_student(self, student_id: int, limit: int = 50) -> list[SimpleNamespace]:
        cursor = (
            self._collection.find({"student_id": int(student_id)})
            .sort([("at", -1), ("_id", -1)])
            .limit(limit)
        )
        return [_clean(row) for row in cursor]


# ------------------------------------------------- applications, registrations
# The same collections the Application and Event workers write their event
# projections to. Documents use the workers' conventions (string _id, string
# student_id / job_id / event_id) so a worker upsert for the same id updates the
# API's document instead of creating a second one. Resume metadata (storage key,
# original name, size) is part of the application document; the PDF itself stays
# in the uploads volume.

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _as_datetime(value: Any) -> datetime:
    """Documents written by a worker carry ISO strings; the API writes datetimes."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return EPOCH
    if isinstance(value, datetime):
        return _aware(value)
    return EPOCH


class ApplicationStore:
    def __init__(self, database: Any) -> None:
        self._database = database
        self._collection = database["applications"]

    def ensure_indexes(self) -> None:
        # one application per student and job; replaces the MySQL unique key
        self._collection.create_index([("student_id", 1), ("job_id", 1)], unique=True)

    @staticmethod
    def _view(document: dict[str, Any] | None) -> SimpleNamespace | None:
        if document is None:
            return None
        return SimpleNamespace(
            id=int(document["_id"]),
            student_id=int(document["student_id"]),
            job_id=int(document["job_id"]),
            status=document.get("status", "Pending"),
            applied_at=_as_datetime(document.get("applied_at")),
            resume_storage_key=document.get("resume_storage_key"),
            resume_original_name=document.get("resume_original_name"),
            resume_size_bytes=document.get("resume_size_bytes"),
        )

    def create(
        self,
        *,
        student_id: int,
        job_id: int,
        resume_storage_key: str | None = None,
        resume_original_name: str | None = None,
        resume_size_bytes: int | None = None,
        status: str = "Pending",
        application_id: int | None = None,
        applied_at: datetime | None = None,
    ) -> SimpleNamespace:
        document = {
            "_id": str(int(application_id) if application_id else next_id(self._database, "applications")),
            "student_id": str(int(student_id)),
            "job_id": str(int(job_id)),
            "status": status,
            "applied_at": applied_at or utc_now(),
            # the workers keep created_at/updated_at on the same document
            "created_at": applied_at or utc_now(),
            "resume_storage_key": resume_storage_key,
            "resume_original_name": resume_original_name,
            "resume_size_bytes": resume_size_bytes,
        }
        self._collection.insert_one(document)  # DuplicateKeyError for the same student and job
        return self._view(document)

    def get(self, application_id: int) -> SimpleNamespace | None:
        return self._view(self._collection.find_one({"_id": str(int(application_id))}))

    def exists(self, student_id: int, job_id: int) -> bool:
        return (
            self._collection.count_documents(
                {"student_id": str(int(student_id)), "job_id": str(int(job_id))}, limit=1
            )
            > 0
        )

    @staticmethod
    def _newest_first(views: list[SimpleNamespace]) -> list[SimpleNamespace]:
        return sorted(views, key=lambda v: (v.applied_at, v.id), reverse=True)

    def list_for_student(self, student_id: int, status: str | None = None) -> list[SimpleNamespace]:
        query: dict[str, Any] = {"student_id": str(int(student_id))}
        if status is not None:
            query["status"] = status
        return self._newest_first([self._view(row) for row in self._collection.find(query)])

    def list_for_job(self, job_id: int) -> list[SimpleNamespace]:
        rows = self._collection.find({"job_id": str(int(job_id))})
        return self._newest_first([self._view(row) for row in rows])

    def count_for_job(self, job_id: int) -> int:
        return self._collection.count_documents({"job_id": str(int(job_id))})

    def update(self, application_id: int, fields: dict[str, Any]) -> SimpleNamespace | None:
        self._collection.update_one({"_id": str(int(application_id))}, {"$set": fields})
        return self.get(application_id)


class RegistrationStore:
    def __init__(self, database: Any) -> None:
        self._database = database
        self._collection = database["registrations"]

    def ensure_indexes(self) -> None:
        self._collection.create_index([("student_id", 1), ("event_id", 1)], unique=True)

    @staticmethod
    def _view(document: dict[str, Any] | None) -> SimpleNamespace | None:
        if document is None:
            return None
        return SimpleNamespace(
            id=int(document["_id"]),
            student_id=int(document["student_id"]),
            event_id=int(document["event_id"]),
            registered_at=_as_datetime(document.get("registered_at")),
        )

    def create(
        self,
        *,
        student_id: int,
        event_id: int,
        registration_id: int | None = None,
        registered_at: datetime | None = None,
    ) -> SimpleNamespace:
        document = {
            "_id": str(int(registration_id) if registration_id else next_id(self._database, "registrations")),
            "student_id": str(int(student_id)),
            "event_id": str(int(event_id)),
            "registered_at": registered_at or utc_now(),
        }
        self._collection.insert_one(document)  # DuplicateKeyError for the same student and event
        return self._view(document)

    def exists(self, student_id: int, event_id: int) -> bool:
        return (
            self._collection.count_documents(
                {"student_id": str(int(student_id)), "event_id": str(int(event_id))}, limit=1
            )
            > 0
        )

    def list_for_student(self, student_id: int) -> list[SimpleNamespace]:
        rows = self._collection.find({"student_id": str(int(student_id))})
        return [self._view(row) for row in rows]

    def list_for_event(self, event_id: int) -> list[SimpleNamespace]:
        rows = self._collection.find({"event_id": str(int(event_id))})
        views = [self._view(row) for row in rows]
        return sorted(views, key=lambda v: (v.registered_at, v.id), reverse=True)

    def count_for_event(self, event_id: int) -> int:
        return self._collection.count_documents({"event_id": str(int(event_id))})
