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

The complete-preferences student predictably matches `Data Analyst Intern (REQ-001)`
and `Data Science Career Night - San Jose #001`, and has both a saved job and
saved event. `Untrusted Content Test (REQ-002)` contains harmless prompt-injection
demonstration text; `Clean Content Control (REQ-003)` is its clean comparison.
Searches for a title such as `Quantum Botanist` or an event named
`Underwater Basket Weaving` provide reliable no-match demonstrations.

The demo companies (for example Northwind Analytics, Bayview Health Data) and
students are fictional. Job titles end in `(REQ-nnn)` and event titles in
`- <city> #nnn`; that number keeps each title unique, because the seeder finds
its own records by title.

Seed ownership is limited to the reserved `seed3.*@demo.p03.example.com`
accounts and the demo job/event titles. A database seeded by the first version
(titles starting `Pair03 Seed3`) is renamed in place by the next run. Reruns update those records
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
sh scripts/make_env.sh       # or: make env
```

This creates `.env.compose` with fresh random secrets (it never overwrites an existing
file and never prints the values). To choose them yourself instead, run
`cp .env.compose.example .env.compose` and replace the three `change-me` values
(`MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`, `JWT_SECRET_KEY`).

`.env.compose` is ignored by Git. Never commit real values. Every Compose and `make`
command in this README needs this file.

### 2. Build, start, inspect, stop

```bash
docker compose --env-file .env.compose up -d --build     # build and start (make up)
docker compose --env-file .env.compose ps                # inspect       (make ps)
docker compose --env-file .env.compose logs -f p03-job-index-worker
docker compose --env-file .env.compose down              # stop         (make down)
docker compose --env-file .env.compose down -v           # stop and delete the data volumes
```

`p03-db-init` creates the MySQL tables and runs the two Lab 1 migrations, and
`p03-kafka-init` creates the five topics (named `p03.<event type>`, for example `p03.job.created`) and their `.dlq` topics, before the
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
override `http://host.docker.internal:11434`. `OLLAMA_NUM_PREDICT` is an optional
positive-integer response-token cap; it is unset by default, so local behavior is
unchanged unless the variable is explicitly configured.

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
docker exec p03-mongo mongosh p03_handshake --quiet --eval 'printjson(db.job_index.find().toArray())'
docker exec p03-mongo mongosh p03_handshake --quiet --eval 'printjson(db.processed_events.find().toArray())'
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
the six services (Company, Student, Job, Application, Event, Assistant), the
frontend gateway and the four Kafka workers. Two Jobs prepare the data first: `p03-db-init` (MySQL tables and migrations) and
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

### Roll the cluster onto freshly built images

Docker Desktop shares its image store with Compose, so rebuilding is enough; no
registry push. A Job cannot be edited, so `p03-db-init` is deleted and recreated:

```bash
docker compose --env-file .env.compose build
kubectl -n p03 delete job p03-db-init --ignore-not-found
kubectl apply -k k8s
kubectl -n p03 wait --for=condition=complete job/p03-db-init job/p03-kafka-init --timeout=300s
kubectl -n p03 rollout restart deployment
```

`scripts/verify_k8s.sh` does all of this, waits for every rollout, then checks
the client libraries inside the pods, runs the smoke test and a small JMeter
trial through port-forwards, and writes `verify_k8s_output.txt`.

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
  Application services. On Docker Desktop (one node) that just works; on EKS the
  AWS overlay keeps both services on the same node (pod affinity). More nodes
  would need `ReadWriteMany` storage (for example EFS) or object storage.
- The Assistant needs an Ollama model server: Docker Desktop uses Ollama on the
  host (`host.docker.internal`); the AWS overlay runs Ollama inside the cluster
  (`aws/overlay/ollama.yaml`).
- One replica of everything, no autoscaling. Kafka and the databases are
  single-node, not highly available.

## Lab 2: AWS deployment (EKS)

The whole platform runs on Amazon EKS (cluster `p03-handshake`, region `us-east-1`, namespace
`p03`) with the images in Amazon ECR (`p03-<service>`, tag `lab2`). The scripts, the evidence and
the problems we met are in [docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md). No account id, key or
password is committed; the scripts read the account from the AWS CLI session and hide it in their
output.

### Reach the deployment

