"""Add the canonical shared fields and student-owned support tables.

Run from the repository root with:

    .venv/bin/python -m backend.migrate_canonical_schema

This MySQL-only migration is additive and idempotent. It does not drop,
rename, truncate, or delete existing schema objects or data.
"""

from collections.abc import Iterable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from backend.app.database import engine


EXISTING_TABLE_COLUMNS = {
    "students": {
        "college_name": "VARCHAR(255) NULL",
        "major": "VARCHAR(255) NULL",
        "state": "VARCHAR(100) NULL",
        "skills": "TEXT NULL",
    },
    "companies": {
        "description": "TEXT NULL",
        "contact_info": "VARCHAR(255) NULL",
        "profile_picture_storage_key": "VARCHAR(255) NULL",
    },
    "jobs": {
        "category": "VARCHAR(50) NULL",
        "location": "VARCHAR(255) NULL",
        "is_remote": "BOOLEAN NOT NULL DEFAULT FALSE",
        "salary": "DECIMAL(12, 2) NULL",
        "skills": "TEXT NULL",
        "deadline": "DATETIME NULL",
    },
    "events": {
        "location": "VARCHAR(255) NULL",
        "major": "VARCHAR(255) NULL",
        "eligibility": "VARCHAR(255) NULL",
    },
}

STUDENT_PREFERENCE_COLUMNS = {
    "student_id": "INTEGER NOT NULL",
    "job_preferences": "JSON NULL",
    "event_preferences": "JSON NULL",
    "updated_at": (
        "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP"
    ),
}

SAVED_ITEM_COLUMNS = {
    "id": "INTEGER NOT NULL AUTO_INCREMENT",
    "student_id": "INTEGER NOT NULL",
    "job_id": "INTEGER NULL",
    "event_id": "INTEGER NULL",
    "item_type": "VARCHAR(20) NOT NULL",
    "saved_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
}


def _table_names(connection: Connection) -> set[str]:
    return set(inspect(connection).get_table_names())


def _column_names(connection: Connection, table_name: str) -> set[str]:
    return {
        column["name"]
        for column in inspect(connection).get_columns(table_name)
    }


def _add_missing_columns(
    connection: Connection,
    table_name: str,
    column_definitions: dict[str, str],
) -> None:
    existing_columns = _column_names(connection, table_name)

    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            print(f"Already present: {table_name}.{column_name}")
            continue

        connection.execute(
            text(
                f"ALTER TABLE `{table_name}` "
                f"ADD COLUMN `{column_name}` {definition}"
            )
        )
        print(f"Added: {table_name}.{column_name}")


def _primary_key_columns(
    connection: Connection,
    table_name: str,
) -> tuple[str, ...]:
    constrained = inspect(connection).get_pk_constraint(table_name).get(
        "constrained_columns"
    )
    return tuple(constrained or ())


def _unique_column_sets(
    connection: Connection,
    table_name: str,
) -> set[tuple[str, ...]]:
    inspector = inspect(connection)
    unique_sets = {
        tuple(constraint.get("column_names") or ())
        for constraint in inspector.get_unique_constraints(table_name)
    }
    unique_sets.update(
        tuple(index.get("column_names") or ())
        for index in inspector.get_indexes(table_name)
        if index.get("unique")
    )
    return unique_sets


def _index_names(connection: Connection, table_name: str) -> set[str]:
    return {
        index["name"]
        for index in inspect(connection).get_indexes(table_name)
        if index.get("name")
    }


def _foreign_key_pairs(
    connection: Connection,
    table_name: str,
) -> set[tuple[tuple[str, ...], str, tuple[str, ...]]]:
    return {
        (
            tuple(foreign_key.get("constrained_columns") or ()),
            foreign_key.get("referred_table", ""),
            tuple(foreign_key.get("referred_columns") or ()),
        )
        for foreign_key in inspect(connection).get_foreign_keys(table_name)
    }


def _check_names(connection: Connection, table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspect(connection).get_check_constraints(
            table_name
        )
        if constraint.get("name")
    }


