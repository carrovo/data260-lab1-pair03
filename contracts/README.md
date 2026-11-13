# Pair 03 contracts (PROPOSED - not frozen until both partners approve)

Everything here is what services agree on. Change it only by editing this
folder in a pull request that both of us approve. Code is built against the
files in `contracts/examples/` and `backend/common/`, never against the other
partner's in-progress code.

## 1. Ports and names

Source of truth: `contracts/services.json`. Ports stay inside 9030 to 9039.
Image names and Kubernetes names use the `p03-` prefix. A test checks that
each Dockerfile uses the port listed there.

| Service | Port | Image / Kubernetes name |
| --- | --- | --- |
| company | 9030 | p03-company-service |
| student | 9031 | p03-student-service |
| job | 9032 | p03-job-service |
| application | 9033 | p03-application-service |
| event | 9034 | p03-event-service |
| assistant | 9035 | p03-assistant-service |
| frontend | 9036 | p03-frontend |
| kafka | 9037 | p03-kafka |
| mongo | 9038 | p03-mongo |

Every service exposes `GET /health` returning
`{"status": "ok", "service": "<name>", "pair": "03"}`.

Services read `DATABASE_URL` and `JWT_SECRET_KEY` from the environment.
Never put real values in an image, a manifest or Git.

## 2. Authentication token

Signed JWT (HS256, shared `JWT_SECRET_KEY`), sent as `Authorization: Bearer`.

| Claim | Meaning |
| --- | --- |
| `sub` | account id as a string |
| `role` | `student` or `company` |
| `iat`, `exp` | issued-at and expiry, Unix seconds |

Each service checks the role itself. A student token is rejected on company
routes and the other way round.

Open point: today `sub` is a MySQL integer id turned into a string and
`decode_access_token` converts it back with `int()`. After the MongoDB
migration `sub` is the string `_id`, so that conversion must go.

## 3. Request tracing

Every request carries `X-Trace-Id`. The assistant creates one when the header
is missing. Services copy it into log lines and into the `trace_id` of every
Kafka event they publish.

## 4. Kafka

Topics, producers and consumers (code: `backend/common/events.py`):

| Topic | Producer | Consumer | Payload keys |
| --- | --- | --- | --- |
| application.created | application | application-worker | application_id, student_id, job_id |
| application.updated | application | application-worker | application_id, student_id, job_id |
| application.status_changed | company | notification-worker | application_id, student_id, job_id, old_status, new_status |
| event.registration_created | event | event-worker | registration_id, student_id, event_id |
| job.created | job | job-index-worker | job_id, company_id, title |

The table lists event types. The real Kafka topics are `p03.<event type>` (for example
`p03.job.created`, dead letters `p03.job.created.dlq`). Code, envelopes and workers use
the plain event type; the prefix is added in one place (`kafka_topic()` in
`backend/common/events.py`, used by the Kafka adapters) and in the topic-creation jobs.
`KAFKA_TOPIC_PREFIX` overrides it.

Every message is one envelope: `event_id`, `event_type`, `trace_id`,
`occurred_at`, `producer`, `payload`. Ids inside payloads are strings.

Consumer rules:

1. Idempotent. Before writing, record the event in `processed_events`
   (document `_id` = `<consumer>:<event_id>`, so each worker keeps its own
   record). A duplicate is skipped.
2. Commit the Kafka offset only after the database write succeeds.
3. Retry a failing message at most 3 times, then publish it to
   `<topic>.dlq` and carry on with the next message. The dead-letter message
   keeps the original text plus `error`, `attempts` and `failed_at`.

## 5. MongoDB collections

| Collection | Written by |
| --- | --- |
| students, student_sessions | student |
| companies | company |
| jobs | job |
| applications | application-worker |
| events | event |
| registrations | event-worker |
| saved_items, activity_logs | assistant (saved items), each service (its own log lines) |
| job_index | job-index-worker |
| notifications | notification-worker |
| processed_events | every worker |
| assistant_rules, student_memory, conversations | assistant |

One service writes each collection. Others read it through that service's API
or learn about changes from Kafka. Document `_id` is a string.

Workers (one image, `p03-worker`, chosen with `WORKER_NAME`): `application-worker` (reads `application.created` and `application.updated`), `job-index-worker`, `notification-worker`, `event-worker`. Each reads `KAFKA_BOOTSTRAP` and `MONGO_URL` from the environment. Students read their notifications through the Student service API.

## 6. Open points for Xuanhua

1. Port table as above: agreed.
2. Payload keys per topic: `application_id`, `student_id`, `job_id` are enough for the
   Application Worker (agreed).
3. `application.updated`: sent when a student replaces the resume
   (`PUT /applications/{id}/resume`); it carries the same three ids (agreed).
4. Who owns `saved_items` - assistant or student service?
5. Split of the student registration route between `events.py` and
   `registration_routes.py`.
