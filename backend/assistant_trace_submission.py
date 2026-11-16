"""Validate and copy a complete sanitized timing run; never alter raw evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from backend.assistant_timing_report import analyze

FILES = ("environment.json", "warmup.jsonl", "measurements.jsonl", "analysis.json",
         "success_trace.json", "failure_trace.json", "summary.md")
PRIVATE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
    r"|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    r"|(?:mongodb(?:\+srv)?|mysql(?:\+pymysql)?)://[^\s/:]+:[^\s@]+@"
)


def validate(source):
    names = FILES + (("host_observation.json",) if (source / "host_observation.json").exists() else ())
    for name in names:
        content = (source / name).read_text()
        if PRIVATE.search(content):
            raise ValueError("sensitive_output_rejected")
    environment = json.loads((source / "environment.json").read_text())
    rows = [json.loads(line) for line in (source / "measurements.jsonl").read_text().splitlines() if line.strip()]
    if len(rows) != 50 or [row["index"] for row in rows] != list(range(1, 51)):
        raise ValueError("exactly_fifty_ordered_requests_required")
    if len({row["trace_id"] for row in rows}) != 50 or any(row["phase"] != "measured" for row in rows):
        raise ValueError("duplicate_or_nonmeasured_trace")
    for row in rows:
        report = row.get("timing")
        if report is not None:
            if row["trace_id"] != report["trace_id"] or report["dropped_spans"]:
                raise ValueError("uncorrelated_or_truncated_trace")
            for stage in ("model", "tool", "database"):
                if report[f"{stage}_call_count"] != sum(span["stage"] == stage for span in report["spans"]):
                    raise ValueError("span_count_mismatch")
            if report["queue_wait_ms"] is not None:
                raise ValueError("unexpected_queue_claim")
    if json.loads((source / "analysis.json").read_text()) != analyze(rows, expected=50):
        raise ValueError("aggregate_not_reproducible")
    for name, digest in environment["source_sha256"].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise ValueError("runtime_source_changed_since_run")
    return environment, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    environment, rows = validate(args.source)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    names = FILES + (("host_observation.json",) if (args.source / "host_observation.json").exists() else ())
    for name in names:
        shutil.copyfile(args.source / name, args.output_dir / name)
    manifest = {name: hashlib.sha256((args.source / name).read_bytes()).hexdigest() for name in names}
    (args.output_dir / "sha256.json").write_text(json.dumps(manifest, indent=2) + "\n")
    lines = ["# Successful and controlled-failure Assistant traces", "",
             "Actual loopback network HTTP; live Ollama and Mongo; isolated production auth/router/Agent/tool paths. Sanitized response observations, not raw authorization headers or prompts.", ""]
    for title, filename in (("Successful read-only trace", "success_trace.json"),
                            ("Controlled failed trace (outside the 50)", "failure_trace.json")):
        row = json.loads((args.source / filename).read_text())
        report = row["timing"]
        lines += [f"## {title}", "", f"Trace `{row['trace_id']}`; echoed `{row['echoed_trace_id']}`.",
                  f"HTTP **{row['http_status']}**, application outcome **{row['outcome']}**; injected `{row['injected_failure']}`.",
                  f"Observed response: {row['response']['reply']}",
                  f"Client end-to-end {row['end_to_end_ms']:.3f} ms; server request lifecycle {report['server_elapsed_ms']:.3f} ms.",
                  f"Calls: model {report['model_call_count']}, tool {report['tool_call_count']}, direct DB {report['database_call_count']}; errors `{report['errors']}`.",
                  "", "| Span | Parent | Stage/operation | Start ms | End ms | Inclusive ms | Error |",
                  "|---:|---:|---|---:|---:|---:|---|"]
        for span in report["spans"]:
            lines.append(f"| {span['id']} | {span['parent_id'] if span['parent_id'] is not None else '-'} | {span['stage']}/{span['operation']} | {span['start_ms']:.3f} | {span['end_ms']:.3f} | {span['elapsed_ms']:.3f} | {span['error'] or '-'} |")
        lines += ["", "DB child spans are already inside their tool parent; native prompt/decode inference is inside model wall time. Do not add inclusive stages. Queue wait is unavailable.", ""]
    if (args.source / "host_observation.json").exists():
        observation = json.loads((args.source / "host_observation.json").read_text())
        lines += ["## Shared-host environment observation", "", observation["background_activity"],
                  f"CPU {observation['cpu']}; logical cores {observation['logical_cpu_cores']}; RAM {observation['ram_bytes']} bytes. Hardware source: `{observation['hardware_source']}`.", ""]
    lines += ["## Reproduction", "", "```bash",
              "sh scripts/assistant_stage_timing.sh --label carol-stage50 --requests 50 --warmup 2",
              "# Use the fresh run directory printed by the command:",
              ".venv/bin/python -m backend.assistant_trace_submission <run-directory> --output-dir <new-submission-directory>",
              "```", "", "Exact code hashes, model options, timeouts, workload and environment are in environment.json. Each reproduction creates new synthetic records and retains every measured failure/timeout; timing numbers are not deterministic.", ""]
    (args.output_dir / "traces.md").write_text("\n".join(lines))
    print(json.dumps({"output": str(args.output_dir), "measured_requests": len(rows), "source_files_verified": len(environment["source_sha256"])}))


if __name__ == "__main__":
    main()
