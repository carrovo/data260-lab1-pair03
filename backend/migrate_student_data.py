"""Copy the student-side MySQL rows into MongoDB (PERSISTENCE=mongo).

Students, their preferences, saved items, applications (with their resume
metadata) and registrations live in MongoDB in that mode. This loads whatever
is in the matching MySQL tables into the collections, keeping every id.
Applications and registrations get the string ids and string foreign keys the
Kafka workers use, so a worker upsert updates the same document. Safe to rerun: existing documents are overwritten with the same data
and the id counters are raised above the loaded ids.

  python -m backend.migrate_student_data
"""

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    Application,
    Registration,
    SavedItem,
    Student,
    StudentPreferences,
)
from backend.common.mongo_store import (
    ApplicationStore,
    RegistrationStore,
    SavedItemStore,
    StudentStore,
    raise_counter_to,
)


def copy_students_to_mongo(session: Session, database: Any) -> dict[str, int]:
    StudentStore(database).ensure_indexes()
    SavedItemStore(database).ensure_indexes()
    ApplicationStore(database).ensure_indexes()
    RegistrationStore(database).ensure_indexes()

    students = session.scalars(select(Student)).all()
    for student in students:
        database["students"].replace_one(
            {"_id": student.id},
            {
                "_id": student.id,
                "email": student.email,
                "password_hash": student.password_hash,
                "full_name": student.full_name,
                "city": student.city,
                "college_name": student.college_name,
                "major": student.major,
                "state": student.state,
                "skills": student.skills,
                "created_at": student.created_at,
            },
            upsert=True,
        )

    preferences = session.scalars(select(StudentPreferences)).all()
    for row in preferences:
        database["student_preferences"].replace_one(
            {"_id": row.student_id},
            {
                "_id": row.student_id,
                "job_preferences": row.job_preferences,
                "event_preferences": row.event_preferences,
                "updated_at": row.updated_at,
            },
            upsert=True,
        )

    saved = session.scalars(select(SavedItem)).all()
    for row in saved:
        item_id = row.job_id if row.item_type == "job" else row.event_id
        database["saved_items"].replace_one(
            {"_id": row.id},
            {
                "_id": row.id,
                "student_id": row.student_id,
                "item_type": row.item_type,
                "item_id": item_id,
                "saved_at": row.saved_at,
            },
            upsert=True,
        )

    applications = session.scalars(select(Application)).all()
    for row in applications:
        # $set keeps the worker's trace fields on a document it already wrote
        database["applications"].update_one(
            {"_id": str(row.id)},
            {
                "$set": {
                    "student_id": str(row.student_id),
                    "job_id": str(row.job_id),
                    "status": row.status,
                    "applied_at": row.applied_at,
                    "created_at": row.applied_at,
                    "resume_storage_key": row.resume_storage_key,
                    "resume_original_name": row.resume_original_name,
                    "resume_size_bytes": row.resume_size_bytes,
                }
            },
            upsert=True,
        )

    registrations = session.scalars(select(Registration)).all()
    for row in registrations:
        database["registrations"].update_one(
            {"_id": str(row.id)},
            {
                "$set": {
                    "student_id": str(row.student_id),
                    "event_id": str(row.event_id),
                    "registered_at": row.registered_at,
                }
            },
            upsert=True,
        )

    raise_counter_to(database, "students", max((s.id for s in students), default=0))
    raise_counter_to(database, "saved_items", max((r.id for r in saved), default=0))
    raise_counter_to(database, "applications", max((r.id for r in applications), default=0))
    raise_counter_to(database, "registrations", max((r.id for r in registrations), default=0))
    return {
        "applications": len(applications),
        "registrations": len(registrations),
        "students": len(students),
        "student_preferences": len(preferences),
        "saved_items": len(saved),
    }


def main() -> None:
    from backend.app.config import settings

    if settings.persistence != "mongo":
        print("PERSISTENCE is not 'mongo'; nothing to copy.")
        return

    from backend.app.database import SessionLocal
    from backend.app.repos import get_mongo_database

    with SessionLocal() as session:
        counts = copy_students_to_mongo(session, get_mongo_database())
    for name, count in counts.items():
        print(f"Copied {count} rows into MongoDB {name}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Student migration failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
