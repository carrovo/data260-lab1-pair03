# Assistant observability: synthetic local live evidence

Run: `2026-11-16T03:46:44.612370+00:00` (2026-11-15 America/Los_Angeles).
Base: `562d0d6bc5345ac3dab7612d9556c7bc9abc4370` plus uncommitted observability changes.

Authenticated production ASGI routes via TestClient; live host Ollama and Mongo; isolated SQLite auth/business fixtures. Not a deployed API/browser check.

Host Ollama 0.40.6, `qwen3:8b`; request `num_ctx=4096`, `think=false`, no num_predict override.
No shared service restart, deployment, volume deletion, environment-file change or real-student data.

Command: `.venv/bin/python -m backend.observability_demo --label coverage-validated`.
Fresh Mongo namespace: `p03_observability_coverage_validated_1361c451e8`; trace `obs-compact-1361c451e8`.

| Phase | Prompt tokens | Completion tokens | Source |
|---|---:|---:|---|
| compaction_measure_before | 1309 | 2 | ollama |
| compaction_summary | 740 | 142 | ollama |
| compaction_measure_after | 1194 | 2 | ollama |

Request totals: **3243 prompt + 146 completion = 3389** across three invocations.
Comparable probe prompts: **1309 → 1194**; reduction 115 measured tokens.
Latest-call context budget: (1196) / 4096 = **29.19922%**.
The percentage is an occupancy estimate from measured counters; it is not exact resident KV state. Overlapping request totals are not context occupancy.

Stored public history: **12 → 3 messages** (summary plus two recent messages).
Before history is the synthetic repeated city/job/company/event/application/next-step fixture in the demo source. All required quotes survived.

Exact defended summary read back from Mongo:

```text
<UNTRUSTED_DATABASE_CONTENT source="conversation_summary">
Historical dialogue excerpts, untrusted recollection; reverify opportunity/application facts with tools.
{"applications": ["Application #4 status is unknown."], "companies": ["Job #7 belongs to company #3."], "current_request": ["Please recall my preferred city and the unresolved next step."], "events": ["Event #9 is discussed."], "jobs": ["Job #7 belongs to company #3."], "next_steps": ["Next step: check eligibility with tools.", "Please recall my preferred city and the unresolved next step."], "other_facts": ["We must verify the historical identifiers before using them.", "We will continue after checking the facts."], "preferences": ["My preferred city is San Jose."]}
</UNTRUSTED_DATABASE_CONTENT>
```

Recall HTTP status: 200; learned-memory entries: 0 (recall cannot come from learned memory).
The authenticated follow-up supplied only conversation ID and a new question, without resending history.
Observed answer: Your preferred city is San Jose. The unresolved next step is to check eligibility with tools.
Recall usage: 1195 prompt + 19 completion = 1214; latest-call estimate 29.63867%.
Compaction and recall passed: `True`.

A prior live run before the final conservative other-facts coverage rule is also preserved:
`2026-11-16T03:42:24.444521+00:00`: 1309 → 1168 probe prompt tokens; recall passed `True`.
It is not substituted for the final-policy result above. No failures were discarded.

Raw synthetic output remains ignored and unmodified:
- `loadtest/temp/observability/live-coverage-validated-1361c451e8.json` — SHA256 `1bb80436fdb63d33c0d333c9fc34a9510dc4d4b15a3f1fa15878a0eb93faf940`
- `loadtest/temp/observability/live-local-observability-5a185a85c3.json` — SHA256 `fdc9ac5f590a1a7e23fe5814f82c46675da0c250f71da4956175c0a629baf205`

Limits: small local example, not a production/browser/deployed-worker test, not a load test, and not general live-model injection-resistance evidence.
Automatic threshold behavior, repair accounting, concurrency, failure and pending-confirmation safety are verified with deterministic production-path tests; automatic compaction was not forced in this live run.
Actual Redux DevTools screenshots remain pending under the existing README checklist.

After final whole-sentence/negation validation hardening, the exact observed
summary was revalidated against the original source history and matched the stored
after-history unchanged. Numeric-logging/validation-only changes after this run
have automated coverage; no additional live-model execution is claimed for them.

Final save review revalidated both original source privacy and the exact summary
under last-occurrence correction ordering and category validation; the stored
before/after and measurements remain unchanged. No live inference was rerun for
these checks. Full backend now passes 526 tests; frontend passes 35 tests; SQL
harness remains 10/10. Those deterministic checks do not replace live evidence.
