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

## Deterministic Final Demo Data

Run both migrations above before loading final demo data. The seed generator
validates the canonical schema and stops without changing it when a required
table or column is missing. It does not run or replace migrations.

From the repository root, run:

```bash
.venv/bin/python -m backend.seed_final_data
```

The generator uses `SEED = 3`, the Pair 03 cities (San Jose, Santa Clara, and
Fremont), and the fixed default base date `2030-01-15`. To make the displayed
schedule relative to another documented date while retaining deterministic
output, set an ISO date explicitly:

```bash
SEED_BASE_DATE=2031-01-15 .venv/bin/python -m backend.seed_final_data
```

For reproducible assistant transcripts, the server-owned deterministic demo
reference date is `2029-10-15`. Relative date phrases are calculated from that
date, so “next month” means the complete range `2029-11-01` through
`2029-11-30`. This assistant reference is independent of client conversation
history and does not change or rerun the seed generator.

Each successful run verifies and reports these exact reserved demo counts:

| Entity | Count |
|---|---:|
| Students | 200 |
| Companies | 50 |
| Jobs | 300 |
| Applications | 1,500 |
| Events | 100 |
| Student preference rows | 150 |
| Event registrations | 600 |
| Saved jobs and events | 600 |

The following credentials are intentionally shared for classroom demos only.
They must not be reused outside this lab:

| Scenario | Email | Password |
|---|---|---|
| Student with complete job/event preferences | `seed3.student.001@demo.p03.example.com` | `Pair03Demo!2026` |
| Student with partial preferences | `seed3.student.002@demo.p03.example.com` | `Pair03Demo!2026` |
| Student with no preference row | `seed3.student.004@demo.p03.example.com` | `Pair03Demo!2026` |
| Company owning multiple jobs and events | `seed3.company.001@demo.p03.example.com` | `Pair03Demo!2026` |

The complete-preferences student predictably matches `Pair03 Seed3 Job 001 -
Data Analyst Intern` and `Pair03 Seed3 Event 001 - Data Science Career Night`,
and has both a saved job and saved event. `Pair03 Seed3 Job 002 - Untrusted
Content Test` contains harmless prompt-injection demonstration text; `Pair03
Seed3 Job 003 - Clean Content Control` is its clean comparison. Searches for a
title such as `Quantum Botanist` or an event named `Underwater Basket Weaving`
provide reliable no-match demonstrations.

Seed ownership is limited to the reserved `seed3.*@demo.p03.example.com`
accounts and `Pair03 Seed3` job/event natural keys. Reruns update those records
in one transaction without duplicating applications, registrations,
preferences, or saved items. The script never drops or truncates tables and
does not delete unrelated user data. It refuses a legacy generic
`saved_items.item_id` schema rather than rewriting it. Seeded applications keep
resume metadata null and do not create or claim uploaded PDF files.

The generator and its safety behavior are covered with disposable SQLite tests.
It has not yet been executed against the real MySQL database; run the documented
migrations and perform a reviewed MySQL smoke run before the final demo.
