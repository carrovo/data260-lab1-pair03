"""Prepare MySQL for PERSISTENCE=mongo.

Companies and jobs live in MongoDB in that mode, so the MySQL foreign keys
that point at the companies and jobs tables (applications.job_id,
saved_items.job_id, events.company_id, jobs.company_id ...) would reject rows
that refer to them. This drops those constraints. The columns stay, so every
query and the data shape are unchanged.

Safe to rerun, and a no-op unless PERSISTENCE=mongo and the database is MySQL.
Run it after backend.create_schema:  python -m backend.migrate_mongo_persistence
"""

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from backend.app.config import settings

MONGO_OWNED_TABLES = ("companies", "jobs", "events")


def foreign_keys_to(
    inspector: Any, tables: tuple[str, ...] = MONGO_OWNED_TABLES
) -> list[tuple[str, str | None, str]]:
    """(table, constraint name, referred table) for every FK into `tables`."""
    found = []
    for table in sorted(inspector.get_table_names()):
        for foreign_key in inspector.get_foreign_keys(table):
            if foreign_key["referred_table"] in tables:
                found.append(
                    (table, foreign_key.get("name"), foreign_key["referred_table"])
                )
    return found


def drop_foreign_keys(engine: Engine) -> list[tuple[str, str | None, str]]:
    constraints = foreign_keys_to(inspect(engine))
    if engine.dialect.name != "mysql":
        return constraints  # nothing is executed (SQLite cannot drop them)

    with engine.begin() as connection:
        for table, name, _referred in constraints:
            if name:
                connection.execute(
                    text(f"ALTER TABLE `{table}` DROP FOREIGN KEY `{name}`")
                )
    return constraints


def main() -> None:
    if settings.persistence != "mongo":
        print("PERSISTENCE is not 'mongo'; MySQL foreign keys left unchanged.")
        return

    from backend.app.database import engine

    dropped = drop_foreign_keys(engine)
    if not dropped:
        print("No foreign keys to companies or jobs remain.")
    for table, name, referred in dropped:
        print(f"Dropped {table}.{name} -> {referred}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Mongo persistence migration failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
