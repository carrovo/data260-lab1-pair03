# Assistant load-test summary (2026-11-13-pr3-assistant)

Generated from `loadtest/assistant_2026-11-13-pr3-assistant_<users>.jtl` with:

`python3 loadtest/summarize.py assistant 2026-11-13-pr3-assistant --test-environment 'Docker Compose on Apple M4 MacBook Air (10 CPU cores, 16 GB RAM); Assistant container reached host Ollama via http://host.docker.internal:11434' --ollama-version 0.40.6 --model qwen3:8b`

The runner uses 5, 10, 20 and 50 users, a 5-second ramp-up, 3 loops and 500 ms think time. Percentiles use the standard nearest-rank method and include every `Assistant chat` sample, including unsuccessful samples.

## Test environment

- System: Docker Compose on Apple M4 MacBook Air (10 CPU cores, 16 GB RAM); Assistant container reached host Ollama via http://host.docker.internal:11434
- Ollama: 0.40.6
- Model: `qwen3:8b`

| Concurrent users | Assistant samples | Successes | Errors | Success rate | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (req/s) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 15 | 15 | 0 | 100.00% | 36933 | 47537 | 47537 | 0.12 |
| 10 | 30 | 30 | 0 | 100.00% | 62071 | 66259 | 67428 | 0.15 |
| 20 | 60 | 60 | 0 | 100.00% | 120492 | 124361 | 126213 | 0.16 |
| 50 | 150 | 120 | 30 | 80.00% | 240693 | 289255 | 299736 | 0.19 |

## Observed errors

| Concurrent users | Count | Response code | Response message |
|---:|---:|---|---|
| 50 | 20 | 500 | Internal Server Error |
| 50 | 10 | Non HTTP response code: org.apache.http.NoHttpResponseException | Non HTTP response message: localhost:9035 failed to respond |

## Interpretation

Saturation begins at 10 users: p50 rises from 36933 ms to 62071 ms while throughput increases only from 0.12 to 0.15 req/s, well below linear scaling.
The 50-user level is not reliable in this environment: 30 of 150 Assistant requests failed (20.00% error rate).