def _ensure_primary_key(
    connection: Connection,
    table_name: str,
    columns: Iterable[str],
    constraint_name: str,
) -> None:
    expected = tuple(columns)
    if _primary_key_columns(connection, table_name) == expected:
        print(f"Already present: {constraint_name}")
        return

    joined_columns = ", ".join(f"`{column}`" for column in expected)
    connection.execute(
        text(
            f"ALTER TABLE `{table_name}` ADD CONSTRAINT "
            f"`{constraint_name}` PRIMARY KEY ({joined_columns})"
        )
    )
    print(f"Added: {constraint_name}")


def _ensure_unique_constraint(
    connection: Connection,
    table_name: str,
    columns: Iterable[str],
    constraint_name: str,
) -> None:
    expected = tuple(columns)
    if expected in _unique_column_sets(connection, table_name):
        print(f"Already present: unique {table_name}{expected}")
        return

    joined_columns = ", ".join(f"`{column}`" for column in expected)
    connection.execute(
        text(
            f"ALTER TABLE `{table_name}` ADD CONSTRAINT "
            f"`{constraint_name}` UNIQUE ({joined_columns})"
        )
    )
    print(f"Added: {constraint_name}")


def _ensure_index(
    connection: Connection,
    table_name: str,
    column_name: str,
    index_name: str,
) -> None:
    if index_name in _index_names(connection, table_name):
        print(f"Already present: {index_name}")
        return

    connection.execute(
        text(
            f"CREATE INDEX `{index_name}` "
            f"ON `{table_name}` (`{column_name}`)"
        )
    )
    print(f"Added: {index_name}")


def _ensure_foreign_key(
    connection: Connection,
    table_name: str,
    column_name: str,
    referred_table: str,
    constraint_name: str,
) -> None:
    expected = ((column_name,), referred_table, ("id",))
    if expected in _foreign_key_pairs(connection, table_name):
        print(f"Already present: {constraint_name}")
        return

    connection.execute(
        text(
            f"ALTER TABLE `{table_name}` ADD CONSTRAINT "
            f"`{constraint_name}` FOREIGN KEY (`{column_name}`) "
            f"REFERENCES `{referred_table}` (`id`)"
        )
    )
    print(f"Added: {constraint_name}")


def _ensure_check_constraint(
    connection: Connection,
    table_name: str,
    constraint_name: str,
    expression: str,
) -> None:
    if constraint_name in _check_names(connection, table_name):
        print(f"Already present: {constraint_name}")
        return

    connection.execute(
        text(
            f"ALTER TABLE `{table_name}` ADD CONSTRAINT "
            f"`{constraint_name}` CHECK ({expression})"
        )
    )
    print(f"Added: {constraint_name}")


def _ensure_student_preferences(connection: Connection) -> None:
    if "student_preferences" not in _table_names(connection):
        connection.execute(
            text(
                "CREATE TABLE `student_preferences` ("
                "`student_id` INTEGER NOT NULL, "
                "`job_preferences` JSON NULL, "
                "`event_preferences` JSON NULL, "
                "`updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
                "ON UPDATE CURRENT_TIMESTAMP, "
                "CONSTRAINT `pk_student_preferences` "
                "PRIMARY KEY (`student_id`), "
                "CONSTRAINT `fk_student_preferences_student` "
                "FOREIGN KEY (`student_id`) REFERENCES `students` (`id`)"
                ")"
            )
        )
        print("Created: student_preferences")
        return

    _add_missing_columns(
        connection,
        "student_preferences",
        STUDENT_PREFERENCE_COLUMNS,
    )
    _ensure_primary_key(
        connection,
        "student_preferences",
        ("student_id",),
        "pk_student_preferences",
    )
    _ensure_foreign_key(
        connection,
        "student_preferences",
        "student_id",
        "students",
        "fk_student_preferences_student",
    )


