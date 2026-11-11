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

## Lab 2: run the stack with Docker Compose

The Compose project is named `p03`; every container, volume and network carries
that prefix. Host ports stay inside 9030 to 9039 (see `contracts/README.md`).

### 1. One-time setup

```bash
cp .env.compose.example .env.compose
# edit .env.compose: set MYSQL_ROOT_PASSWORD, MYSQL_PASSWORD and JWT_SECRET_KEY
```

`.env.compose` is ignored by Git. Never commit real values.

### 2. Build, start, inspect, stop

```bash
docker compose --env-file .env.compose up -d --build     # build and start (make up)
docker compose --env-file .env.compose ps                # inspect       (make ps)
docker compose --env-file .env.compose logs -f p03-job-index-worker
docker compose --env-file .env.compose down              # stop         (make down)
docker compose --env-file .env.compose down -v           # stop and delete the data volumes
```

`p03-db-init` creates the MySQL tables and runs the two Lab 1 migrations, and
`p03-kafka-init` creates the five topics and their `.dlq` topics, before the
services start.

### 3. Load the demo data (SEED=3), once

```bash
docker compose --env-file .env.compose --profile seed run --rm p03-seed   # make seed
```

### 4. Check that it works

```bash
make smoke      # python scripts/smoke.py
```

The stack includes all six services (Company 9030, Student 9031, Job 9032,
Application 9033, Event 9034, Assistant 9035). The Assistant needs Ollama
(`qwen3:8b`) running on the host; set `OLLAMA_BASE_URL` in `.env.compose` to
override `http://host.docker.internal:11434`.

End-to-end check of a Kafka flow (company posts a job, the Job service publishes
`job.created`, the worker indexes it in MongoDB). The token from the Company
service is accepted by the Job service because they share `JWT_SECRET_KEY`:

```bash
TOKEN=$(curl -s -X POST http://localhost:9030/api/companies/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"Password123","name":"Demo Co","city":"San Jose","description":"Demo","contact_info":"demo@example.com"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s -X POST http://localhost:9032/api/companies/jobs \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'X-Trace-Id: demo-trace-1' \
  -d "{\"title\":\"Data Analyst Intern\",\"description\":\"Analyze data.\",\"city\":\"San Jose\",\"category\":\"internship\",\"location\":\"Downtown\",\"is_remote\":false,\"salary\":\"32.50\",\"skills\":\"Python, SQL\",\"deadline\":\"$(date -u -v+30d +%Y-%m-%dT%H:%M:%SZ)\"}"

docker compose --env-file .env.compose logs p03-job-index-worker | tail -3
docker exec p03-mongo mongosh p03 --quiet --eval 'printjson(db.job_index.find().toArray())'
docker exec p03-mongo mongosh p03 --quiet --eval 'printjson(db.processed_events.find().toArray())'
```

The `date -v+30d` form is for macOS. On Linux use `date -u -d '+30 days' +%Y-%m-%dT%H:%M:%SZ`.

### Tracing: follow one request through every service

Every request gets a trace id. A client can send its own `X-Trace-Id` (letters,
digits, `.`, `_`, `-`, up to 64 characters); otherwise the service creates one.
The id is returned in the `X-Trace-Id` response header, written to the access log
(`trace_id=...`), put on the Kafka event, and stored by the worker in MongoDB.

```bash
curl -si -X POST http://localhost:9032/api/companies/jobs \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'X-Trace-Id: trace-demo-2' \
  -d "{...same job body as above...}" | grep -i x-trace-id

docker compose --env-file .env.compose logs | grep trace-demo-2
```

The `grep` shows the access-log line from `p03-job-service` and the
`processed ... trace_id=trace-demo-2` line from `p03-job-index-worker`.

## Lab 2: run the stack on Kubernetes

Manifests live in `k8s/` and use the namespace `p03` and `p03-` names. They run
the same pieces as Docker Compose: MySQL, MongoDB, Kafka (single node, KRaft),
the Company, Job and Event services, and the three Kafka workers. Two Jobs
prepare the data first: `p03-db-init` (MySQL tables and migrations) and
`p03-kafka-init` (topics and their `.dlq` topics).

### Local cluster (Docker Desktop)

1. Docker Desktop, Settings, Kubernetes, enable it, wait until it is green.
2. Build the images once (Kubernetes on Docker Desktop reuses them):
   `docker compose --env-file .env.compose build`
3. Create the secret from `.env.compose` and deploy:

```bash
kubectl config use-context docker-desktop
make k8s-up          # creates the namespace and Secret p03-secrets, then applies k8s/
make k8s-status
kubectl -n p03 wait --for=condition=complete job/p03-db-init job/p03-kafka-init --timeout=300s
kubectl -n p03 wait --for=condition=available deployment --all --timeout=300s
```

The Secret is built from `.env.compose` by `make k8s-secret`, so passwords and
the JWT key are never written into a manifest or committed.

### Load the demo data (SEED=3), once

```bash
make k8s-seed
```

### Reach a service from your laptop

```bash
kubectl -n p03 port-forward svc/p03-job-service 9032:9032 &
curl -s http://localhost:9032/health
```

### Useful commands

```bash
kubectl -n p03 get pods -o wide
kubectl -n p03 logs deploy/p03-job-index-worker --tail=20
kubectl -n p03 logs job/p03-kafka-init
kubectl -n p03 describe pod <pod>        # when something will not start
make k8s-down                            # deletes the namespace and all data
```

### Known limits

- Uploaded resumes live on one `ReadWriteOnce` volume shared by the Company and
  Application services. That works on a single node (Docker Desktop); a
  multi-node cluster needs `ReadWriteMany` storage or object storage.
- The Assistant reaches Ollama on the host (`host.docker.internal`), so it works
  on Docker Desktop but not on a cloud cluster without a hosted model.
- One replica of everything, no autoscaling. Kafka and the databases are
  single-node, not highly available.
