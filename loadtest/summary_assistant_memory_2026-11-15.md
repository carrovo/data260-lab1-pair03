# Pair 03 Assistant memory: synthetic consolidation evidence

Recorded 2026-11-15. This is deterministic consolidation with real local Kafka
and MongoDB, with no model inference. Full sanitized submission data is in
[evidence_assistant_memory_2026-11-15.json](evidence_assistant_memory_2026-11-15.json).
The original ignored temporary evidence remains unchanged.

| Observation | Actual result |
|---|---|
| Before | 63 dated synthetic entries |
| After | 30 entries |
| Duplicate groups | 30 original duplicate pairs |
| Contradictory groups | 3, each with a later dated correction |
| Unrelated topics retained | All 27 topics `topic-03` through `topic-29` |
| Event | `052e0c31-4f18-4507-b981-846039679967` |
| Trace | `memory-demo-71cd9f874a704fa1ab14771887433921` |
| Processed receipt | `assistant-memory-worker:052e0c31-4f18-4507-b981-846039679967` |
| Completion | `2026-11-15T21:50:20.859119Z`, matching event/trace |

Decision example: `topic-00` retained `correction-0` (`corrected-0`, February 1)
over the two `original-0` assertions dated January 1. The other two contradictions
follow the same explicit-date policy. The count reduction comes from 30 duplicate
merges plus three superseded assertions, not truncation of unrelated facts. No
model mistake or model correction is claimed.

Execution used `backend.memory_demo` in a temporary worker-image container with
source mounted. It published to isolated topic
`p03.memorydemo-carol-20261115-memory.assistant.memory_consolidation_requested`,
consumed with the production Confluent consumer and `run_consumer`, dispatched
through `WORKERS["assistant-memory-worker"][event_type]` to production
`backend.common.assistant_memory.consolidate`, and observed Mongo plus the
`MongoProcessedEventStore` receipt. The consumer ran **inside the CLI**, not as a
separately deployed worker service. Real HTTP/Ollama memory, full Compose service
deployment, Kubernetes and AWS were not verified by this run.

The run predates final publication-acknowledgement and opaque-entry review fixes;
those fixes have subsequent automated test coverage, not a new live run. All
submitted entries are synthetic; no credentials, tokens, connection URLs or real
student information are included. The JSON explicitly identifies duplicate and
contradiction groups and includes every before/after entry and decision.

To reproduce, use the README memory demo command with a fresh label and ignored
output directory in an environment prepared with local Mongo/Kafka. `--seed-only`
is idempotent and does not resurrect facts already merged by consolidation.