```bash
aws eks update-kubeconfig --name p03-handshake --region us-east-1
kubectl -n p03 get pods
kubectl -n p03 get svc p03-frontend        # EXTERNAL-IP is the public address
```

Open `http://<EXTERNAL-IP>:9036` (the React app and the `/gw` API gateway share this port) and
sign in with one of the seeded accounts from the demo-data table above. Quick checks:

```bash
curl -s http://<EXTERNAL-IP>:9036/healthz                       # 200
G=http://<EXTERNAL-IP>:9036 sh scripts/check_kafka_flow.sh      # PASS = Kafka flow end to end
sh scripts/aws_verify.sh                                        # login, job search, kubectl output
```

### Pause and resume (the cluster is paused between sessions to save credit)

```bash
sh scripts/aws_pause.sh down     # nodes to 0; cluster, volumes and images stay
sh scripts/aws_pause.sh up       # about 5 minutes until both nodes are Ready
kubectl get nodes                # then: kubectl -n p03 get pods
```

The public address does not change when the cluster resumes. Give the workers a few minutes
before showing the Kafka flow: the first events after a resume can be applied late.

### Assistant on AWS

Ollama (`qwen3:8b`) runs in the cluster on CPU-only nodes (`aws/overlay/ollama.yaml`). The AWS
overlay sets `OLLAMA_NUM_PREDICT=256` (the optional answer-length cap; unset everywhere else),
a 300 s load balancer idle timeout and a 280 s gateway timeout. One answer takes about 2 to 3
minutes there, so ask one question a few minutes before a demo to load the model.

### Deploy from scratch

The ordered commands (`aws_ecr_push.sh`, `eksctl create cluster -f aws/eks-cluster.yaml`,
`aws_ebs_csi.sh`, `aws_deploy.sh`, `aws_ollama.sh`) are listed in `docs/AWS_DEPLOYMENT.md`.

## Persistence switch (MySQL or MongoDB)

Companies, jobs and events can live in MySQL (default) or MongoDB. Set
`PERSISTENCE=mongo` in `.env.compose` (Compose) or in `k8s/config.yaml` (Kubernetes);
the database is `p03_handshake`. In Mongo mode `p03-db-init` drops the MySQL foreign keys
that point at those three tables, and the seed loads them into MongoDB. Students,
applications, saved items and event registrations always stay in MySQL.

All code that reads companies, jobs or events goes through the repositories in
`backend/app/repos.py`: the Company, Job and Event routes, the student application
and registration routes, and the Assistant tools. With `PERSISTENCE=sql` the original
SQL code paths run unchanged.

Status: Mongo mode is verified on Docker Compose and on Kubernetes (50 companies,
300 jobs, 100 events in MongoDB, plus the smoke test). The CRUD load plan covers
100 / 200 / 300 / 400 / 500 users; the recorded Mongo checkpoints at 100, 300 and
500 users had 0 errors (see `METRICS.md`). `k8s/config.yaml` stays on `sql`;
`sh scripts/k8s_mongo.sh on` (or `off`) switches a running cluster without editing
files. On Compose, remove the `PERSISTENCE=mongo` line, rebuild, and reseed to go back.

## Frontend and gateway (port 9036)

`frontend/` is the React app. Its image (`frontend/Dockerfile`) builds the site and
serves it with nginx on port 9036. nginx is also the single entry point for the
browser, so there is one origin and no CORS: it forwards API calls to the six
services by path (`frontend/nginx.conf`). Student requests use the prefix `/gw`
(removed before forwarding) because the app has its own `/jobs`, `/events` and
`/applications` pages.

| Browser path | Service |
|---|---|
| `/gw/auth/*` | Student 9031 |
| `/gw/jobs`, `/gw/jobs/{id}` | Job 9032 |
| `/gw/jobs/{id}/applications`, `/gw/applications/*` | Application 9033 |
| `/gw/events*`, `/gw/registrations/*` | Event 9034 |
| `/gw/assistant/*` | Assistant 9035 |
| `/api/companies/auth`, `/me`, `/students`, `/applications`, `/jobs/{id}/applicants` | Company 9030 |
| `/api/companies/jobs*` | Job 9032 |
| `/api/companies/events*` | Event 9034 |

`backend/tests/test_frontend_gateway.py` replays nginx's matching rule against 27
real paths. Open http://localhost:9036 after `up -d --build`; demo logins are in
the table above. In Compose the gateway starts with the rest of the stack; in
Kubernetes it is `k8s/frontend.yaml`.

