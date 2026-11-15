"""Copy the student-side MySQL rows into MongoDB (PERSISTENCE=mongo).

Students, their preferences and their saved items live in MongoDB in that
mode. This loads whatever is in the MySQL students, student_preferences and
saved_items tables into the matching collections, keeping every id so that
applications and registrations (still in MySQL) keep pointing at the right
student. Safe to rerun: existing documents are overwritten with the same data
and the id counters are raised above the loaded ids.

  python -m backend.migrate_student_data
"""

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import SavedItem, Student, StudentPreferences
from backend.common.mongo_store import (
    SavedItemStore,
    StudentStore,
    raise_counter_to,
)


def copy_students_to_mongo(session: Session, database: Any) -> dict[str, int]:
    StudentStore(database).ensure_indexes()
    SavedItemStore(database).ensure_indexes()

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

    raise_counter_to(database, "students", max((s.id for s in students), default=0))
    raise_counter_to(database, "saved_items", max((r.id for r in saved), default=0))
    return {
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
