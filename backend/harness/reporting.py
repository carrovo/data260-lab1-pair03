"""Safe, deterministic serialization for Agent harness evidence."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPORT_SCHEMA_VERSION = 1
MAX_SAFE_STRING_LENGTH = 4000
MAX_SAFE_COLLECTION_ITEMS = 100
MAX_SAFE_DEPTH = 8

_SENSITIVE_KEYS = (
    "access_token",
    "action_token",
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "database_url",
    "db_url",
    "email",
    "jwt",
    "password",
    "secret_key",
    "student_id",
)
_TOKEN_METRIC_KEYS = {
    "input_tokens",
    "output_tokens",
    "context_tokens",
}
_JWT_RE = re.compile(
    r"\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]+=*")
_DATABASE_URL_RE = re.compile(
    r"(?i)\b(?:mysql|mariadb|postgres(?:ql)?|sqlite)(?:\+[a-z0-9_]+)?://\S+"
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _sensitive_key(key: Any) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    if normalized in _TOKEN_METRIC_KEYS:
        return False
    return any(part in normalized for part in _SENSITIVE_KEYS)


def _safe_string(value: str) -> str:
    value = _JWT_RE.sub("[REDACTED_JWT]", value)
    value = _BEARER_RE.sub("Bearer [REDACTED]", value)
    value = _DATABASE_URL_RE.sub("[REDACTED_DATABASE_URL]", value)
    value = _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    if len(value) > MAX_SAFE_STRING_LENGTH:
        return value[:MAX_SAFE_STRING_LENGTH] + "...[TRUNCATED]"
    return value


def safe_value(value: Any, *, depth: int = 0) -> Any:
    """Return bounded JSON data with credentials and PII removed."""

    if depth >= MAX_SAFE_DEPTH:
        return "[TRUNCATED]"
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_SAFE_COLLECTION_ITEMS:
                result["[TRUNCATED]"] = "[TRUNCATED]"
                break
            safe_key = str(key)[:200]
            result[safe_key] = (
                "[REDACTED]"
                if _sensitive_key(key)
                else safe_value(item, depth=depth + 1)
            )
        return result
    if isinstance(value, (list, tuple)):
        items = [
            safe_value(item, depth=depth + 1)
            for item in value[:MAX_SAFE_COLLECTION_ITEMS]
        ]
        if len(value) > MAX_SAFE_COLLECTION_ITEMS:
            items.append("[TRUNCATED]")
        return items
    if isinstance(value, (bytes, bytearray)):
        return "[BINARY REDACTED]"
    if isinstance(value, str):
        return _safe_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _safe_string(str(value))


def make_report(
    results: Iterable[Any],
    *,
    label: str,
    persistence: str,
    commit_sha: str,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    ordered = sorted(results, key=lambda result: result.case_id)
    cases = [safe_value(result) for result in ordered]
    passed = sum(case["passed"] is True for case in cases)
    failed = len(cases) - passed
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run": {
            "label": label,
            "timestamp_utc": timestamp_utc
            or datetime.now(timezone.utc).isoformat(),
            "commit_sha": commit_sha,
            "persistence_mode": persistence,
            "model_client": "deterministic scripted/input-sensitive clients",
            "live_services_used": False,
            "required_cases": len(cases),
            "passed": passed,
            "failed": failed,
        },
        "cases": cases,
    }


def normalized_report(report: dict[str, Any]) -> dict[str, Any]:
    """Remove only timestamp and elapsed time for reproducibility checks."""

    normalized = json.loads(json.dumps(report, sort_keys=True))
    normalized["run"].pop("timestamp_utc", None)
    for case in normalized["cases"]:
        case.pop("elapsed_ms", None)
    return normalized


def _markdown(report: dict[str, Any]) -> str:
    run = report["run"]
    lines = [
        f"# Deterministic Agent Harness: {run['label']}",
        "",
        f"- Commit: `{run['commit_sha']}`",
        f"- Persistence: `{run['persistence_mode']}`",
        f"- Timestamp (UTC): `{run['timestamp_utc']}`",
        f"- Result: {run['passed']} passed, {run['failed']} failed",
        "- Live services used: no",
        "",
        "| Case | Category | Result | Guardrail | Tools | Retries | Iterations | Elapsed ms |",
        "|---|---|---:|---|---|---:|---:|---:|",
    ]
    for case in report["cases"]:
        tools = ", ".join(case["tool_names"]) or "none"
        guardrail = str(case["guardrail_outcome"]).replace("|", "\\|")
        lines.append(
            f"| {case['case_id']} | {case['category']} | "
            f"{'PASS' if case['passed'] else 'FAIL'} | {guardrail} | "
            f"{tools} | {case['retry_count']} | "
            f"{case['iteration_count']} | {case['elapsed_ms']:.3f} |"
        )
    lines.extend([
        "",
        "The JSON report contains the complete safe per-case evidence. "
        "JWTs, confirmation tokens, credentials, private PII, database URLs, "
        "and raw unbounded logs are intentionally excluded.",
        "",
    ])
    return "\n".join(lines)


def write_reports(
    report: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    label = report["run"]["label"]
    json_path = output_dir / f"agent_harness_{label}.json"
    markdown_path = output_dir / f"agent_harness_{label}.md"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path
