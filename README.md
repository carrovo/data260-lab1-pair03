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

The Assistant captures the actual server date for each request. There is no
application timezone setting; **UTC is the explicit default**, independent of the
host/browser timezone. For a request dated `2026-11-16` UTC, “next month” means
`2026-12-01` through `2026-12-31`. All iterations/repairs and both compaction probes
use their request's captured date. Explicit user dates/ranges remain unchanged;
conversation content cannot override the server clock. Tests inject an aware clock
for deterministic calendar checks. Fixed seed schedules and older transcript dates
remain historical fixtures; this policy does not alter or rerun the seed generator.

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

## Deterministic Agent harness (Xuanhua Li)

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

### Assistant memory (Xuanhua Li)

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

### Student Redux state (Xuanhua Li)

The existing store now also owns `session`, `savedItems` and `assistant`. The
jobs, companies, applications and events slice implementations are unchanged.
Authentication initialization restores the existing `student_access_token` storage
key. Credentials travel through closure-based thunks and the authenticated client;
JWTs and confirmation tokens are excluded from Redux actions/state. A store-lifetime
private runtime retains pending confirmation tokens across route navigation only.
Logout, current-account 401 responses and a new sign-in clear student caches;
generation/request guards discard previous-account completions.

Use `/saved` to refresh or unsave opportunities, or Save for later on a job/event.
The frontend needed a small authenticated HTTP facade: GET/POST
`/auth/saved-items` and DELETE `/auth/saved-items/{job|event}/{id}` use the existing
SQL/Mongo stores and authenticated identity. No business repository was changed.
Assistant-triggered saves still require the production confirmation flow.

Assistant public messages and a safe pending-action summary survive route changes.
The client reads `X-Conversation-Id` from the backend response and then sends
`conversation_id` without resending history. Without an ID it retains the existing
public user/assistant history contract. CORS exposes that header for development.
A missing in-memory confirmation token also blocks further submissions and
explicitly requires New conversation; an active server session is ended during
that restart. An expired/ended ID requires New conversation; that action ends an active server
session before clearing the thread. A response explicitly confirming session end
is respected even if asynchronous consolidation was unavailable. This UI does not
claim that consolidation was queued. Reload restores authentication only: thread
state/IDs and pending tokens are not durably persisted, and automatic refresh or
cross-device thread restoration is not implemented.

Run the installed frontend tooling from the repository root:

```bash
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

Redux DevTools submission evidence is still a manual step: the automated in-app
browser does not provide the Redux DevTools extension. In a local development
browser with that extension, use synthetic accounts and dialogue only. Open the
Redux panel, sign in, select `session/ready`, and capture the `session` state and
safe action. Send a synthetic Assistant question, navigate to Saved items and back,
select `assistant/completed`, and capture its public messages/conversation ID and
safe pending summary (if present). Optionally capture `savedItems/received` after
saving a synthetic opportunity. Verify that neither State nor Action contains a
JWT, password or `action_token`; do not capture Network headers, localStorage,
private dialogue or real student information. These must be actual Redux-panel
captures, not ordinary page screenshots or exported state dumps.

### Agent usage and conversation compaction (Xuanhua Li)

Assistant responses add `usage` and `compaction` fields; existing response fields,
authentication, tool validation, one-repair/six-iteration limits and explicit
confirmation remain intact. The existing trace logger records only numeric usage,
call purpose/source and trace ID, never model prompts, replies or credentials.

`OllamaClient` preserves `prompt_eval_count` and `eval_count` as per-call prompt and
completion counts ([Ollama API](https://docs.ollama.com/api/chat)). Request totals
sum every invocation, including tool loops, repair calls and compaction probes/
summary generation. Repeated prompts overlap: totals describe evaluated request
work, not unique context or billing. Any missing counter makes that aggregate
unknown (`null`); a request with no model invocations legitimately totals zero.
Deterministic tests label supplied counters `synthetic`, never live measurements.

`OLLAMA_NUM_CTX` is a positive integer, default **4096**, preserving the previously
hard-coded native request budget. Capacity comes from the actual request's
`options.num_ctx`, not a guessed model architecture limit. Latest-call context is
`(latest prompt + latest completion) / requested num_ctx * 100`, using only the
latest call, never the request sum. This is an **estimated occupancy derived from
measured counters**, not an exact observation of Ollama's resident/sliding KV
window. It can exceed 100% when evaluated work exceeds the requested budget; it
is not silently clamped. Missing usage/capacity is displayed as unknown. The UI
warns strictly above **70%**, using the unrounded value. Per-call source/purpose,
request totals and latest-call percentage are shown separately in the existing
Redux Assistant state, with the existing account/late-response guards and resets.

In an active Mongo-backed Assistant conversation, type **`/compact`** or choose
Compact conversation. The command uses the authenticated student's stored history;
client-supplied history cannot replace it. `ASSISTANT_COMPACT_THRESHOLD_PERCENT`
(default **80**, valid range `(0, 100]`) automatically attempts compaction when a
completed Agent call's known context estimate exceeds that percentage. There is
at most one automatic attempt per HTTP request and no recursive Agent loop.
Unknown occupancy never triggers it. No Compose/Kubernetes/AWS defaults changed.

Compaction is separate from Kafka learned-memory consolidation. It performs at
most three calls: a before probe, a model-selected extractive summary, and an after
probe. Probes use identical trusted rules, tool schemas and a fixed READY request;
reported before/after values are their measured **prompt** counts, not the summary
call's input/output or character estimates. All three calls count toward request
usage. If metadata is unavailable, reduction is explicitly unverified/unknown;
when comparable counts exist, no reduction means failure and no replacement.

The summary retains source-verbatim quotes grouped into preferences, jobs,
companies, events, applications, current request, next steps and other facts.
Every original sentence and concrete identifier must remain represented by the
summary or the **two most recent public messages**, retained verbatim. Exact
duplicates may merge; no unrelated facts are dropped to hit a target. Bounds are
40 quotes per group and 6500 characters for the defended summary (a safety bound,
not a token estimate). This conservative extractive policy may refuse to compact
a large, entirely novel history; it does not fabricate a lossy paraphrase.

Generated text is validated against source dialogue and passed through production
untrusted-data delimiters/sanitization as a user-role recollection. It never
becomes a system rule or verified opportunity/application fact; reverify those
facts with tools. Private content is not persisted. Previously compacted quotes
are flattened on repeat compaction, rather than nesting summaries. Mongo's
existing ownership/expiry/version CAS atomically replaces history plus numeric
`last_usage`/`last_compaction` metadata. Failed models, unusable summaries, expiry
or a concurrent turn retain the old/current history. Automatic failure still
saves the current public turn without discarding the uncompressed conversation.

A durable `pending_confirmation` boolean blocks compaction and further normal
turns until the student confirms, declines or ends the session. It contains no
confirmation token. Compaction calls cannot dispatch tools, approve or replay a
write. Existing transient-token restart UI remains unchanged. No Redux persistence,
refresh/cross-device restore, AWS deployment or load testing was added.

Verification commands (repository root, installed `.venv`/frontend dependencies):

```bash
.venv/bin/python -m pytest -q backend/tests/test_agent_observability.py backend/tests/test_ollama_client.py backend/tests/test_ai_core.py backend/tests/test_student_assistant.py backend/tests/test_assistant_memory.py -rs
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
.venv/bin/python -m pytest -q backend/tests -rs
sh scripts/run_agent_harness.sh --persistence sql --label observability-final --output-dir loadtest/temp/agent_harness/observability-final
```

Optional live verification, only when host Ollama `qwen3:8b` and the existing
`p03-mongo` container/host port 9038 are already available:

```bash
.venv/bin/python -m backend.observability_demo --label local-check
```

The demo reads existing container credentials in memory, creates a fresh
`p03_observability_<label>_<suffix>` database and isolated SQLite authentication
fixtures, and invokes authenticated production routes via local ASGI TestClient.
It does not deploy an API or restart services, overwrite environment files, delete
data, or access real student records. Each run writes a new synthetic JSON file
under ignored `loadtest/temp/observability/` and reports its path. Model generation
is not deterministic; retain/report failures rather than claiming success from
health checks. See the tracked observability summary and METRICS for actual runs.
The earlier Redux DevTools screenshot checklist remains pending and unchanged.

Compaction is synchronous and adds bounded model work. On slow hardware, multiple
calls may exceed unchanged gateway/proxy timeouts; this checkpoint does not claim
AWS/gateway timeout or load validation. Final live output was revalidated against
the strengthened whole-sentence/negation validator unchanged; validation/logging
hardening afterward has automated coverage, not a separately claimed live rerun.

Final review additionally preserves each duplicate quote's last-occurrence order
(e.g. A → B → A retains B before the final A), rejecting model-reordered or
misclassified quotes. Malformed summary-shaped data is retained as ordinary
untrusted history rather than silently skipping invalid fields. Quoted JSON
credential keys use the shared privacy filter; detected private/invalid source
history is rejected before any compaction model call. The recorded synthetic live
example passes these stricter checks unchanged, so no inference rerun was needed.

### Assistant trace and 50-request stage evidence (Xuanhua Li)

`TraceMiddleware` now correlates bounded numeric Assistant stage spans with the
existing `X-Trace-Id` and `p03.http` logger. It emits an `assistant_timing` JSON
record per `/assistant/chat` request. No new tracing service or public debug route
is added. The same production Agent/model/tool paths are timed; an optional
middleware sink lets the isolated evidence runner retain those exact reports.
No prompts, SQL statements, Mongo command contents, credentials or tokens enter
stage records. A maximum of 256 detailed spans is retained per request; aggregates
remain counted, and dropped detail is explicitly reported.

Definitions (all local spans use `time.perf_counter`):

- Client end-to-end: actual HTTP POST until response or observed timeout.
- Server elapsed: ASGI request lifecycle until final timing reporting; dependency
  cleanup can finish after the client has received its response.
- Model-call wall time/count: each actual client invocation, including tool-loop
  and repair calls and failed connections. Includes client/network, model load,
  remote scheduling and inference; it is not all pure inference.
- Native inference: directly reported Ollama `prompt_eval_duration + eval_duration`
  in nanoseconds, converted to ms. Missing metadata stays unavailable; no
  inference time is fabricated from tokens or client wall time.
- Tool time/count: actual implementation execution, not merely proposed or rejected
  tool calls. Confirmation-path execution uses the same timing span.
- Database: directly observed PyMongo command round trips and SQLAlchemy cursor
  execution, including failures. These exclude unobserved server selection,
  pool wait and full repository/result-materialization overhead.
- Database spans can be inside tool spans; native inference is inside model wall
  time. Inclusive stage totals must **not** be added as exclusive request costs.
  Unattributed time and client/server differences are **not queue wait**. Queue
  wait remains unavailable because it is not directly exposed here.

With existing host Ollama `qwen3:8b` and `p03-mongo` already running, reproduce from
the repository root using the installed virtual environment:

```bash
sh scripts/assistant_stage_timing.sh --label carol-stage50 --requests 50 --warmup 2
```

This creates a fresh loopback Uvicorn server and unique synthetic Mongo namespace,
using production student auth, Assistant, Agent, native Ollama and real repository
reads. Requests use actual network HTTP, **not** ASGITransport/TestClient or a
scripted model. Business persistence is Mongo only in this process; the application
SQL default and shared service configuration are unchanged. No existing data,
volumes or environment files are deleted/overwritten. A synthetic signup happens
outside measurement; JWTs remain in memory. Same synthetic account, fresh server
conversation per request, no caller-carried history. The read-only search workload
is fixed in `backend/assistant_trace_evidence.py` and recorded in environment.json.

Protocol: concurrency **1**; exactly two warm-ups outside the 50; native model
`num_ctx=4096`, `num_predict=128`, `think=false`, temperature 0.1; 60-second model-call
timeout and 420-second client HTTP timeout. Existing Agent repair/iteration bounds
remain in effect. No client retries, selective replacement or filtering of failed
requests. Errors/timeouts stay in the JSONL and all-request nearest-rank p50/p95/p99.
Unknown native inference/database/queue stages remain unavailable. This is a
sequential attribution run, not a replacement for JMeter concurrency evidence.

One separate failure request, also excluded from the 50, uses a reserved
non-listening loopback port for the native model client. The override exists only
on this isolated app; no production failure flag is added, no shared model is
stopped. Its HTTP status and actual safe Agent outcome are recorded independently
(HTTP 200 can still be an application failure), with bounded observed attempts.
The first valid measured read supplies the successful trace.

Raw sanitized observations are append-written under a new directory in ignored
`loadtest/temp/assistant_trace/`; interrupted runs remain partial, not described as
50 completed requests. The command reports the directory. To validate and preserve
a complete 50-request submission without altering raw files:

```bash
.venv/bin/python -m backend.assistant_trace_submission <run-directory> --output-dir <new-submission-directory>
```

The exporter verifies all 50 unique traces, stage counts, source hashes and
recomputed aggregates; it rejects sensitive patterns and refuses to overwrite an
existing destination. It preserves warm-ups separately and includes successful/
failed trace dossiers and hashes. Source/configuration hashes identify the exact
instrumented working-tree code used, alongside its base commit. Shared-host CPU,
Docker or model activity can affect timings; see the actual evidence notes rather
than treating this as an idle-machine or deployed/AWS benchmark. Trapti's separate
API → Kafka worker → Mongo document trace remains her evidence and is not replaced
by this Assistant-only run. Redux DevTools screenshots remain pending.

Recorded run (2026-11-15 local / 2026-11-16 UTC):
[`loadtest/evidence_assistant_trace_stage50/`](loadtest/evidence_assistant_trace_stage50/)
contains the 50 sanitized JSONL measurements, separate warm-ups, successful and
controlled-failure traces, aggregate analysis, source/configuration hashes and
hardware/background-activity notes. All 50 succeeded; end-to-end p50/p95/p99 were
16.463/20.145/24.119 seconds. The backend regression suite overlapped warm-ups and
early measured requests; other Docker workloads were present. Keep this shared-host
limitation with any reuse of the numbers. Reported timeouts mean client HTTP
deadlines; the existing model abstraction classifies internal transport failures
as bounded `model_backend_error`, without identifying their timeout subtype.

### Bounded conversation compaction — Xuanhua Li (2026-11-16)

`/compact` now uses Ollama native JSON Schema output for a bounded selection of
canonical source-quote IDs. A single inventory replaces duplicated dialogue and
required-quote text. Narrow rules remove exact duplicates, clearly equivalent
single-clause notes and recognized acknowledgements/procedural scaffolding;
distinct facts, identifiers, uncertainties, negations and corrections remain exact
source quotes. The stored untrusted catalog preserves global chronological order,
with category references and source-span/hash provenance. Older grouped summaries
remain readable. No arbitrary free-text summary or invented fact is accepted.

Preflight validates coverage, source privacy, group/reference/summary limits and
available context before any model call. Token preflight is explicitly an
**estimate** (ASCII UTF-8 bytes/2 plus framing reserve; non-ASCII byte fallback),
including production rule/memory injection, not measured tokenizer output. The
summary receives a per-call output allocation capped at 512 tokens and never above
an existing configured output cap. Infeasible sources fail explicitly; they are not
silently truncated. Native model context 4096, 240-second timeout, existing
thresholds, ownership/confirmation protections and atomic Mongo version checks
were not raised or relaxed. Compaction still uses at most three model calls.

One controlled real-network verification used the current frontend proxy, real
local Mongo/Ollama and a same-owner source-identical copy of the 32-message
conversation. Measured probe prompts fell **2922 → 2505 (14.27%)** and stored
messages **32 → 3**. The original conversation remained version 13 / 32 messages,
with its history hash unchanged. The one follow-up supplied only conversation ID
and a question, without answers/history; recall matched the preferred city,
unsubmitted/unknown application state and eligibility-check next step. All 75
source references and requested facts were independently checked in the stored
catalog. City also exists in learned memory, so city recall alone is not proof.

The request took approximately **269 seconds**. This is isolated local network
HTTP evidence, not deployed gateway/AWS/browser screenshot verification. Synchronous
latency remains substantial, and the heuristic preflight is not a guarantee against
native truncation for every input. Earlier invalid-JSON, no-reduction and timeout
attempts remain preserved; older successful demo evidence is not relabeled.

Existing local verification records remain ignored under
`loadtest/temp/final-evidence/compaction-budget/` (README.md, live-result.json,
offline-verified.json and test/harness logs); prior failures remain under
`loadtest/temp/final-evidence/compaction-fix/` and in the original backend log.
These are local paths, not claimed tracked submission artifacts. No private login
file, raw dialogue/logs, temporary evidence or screenshot is included in this fix.
Screenshots remain for separate chat/folder delivery: use the actual Redux DevTools,
usage/compaction/recall UI and saved-evidence views; do not substitute state dumps
or relabel earlier ASGI evidence as a browser run. The five-prompt set still needs
confirmation before its screenshots are claimed.

Verification reused without another run: **95 focused tests**, **559 backend tests**
(no failures/skips) and SQL deterministic harness **10/10**. See METRICS.md and
RUN_LOG.txt for measured counters and command records.