## Load testing and verification

- `loadtest/` holds the JMeter plan (4 scenarios, 100 / 200 / 300 / 400 / 500 concurrent users);
  see `loadtest/README.md` for the commands and `METRICS.md` for the results and
  the two bottlenecks found and fixed (database pool, worker thread pool).
- `scripts/verify_stack.sh` checks a running Compose stack (smoke test, 5-user trial,
  Mongo counts, Kafka offsets, worker log) and writes `verify_output.txt`.
- `scripts/verify_k8s.sh` does the same for Kubernetes (`verify_k8s_output.txt`).
- `scripts/verify_frontend.sh` starts the stack and checks every gateway route
  (`verify_frontend_output.txt`).

## Deterministic Agent harness (Carol)

From the repository root, with the backend dependencies already installed in
`.venv`, run:

```sh
sh scripts/run_agent_harness.sh --persistence sql --label wip
```

The ten stable H01–H10 cases use deterministic scripted/input-sensitive model
clients through production authentication, Agent, tool, confirmation, sanitizer,
and tracing modules. SQL mode uses isolated in-memory SQLite fixtures; no running
database, Kafka, Ollama, or cloud service is required. The command exits nonzero
if any required case fails. JSON evidence and a Markdown summary are written to
the ignored `loadtest/temp/agent_harness/wip/` directory as
`agent_harness_wip.json` and `agent_harness_wip.md`. Use a new label for each run
or `--output-dir` to select a separate temporary directory.

H07 demonstrates `client_carried_history` using two authenticated requests.
This checkpoint does not establish live-model injection resistance, Mongo-mode
harness coverage, or server-persistent conversation memory. Token/context fields
remain nullable placeholders. Generated evidence is temporary and is not tracked.

The Agent validator reads the same declared tool parameter schemas supplied to
the model and rejects invalid arguments before confirmation/execution. It covers
the constraints currently declared: types, properties, required fields,
`additionalProperties`, enums, and numeric minimums, plus recursive object/array
values, finite numbers, constants, length bounds, and maximums. It is a limited
validator: references (`$ref`), composition (`allOf`/`anyOf`/`oneOf`/`not`),
conditional schemas, patterns/formats, and other array/object constraints are
unsupported and currently unused. Schema changes must review validator support;
unsupported constructs are not automatically enforced.

### Assistant memory (Carol)

Memory uses `MONGO_URL` / `MONGO_DB` independently of `PERSISTENCE` (business
default remains `sql`). With Mongo configured, every Assistant interaction uses
memory; Mongo failures return 503, with no in-process persistence substitute.
Without `MONGO_URL`, legacy stateless/client-carried chat remains available;
memory commands and server conversation IDs explicitly return 503.

Collections and indexes:

| Collection | Document / indexes |
|---|---|
| `assistant_rules` | Trusted server rule ID and description; unique `_id`. Idempotently seeded privacy and eligibility rules. Canonical server rules are injected; user text, DB content and consolidation cannot redefine them. |
| `student_memory` | `_id` and unique `student_id` are the authenticated string ID; `version`, bounded `entries`, event receipts and last consolidation audit. Each entry has stable `id`, ISO `date`, `category`, exclusive fact `key`, `value`, `description`, `provenance`. |
| `conversations` | Opaque `_id`, owner `student_id`, public `messages`, `version`, `expires_at`; owner/expiry compound index and TTL index on expiry. |

The bounded explicit learning grammar is `My preferred city is San Jose.` (also
`role` or `work mode`, optionally prefixed `Remember: `). Only the authenticated
student's input is eligible; retrieved text/model answers never create facts.
Values are bounded and restricted; instruction/credential-like values are rejected.
Dialogue storage omits whole credential-bearing turns and redacts emails. These are
conservative heuristics, not a general sensitive-data classifier; avoid entering
private information. Memory capacity is 200 entries; request consolidation when full.
The latest 20 entries, prioritizing fact keys mentioned in the current request,
are injected as labeled untrusted data through the production sanitizer. Trusted
privacy/eligibility rules remain instructions. Model inference still uses the
production bounded Agent, typed validation, allowlist and confirmation protections.

