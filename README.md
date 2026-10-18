# DATA 260 Lab 1 — Pair 03

A Handshake-style web application for students and companies, built with React, FastAPI, MySQL, and a local Ollama model.

## Pair Configuration

| Parameter | Value |
|---|---|
| Pair | 03 |
| PORT_BASE | 9030 |
| Database/Kafka prefix | p03 |
| SEED | 3 |
| CITY_SET | San Jose, Santa Clara, Fremont |

## Week 1 Goal

Build the foundation of the application:

- Set up the private pair repository;
- Create the initial MySQL schema;
- Implement student and company authentication;
- Add bcrypt password hashing and JWT-based authentication;
- Scaffold the deterministic seed generator;
- Prepare the React frontend and FastAPI backend;
- Document setup decisions and development progress.

## Planned Technology Stack

- Frontend: React
- Backend: FastAPI
- Database: MySQL
- Local LLM: Ollama with `qwen3:8b`
- API documentation: FastAPI `/docs`

## Repository Rules

- Do not commit `.env` files, passwords, API keys, virtual environments, or dependency folders.
- Both partners should make regular commits.
- The final Lab 1 version will be tagged `lab1`.

## Application Resume Schema Migration

After creating the base MySQL schema, add the application resume metadata and
align the application status default by running this command from the repository
root:

```bash
.venv/bin/python -m backend.migrate_application_resumes
```

The migration is safe to run more than once. It preserves existing applications,
changes legacy `submitted` statuses to `Pending`, and leaves resume metadata empty
for legacy rows that predate required resume uploads.

## Canonical Shared-Schema Migration

After the base schema and application-resume migration are present, add the
agreed student/company shared fields, student preferences, and saved-item tables
with:

```bash
.venv/bin/python -m backend.migrate_canonical_schema
```

This MySQL-only migration is additive and safe to rerun. It detects existing
columns, indexes, and constraints before adding them, and never drops, renames,
truncates, or deletes existing data. New profile, job, and event attributes are
nullable for compatibility with existing rows; `jobs.is_remote` is backfilled by
its database default of `FALSE`. A later data-quality checkpoint may backfill and
tighten `jobs.category` after every legacy job has a verified category.

The canonical saved-item table uses explicit `job_id` and `event_id` foreign
keys. If a legacy company-only `saved_items.item_id` table is detected, the
migration stops before making changes so that its data can be mapped in a
separately coordinated, non-destructive backfill.
