"""Summarize measured requests without adding overlapping inclusive stages."""
import math
import statistics


def nearest_rank(values, percentile):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(percentile / 100 * len(ordered)) - 1]


def analyze(rows, expected=50):
    elapsed = [row["end_to_end_ms"] for row in rows]
    stages = {}
    for key in ("model_elapsed_ms", "native_inference_ms", "tool_elapsed_ms", "database_elapsed_ms", "database_inside_tool_ms"):
        values = [row["timing"][key] for row in rows if row.get("timing") and row["timing"].get(key) is not None]
        stages[key] = {"available_requests": len(values), "total_ms": sum(values) if values else None,
                       "mean_available_ms": statistics.mean(values) if values else None}
    candidates = {key: stages[key]["total_ms"] for key in ("model_elapsed_ms", "tool_elapsed_ms", "database_elapsed_ms")
                  if stages[key]["available_requests"] == len(rows) and rows}
    dominant = max(candidates, key=candidates.get) if candidates else "unavailable"
    return {
        "expected_requests": expected, "measured_requests": len(rows), "complete": len(rows) == expected,
        "successes": sum(row["outcome"] == "success" for row in rows),
        "errors": sum(row["outcome"] != "success" and not row["timeout"] for row in rows),
        "timeouts": sum(row["timeout"] for row in rows),
        "end_to_end_ms": {f"p{p}": nearest_rank(elapsed, p) for p in (50, 95, 99)},
        "stages": stages, "dominant_inclusive_measured_stage": dominant,
        "model_calls": sum(row.get("timing", {}).get("model_call_count", 0) for row in rows if row.get("timing")),
        "tool_calls": sum(row.get("timing", {}).get("tool_call_count", 0) for row in rows if row.get("timing")),
        "database_calls": sum(row.get("timing", {}).get("database_call_count", 0) for row in rows if row.get("timing")),
        "requests_with_timing": sum(row.get("timing") is not None for row in rows),
        "queue_wait_ms": None,
        "overlap": "Inclusive DB command/cursor spans can be nested in tools; native inference is inside model-call wall time. These rows are not additive. No residual is called queue wait.",
    }


def markdown(summary, environment):
    def number(value):
        return "unavailable" if value is None else f"{value:.3f}"
    lines = ["# Assistant trace and stage timing (Carol)", "",
             f"UTC start: `{environment['timestamp_utc']}`; base `{environment['commit_sha']}` plus source hashes in environment.json.",
             "Actual network HTTP to a new loopback Uvicorn instance; production auth/Assistant/Agent/tools; live host Ollama and real Mongo in a new synthetic namespace. Not in-process ASGI or deterministic-model timing.", "",
             f"Workload: {environment['workload']}",
             f"Concurrency 1; {environment['warmup_requests']} warm-ups excluded; {summary['measured_requests']} measured of {summary['expected_requests']} requested. No client retries or replacement requests.",
             f"Model `{environment['model']}`, num_ctx={environment['num_ctx']}, num_predict={environment['num_predict']}, think=false, temperature=0.1.",
             f"Model-call timeout {environment['model_timeout_seconds']}s; client HTTP timeout {environment['http_timeout_seconds']}s.", "",
             f"Successes: **{summary['successes']}**; errors: **{summary['errors']}**; timeouts: **{summary['timeouts']}**. Complete: `{summary['complete']}`.",
             "All measured outcomes, including errors/timeouts, participate in end-to-end percentiles (standard nearest-rank).", "",
             "| End-to-end ms | p50 | p95 | p99 |", "|---|---:|---:|---:|",
             "| All measured requests | " + " | ".join(number(summary['end_to_end_ms'][f'p{p}']) for p in (50, 95, 99)) + " |", "",
             "| Measured stage (inclusive) | Total ms | Mean available/request ms | Coverage |", "|---|---:|---:|---:|"]
    for key, value in summary["stages"].items():
        lines.append(f"| {key} | {number(value['total_ms'])} | {number(value['mean_available_ms'])} | {value['available_requests']}/{summary['measured_requests']} |")
    lines += ["", f"Largest fully covered inclusive stage: **{summary['dominant_inclusive_measured_stage']}**.",
              f"Observed calls: model {summary['model_calls']}, tools {summary['tool_calls']}, database {summary['database_calls']}.",
              summary["overlap"], "",
              "Model wall time includes client serialization, connection/network, Ollama scheduling/load and inference. Native inference is directly reported prompt_eval_duration + eval_duration; it excludes load and is unavailable on failed/missing metadata.",
              "Database spans directly time Mongo commands or SQL cursor execution, not full repository/materialization time or connection-pool wait. Other uninstrumented time remains unattributed.",
              "Queue wait: **unavailable**. No queue attribution is inferred from client/server differences or stage subtraction.", "",
              "success_trace.json includes an actual read-only tool execution and sanitized response. failure_trace.json is a separate injected model-connect failure on this isolated instance, outside the 50-request workload; HTTP status and safe Agent outcome are reported separately.",
              "No shared service was stopped/reconfigured. No real student, credentials, JWTs, confirmation tokens, private prompts, SQL or Mongo command contents are included.",
              "This sequential attribution experiment does not replace JMeter concurrency levels or establish deployed/AWS/browser performance. Shared host/model activity can affect results.", ""]
    return "\n".join(lines)
