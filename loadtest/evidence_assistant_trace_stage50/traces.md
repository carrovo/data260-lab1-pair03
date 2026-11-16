# Successful and controlled-failure Assistant traces

Actual loopback network HTTP; live Ollama and Mongo; isolated production auth/router/Agent/tool paths. Sanitized response observations, not raw authorization headers or prompts.

## Successful read-only trace

Trace `trace-f77e5d5679-measured-01`; echoed `trace-f77e5d5679-measured-01`.
HTTP **200**, application outcome **success**; injected `False`.
Observed response: - Title: Pair03 Trace Data Intern
- City: San Jose
Client end-to-end 14322.896 ms; server request lifecycle 14348.072 ms.
Calls: model 2, tool 1, direct DB 14; errors `[]`.

| Span | Parent | Stage/operation | Start ms | End ms | Inclusive ms | Error |
|---:|---:|---|---:|---:|---:|---|
| 1 | - | database/mongo_command | 2.280 | 3.545 | 1.265 | - |
| 2 | - | database/mongo_command | 3.776 | 5.049 | 1.273 | - |
| 3 | - | database/mongo_command | 12.727 | 13.284 | 0.557 | - |
| 4 | - | database/mongo_command | 13.443 | 13.924 | 0.482 | - |
| 5 | - | database/mongo_command | 14.071 | 14.533 | 0.463 | - |
| 6 | - | database/mongo_command | 14.646 | 15.167 | 0.521 | - |
| 7 | - | database/mongo_command | 15.254 | 15.583 | 0.329 | - |
| 8 | - | database/mongo_command | 15.993 | 16.789 | 0.795 | - |
| 9 | - | database/mongo_command | 16.942 | 17.635 | 0.693 | - |
| 10 | - | database/mongo_command | 17.846 | 18.409 | 0.563 | - |
| 11 | - | model/agent | 18.506 | 7028.063 | 7009.557 | - |
| 12 | - | tool/search_jobs | 7030.508 | 7097.849 | 67.341 | - |
| 13 | 12 | database/mongo_command | 7062.366 | 7077.162 | 14.796 | - |
| 14 | 12 | database/mongo_command | 7080.314 | 7097.489 | 17.175 | - |
| 15 | - | model/agent | 7097.935 | 14061.422 | 6963.487 | - |
| 16 | - | database/mongo_command | 14069.064 | 14301.439 | 232.375 | - |
| 17 | - | database/mongo_command | 14318.486 | 14341.877 | 23.391 | - |

DB child spans are already inside their tool parent; native prompt/decode inference is inside model wall time. Do not add inclusive stages. Queue wait is unavailable.

## Controlled failed trace (outside the 50)

Trace `trace-f77e5d5679-failure-01`; echoed `trace-f77e5d5679-failure-01`.
HTTP **200**, application outcome **safe_error**; injected `True`.
Observed response: I couldn't complete that request after one repair attempt. Reason: The request requires search_jobs, but the completed tool sequence was empty.
Client end-to-end 648.993 ms; server request lifecycle 648.571 ms.
Calls: model 2, tool 0, direct DB 12; errors `['model_backend_error']`.

| Span | Parent | Stage/operation | Start ms | End ms | Inclusive ms | Error |
|---:|---:|---|---:|---:|---:|---|
| 1 | - | database/mongo_command | 19.219 | 34.750 | 15.531 | - |
| 2 | - | database/mongo_command | 35.417 | 39.107 | 3.690 | - |
| 3 | - | database/mongo_command | 74.569 | 79.001 | 4.432 | - |
| 4 | - | database/mongo_command | 79.982 | 83.675 | 3.693 | - |
| 5 | - | database/mongo_command | 84.353 | 86.037 | 1.684 | - |
| 6 | - | database/mongo_command | 86.598 | 88.884 | 2.287 | - |
| 7 | - | database/mongo_command | 89.464 | 91.857 | 2.393 | - |
| 8 | - | database/mongo_command | 93.915 | 95.931 | 2.016 | - |
| 9 | - | database/mongo_command | 96.498 | 97.849 | 1.351 | - |
| 10 | - | database/mongo_command | 98.291 | 100.864 | 2.573 | - |
| 11 | - | model/agent | 101.351 | 374.590 | 273.239 | model_backend_error |
| 12 | - | model/agent | 374.904 | 637.564 | 262.661 | model_backend_error |
| 13 | - | database/mongo_command | 639.000 | 642.983 | 3.982 | - |
| 14 | - | database/mongo_command | 645.964 | 647.301 | 1.337 | - |

DB child spans are already inside their tool parent; native prompt/decode inference is inside model wall time. Do not add inclusive stages. Queue wait is unavailable.

## Shared-host environment observation

Backend regression suite overlapped warm-ups and the early measured requests; other Docker workloads are present. Shared-host attribution, not an idle-machine benchmark.
CPU Apple M4; logical cores 10; RAM 17179869184 bytes. Hardware source: `sysctl -n machdep.cpu.brand_string hw.ncpu hw.memsize`.

## Reproduction

```bash
sh scripts/assistant_stage_timing.sh --label carol-stage50 --requests 50 --warmup 2
# Use the fresh run directory printed by the command:
.venv/bin/python -m backend.assistant_trace_submission <run-directory> --output-dir <new-submission-directory>
```

Exact code hashes, model options, timeouts, workload and environment are in environment.json. Each reproduction creates new synthetic records and retains every measured failure/timeout; timing numbers are not deterministic.
