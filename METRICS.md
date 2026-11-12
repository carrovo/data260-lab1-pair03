# Lab 1 Metrics

## Measurement Snapshot

| Item | Value |
|---|---|
| Pair | 03 |
| Branch | `integration/final-merge` |
| Commit | `b9e40e62b5247de62297626c9b9959b954195c05` |
| Verification date | 2026-10-19 |
| `PORT_BASE` | 9030 |
| Database prefix | `p03` |
| Seed | 3 |
| City set | San Jose, Santa Clara, Fremont |

## Automated Verification

| Check | Result | Details |
|---|---:|---|
| Backend test suite | PASS | 236 passed, 0 failed, 1 dependency deprecation warning |
| Frontend lint | PASS | ESLint completed with no findings |
| Frontend production build | PASS | 110 modules transformed; build completed in 244 ms |
| FastAPI route decorators | 35 | Counted across `backend/app/routers/` |
| Registered assistant tools | 5 | Preferences, job search, job details, event search, and save |

### Backend Tests by Module

| Test module | Collected tests |
|---|---:|
| `test_ai_core.py` | 35 |
| `test_ai_tools.py` | 73 |
| `test_canonical_schema.py` | 19 |
| `test_company_workflows.py` | 10 |
| `test_final_seed_data.py` | 16 |
| `test_student_applications.py` | 17 |
| `test_student_assistant.py` | 32 |
| `test_student_auth.py` | 7 |
| `test_student_events.py` | 11 |
| `test_student_jobs.py` | 16 |
| **Total** | **236** |

## Deterministic Seed Dataset

The seed generator uses `SEED = 3` and validates these reserved demo-record counts after each successful run.

| Entity | Expected count |
|---|---:|
| Students | 200 |
| Companies | 50 |
| Jobs | 300 |
| Applications | 1,500 |
| Events | 100 |
| Student preference rows | 150 |
| Event registrations | 600 |
| Saved jobs and events | 600 |

The generator is idempotent for its reserved `seed3` records, does not drop or truncate tables, and is covered by 16 automated seed-data tests.

## Assistant Tool-Call Reliability

The agent loop was evaluated across 20 deterministic adversarial turns. Four turns were assigned to each initial outcome category. Failed calls received one error-specific repair prompt; the loop stopped cleanly after the bounded repair attempt.

| Failure mode | Before repair | After repair | Representative example |
|---|---:|---:|---|
| Malformed arguments | 4 | 0 | Invalid JSON repaired to a valid `search_jobs` call |
| Unknown tool name | 4 | 0 | `find_jobs` repaired to registered tool `search_jobs` |
| Text where a tool was required | 4 | 0 | Unsupported text repaired to `search_events` |
| Lost multi-step chain | 4 | 0 | Preferences lookup continued to the required job search |
| Well-formed and correct | 4 | 20 | `is_remote=true` used for a remote internship search |
| **Total turns** | **20** | **20** | One repair attempt maximum |

| Reliability summary | Before repair | After repair |
|---|---:|---:|
| Valid turns | 4 | 20 |
| Failed turns | 16 | 0 |
| Valid-call rate | 20% | 100% |

These are controlled reliability-test results produced with scripted model responses and the real agent loop. They measure the repair behavior deterministically; they are not presented as the natural error rate of the Ollama model.

## Frontend Build Output

| Artifact | Raw size | Gzip size |
|---|---:|---:|
| `dist/index.html` | 0.45 kB | 0.29 kB |
| Main CSS bundle | 54.15 kB | 9.16 kB |
| Main JavaScript bundle | 389.45 kB | 117.41 kB |


## Lab 2 Load Test (JMeter)

Apache JMeter 5.6 (non-GUI), plan `loadtest/handshake.jmx`, run against the Docker Compose stack
on one MacBook Pro (Docker Desktop, 7.7 GiB for containers; JMeter on the same machine, so the
numbers include that contention). Code under test: commit `3d15d3a` on
`feature/lab2-company-services`, `PERSISTENCE=sql`, seed 3 data loaded.

Four scenarios run at the same time: student login + job search, student login + application
upload (PDF), student login + event search + registration, company login + dashboard.
Each virtual user logs in once, then repeats its scenario 30 times with a 500 ms think time.
Users are per scenario, so 25 users per scenario is 100 concurrent users in total.
Applying twice and registering twice are expected 409 answers and count as passes.

| Concurrent users | Requests | Throughput | Mean | p95 | p99 | Max | Errors |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 6,850 | 105 req/s | 10 ms | 14 ms | 260 ms | 626 ms | 0.00% |
| 300 | 20,550 | 272 req/s | 21 ms | 82 ms | 261 ms | 571 ms | 0.00% |
| 500 | 34,250 | 432 req/s | 180 ms | 586 ms | 845 ms | 2,165 ms | 0.00% |

Per request, selected rows (mean / p95 in ms):

| Request | 100 users | 300 users | 500 users |
|---|---:|---:|---:|
| Student login (bcrypt, once per user) | 274 / 340 | 267 / 314 | 308 / 367 |
| Search jobs by keyword | 4 / 7 | 6 / 19 | 64 / 223 |
| Apply with resume (upload) | 8 / 16 | 35 / 138 | 272 / 688 |
| Search events | 6 / 9 | 14 / 43 | 177 / 524 |
| Register for event | 5 / 10 | 17 / 63 | 230 / 631 |

### Bottlenecks found and fixed

| Step | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | 300 users: 3% errors, slowest request 31 s | Each service kept the SQLAlchemy default pool (5 + 10 connections); the logs show `QueuePool limit of size 5 overflow 10 reached` | Pool of 20 + 20, 10 s wait, MySQL `max_connections` 500 (commit `19c72b6`) |
| 2 | 500 users: 11.6% errors, 34,250 requests took 10 min 27 s, mean 3.7 s, slowest 89 s | All failures in the Event service (`QueuePool limit of size 20 overflow 20 reached`, 2,132 errors); MySQL was not the limit (132 of 500 connections used at peak) | Thread pool raised from 40 to 120 per service so finished requests can return their connection (commit `3d15d3a`) |
| 3 | 500 users, same plan | None | 34,250 requests in 1 min 20 s, 0 errors |

Step 2 is explained as FastAPI running plain endpoints and the clean-up of the `get_db`
dependency on one shared 40-thread pool: when all threads wait for a connection, finished
requests cannot get a thread to release theirs. The fix removed the symptom; the explanation
was not isolated with a separate experiment.

Limits of this test: one machine runs the load generator, Docker and the databases together;
the Kubernetes deployment was not load tested; the assistant (Ollama) is not
part of the load test.
