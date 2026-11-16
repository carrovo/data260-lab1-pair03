# Assistant trace and stage timing (Carol)

UTC start: `2026-11-16T05:21:01.728950+00:00`; base `58e09200d6534e4ae227485894f54370d29fd843` plus source hashes in environment.json.
Actual network HTTP to a new loopback Uvicorn instance; production auth/Assistant/Agent/tools; live host Ollama and real Mongo in a new synthetic namespace. Not in-process ASGI or deterministic-model timing.

Workload: Find jobs titled Pair03 Trace Data Intern in San Jose using search_jobs. Reply with only the matching title and city.
Concurrency 1; 2 warm-ups excluded; 50 measured of 50 requested. No client retries or replacement requests.
Model `qwen3:8b`, num_ctx=4096, num_predict=128, think=false, temperature=0.1.
Model-call timeout 60s; client HTTP timeout 420s.

Successes: **50**; errors: **0**; timeouts: **0**. Complete: `True`.
All measured outcomes, including errors/timeouts, participate in end-to-end percentiles (standard nearest-rank).

| End-to-end ms | p50 | p95 | p99 |
|---|---:|---:|---:|
| All measured requests | 16463.086 | 20145.471 | 24119.175 |

| Measured stage (inclusive) | Total ms | Mean available/request ms | Coverage |
|---|---:|---:|---:|
| model_elapsed_ms | 720089.447 | 14401.789 | 50/50 |
| native_inference_ms | 704436.421 | 14088.728 | 50/50 |
| tool_elapsed_ms | 39380.023 | 787.600 | 50/50 |
| database_elapsed_ms | 83573.552 | 1671.471 | 50/50 |
| database_inside_tool_ms | 37564.601 | 751.292 | 50/50 |

Largest fully covered inclusive stage: **model_elapsed_ms**.
Observed calls: model 100, tools 50, database 700.
Inclusive DB command/cursor spans can be nested in tools; native inference is inside model-call wall time. These rows are not additive. No residual is called queue wait.

Model wall time includes client serialization, connection/network, Ollama scheduling/load and inference. Native inference is directly reported prompt_eval_duration + eval_duration; it excludes load and is unavailable on failed/missing metadata.
Database spans directly time Mongo commands or SQL cursor execution, not full repository/materialization time or connection-pool wait. Other uninstrumented time remains unattributed.
Queue wait: **unavailable**. No queue attribution is inferred from client/server differences or stage subtraction.

success_trace.json includes an actual read-only tool execution and sanitized response. failure_trace.json is a separate injected model-connect failure on this isolated instance, outside the 50-request workload; HTTP status and safe Agent outcome are reported separately.
No shared service was stopped/reconfigured. No real student, credentials, JWTs, confirmation tokens, private prompts, SQL or Mongo command contents are included.
This sequential attribution experiment does not replace JMeter concurrency levels or establish deployed/AWS/browser performance. Shared host/model activity can affect results.