def _ensure_saved_items(connection: Connection) -> None:
    if "saved_items" not in _table_names(connection):
        connection.execute(
            text(
                "CREATE TABLE `saved_items` ("
                "`id` INTEGER NOT NULL AUTO_INCREMENT, "
                "`student_id` INTEGER NOT NULL, "
                "`job_id` INTEGER NULL, "
                "`event_id` INTEGER NULL, "
                "`item_type` VARCHAR(20) NOT NULL, "
                "`saved_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                "CONSTRAINT `pk_saved_items` PRIMARY KEY (`id`), "
                "CONSTRAINT `fk_saved_items_student` FOREIGN KEY "
                "(`student_id`) REFERENCES `students` (`id`), "
                "CONSTRAINT `fk_saved_items_job` FOREIGN KEY "
                "(`job_id`) REFERENCES `jobs` (`id`), "
                "CONSTRAINT `fk_saved_items_event` FOREIGN KEY "
                "(`event_id`) REFERENCES `events` (`id`), "
                "CONSTRAINT `uq_saved_item_student_job` UNIQUE "
                "(`student_id`, `job_id`), "
                "CONSTRAINT `uq_saved_item_student_event` UNIQUE "
                "(`student_id`, `event_id`), "
                "CONSTRAINT `ck_saved_item_type` CHECK "
                "(`item_type` IN ('job', 'event')), "
                "CONSTRAINT `ck_saved_item_target_matches_type` CHECK ("
                "(`item_type` = 'job' AND `job_id` IS NOT NULL "
                "AND `event_id` IS NULL) OR "
                "(`item_type` = 'event' AND `event_id` IS NOT NULL "
                "AND `job_id` IS NULL))"
                ")"
            )
        )
        print("Created: saved_items")
        return

    existing_columns = _column_names(connection, "saved_items")
    if "item_id" in existing_columns:
        raise RuntimeError(
            "Legacy saved_items.item_id detected. The canonical schema "
            "requires job_id/event_id foreign keys. Backfill that legacy "
            "table in a separately coordinated migration before running "
            "this additive migration; no data was deleted here."
        )

    _add_missing_columns(connection, "saved_items", SAVED_ITEM_COLUMNS)
    _ensure_primary_key(
        connection,
        "saved_items",
        ("id",),
        "pk_saved_items",
    )
    _ensure_foreign_key(
        connection,
        "saved_items",
        "student_id",
        "students",
        "fk_saved_items_student",
    )
    _ensure_foreign_key(
        connection,
        "saved_items",
        "job_id",
        "jobs",
        "fk_saved_items_job",
    )
    _ensure_foreign_key(
        connection,
        "saved_items",
        "event_id",
        "events",
        "fk_saved_items_event",
    )
    _ensure_unique_constraint(
        connection,
        "saved_items",
        ("student_id", "job_id"),
        "uq_saved_item_student_job",
    )
    _ensure_unique_constraint(
        connection,
        "saved_items",
        ("student_id", "event_id"),
        "uq_saved_item_student_event",
    )
    _ensure_check_constraint(
        connection,
        "saved_items",
        "ck_saved_item_type",
        "`item_type` IN ('job', 'event')",
    )
    _ensure_check_constraint(
        connection,
        "saved_items",
        "ck_saved_item_target_matches_type",
        "(`item_type` = 'job' AND `job_id` IS NOT NULL "
        "AND `event_id` IS NULL) OR "
        "(`item_type` = 'event' AND `event_id` IS NOT NULL "
        "AND `job_id` IS NULL)",
    )
    _ensure_index(
        connection,
        "saved_items",
        "student_id",
        "ix_saved_items_student_id",
    )


def migrate() -> None:
    if engine.dialect.name != "mysql":
        raise RuntimeError("This migration script supports MySQL only.")

    with engine.begin() as connection:
        table_names = _table_names(connection)
        required_tables = set(EXISTING_TABLE_COLUMNS)
        missing_tables = sorted(required_tables - table_names)
        if missing_tables:
            raise RuntimeError(
                "Missing base tables: "
                f"{', '.join(missing_tables)}. Run create_schema.py first."
            )

        if "saved_items" in table_names:
            saved_item_columns = _column_names(connection, "saved_items")
            if "item_id" in saved_item_columns:
                raise RuntimeError(
                    "Legacy saved_items.item_id detected. Coordinate a "
                    "non-destructive data backfill before canonical migration."
                )

        for table_name, definitions in EXISTING_TABLE_COLUMNS.items():
            _add_missing_columns(connection, table_name, definitions)

        _ensure_student_preferences(connection)
        _ensure_saved_items(connection)

    print("Canonical shared-schema migration completed successfully.")


if __name__ == "__main__":
    migrate()
