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

