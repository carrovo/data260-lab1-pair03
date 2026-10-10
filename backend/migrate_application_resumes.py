"""Add application resume metadata and align the status default.

Run from the repository root with:

    .venv/bin/python -m backend.migrate_application_resumes

The migration is intentionally idempotent for the project's existing MySQL
schema. It preserves legacy application rows, which may have no resume.
"""

from sqlalchemy import inspect, text

from backend.app.application_status import ApplicationStatus
from backend.app.database import engine


RESUME_COLUMNS = {
    "resume_storage_key": "VARCHAR(255) NULL",
    "resume_original_name": "VARCHAR(255) NULL",
    "resume_size_bytes": "INTEGER NULL",
}


def migrate() -> None:
    if engine.dialect.name != "mysql":
        raise RuntimeError("This migration script supports MySQL only.")

    inspector = inspect(engine)
    if "applications" not in inspector.get_table_names():
        raise RuntimeError(
            "The applications table does not exist. Run create_schema.py first."
        )

    existing_columns = {
        column["name"] for column in inspector.get_columns("applications")
    }

    with engine.begin() as connection:
        for column_name, column_definition in RESUME_COLUMNS.items():
            if column_name in existing_columns:
                print(f"Already present: applications.{column_name}")
                continue

            connection.execute(
                text(
                    "ALTER TABLE applications "
                    f"ADD COLUMN {column_name} {column_definition}"
                )
            )
            print(f"Added: applications.{column_name}")

        result = connection.execute(
            text(
                "UPDATE applications SET status = :pending "
                "WHERE status = :submitted"
            ),
            {
                "pending": ApplicationStatus.PENDING.value,
                "submitted": "submitted",
            },
        )
        print(f"Updated submitted statuses: {result.rowcount}")

        connection.execute(
            text(
                "ALTER TABLE applications MODIFY COLUMN "
                "status VARCHAR(50) NOT NULL DEFAULT 'Pending'"
            )
        )
        print("Aligned applications.status default: Pending")

    print("Application resume migration completed successfully.")


if __name__ == "__main__":
    migrate()