`POST /assistant/chat` preserves the existing response body and adds
`X-Conversation-Id` when memory is active. Supply that ID as optional JSON
`conversation_id` on subsequent requests. Stored history then takes precedence:
caller history is ignored, so turns are not duplicated. Without an ID, a new
conversation is started and valid client-carried history remains supported.
Stored dialogue is limited to 40 public turns, expires after eight hours, and is
logically inaccessible immediately at expiry; Mongo TTL removes it asynchronously.
Version checks reject concurrent/lapsed history writes with 409. This is separate
from authentication; existing JWTs and confirmation ownership/replay rules apply.

Authenticated commands/routes (through gateway use `/gw/assistant/...`):

- Chat message `/memory`: deterministic dated/category listing, bounded to 40
  entries and the existing reply limit; no model summarization.
- `GET /assistant/memory`: latest 40 learned entries with total count.
- `POST /assistant/conversations/{id}/end`: owner-only discard of current history,
  then delivery-confirmed enqueue. Failure returns 503 with `ended: true` and
  `consolidation_enqueued: false` in the error detail; retry the next route.
  Session history stays ended.
- `POST /assistant/memory/consolidate`: returns 202 only after a successful broker
  acknowledgement, 503 on unavailable/failed/unconfirmed delivery. The scoped
  send waits at most two seconds for acknowledgement, without consolidation or
  model inference. Timeout is an unknown outcome: the event may still arrive,
  so retries can produce another harmless consolidation request. No outbox is used.

`assistant.memory_consolidation_requested` carries only string `student_id`,
with the request trace supplied by the existing publisher. Physical topics and
DLQs use `kafka_topic()`; Compose/Kubernetes initialization now runs
`python -m backend.workers.init_topics` in the shared worker image for all existing
topics and the new topic. `assistant-memory-worker` uses the existing three-attempt
retry/DLQ/offset framework. Build the worker image before running init jobs.

Consolidation is deterministic: same category/key denotes an exclusive fact;
duplicates merge and the latest dated explicit assertion wins contradictions,
with stable entry-ID tie-breaking. Unrelated keys survive. Invalid opaque entries
are preserved; invalid dates fail the operation rather than silently delete data.
No model-generated consolidation output or arbitrary count truncation is used.
An atomic version comparison replaces entries and records the event receipt in
the same student document. Concurrent additions force a re-read/recompute; crash
replay after replacement is a no-op before `processed_events` is repaired. The
common runner commits offsets after writes/processed recording (or durable DLQ).
Only the memory worker opts into delivery-confirmed DLQ sends; if confirmation
fails it raises before offset commit. Existing producers/workers keep their behavior.
Event receipts currently accumulate; long-running deployments need a coordinated
receipt retention policy. Rules are unchanged by learning or consolidation.

Verification commands:

```sh
.venv/bin/python -m pytest -q backend/tests/test_assistant_memory.py -rs
sh scripts/run_agent_harness.sh --persistence sql --label memory-check
# Prepared worker environment; choose a NEW label and output directory per demo.
# MONGO_URL and KAFKA_BOOTSTRAP must identify local services.
python -m backend.memory_demo --label example-new-run --output-dir loadtest/temp/assistant-memory/example-new-run
# Idempotent seed only (Mongo required; no Kafka): add --seed-only.
```

The demo idempotently seeds a synthetic student-memory subject with 63 dated
entries (30 duplicate pairs and three newer corrections), publishes through real
Kafka, runs the production consumer/handler against isolated Mongo, and records
safe before/after entries, event/trace IDs and completion. It uses a dedicated
`p03_memory_demo_<label>` database and `p03.memorydemo-<label>.` topic namespace;
it does not reset databases or reuse business accounts. Rerunning the seed preserves
existing state; choose a fresh label to reproduce the original 63-entry baseline.
Raw evidence remains ignored under `loadtest/temp/`. A reviewed synthetic-only
submission copy and summary are tracked in
`loadtest/evidence_assistant_memory_2026-11-15.json` and
`loadtest/summary_assistant_memory_2026-11-15.md`. See METRICS for actual
results. Persistent-memory HTTP behavior is tested with isolated Mongo mocks;
the real demo verifies Kafka/Mongo consolidation, not a live HTTP/Ollama deployment.
H07 remains `client_carried_history`. Redux, token/context instrumentation, Part 6
automatic compaction, live-model memory safety and AWS deployment are out of scope.
