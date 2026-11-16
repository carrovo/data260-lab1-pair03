"""Command-line entry point for the deterministic Agent harness."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAFE_LABEL = re.compile(r"^[A-Za-z0-9._-]+$")


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic, offline Lab 2 Agent harness."
    )
    parser.add_argument("--persistence", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Output directory. Defaults to the ignored "
            "loadtest/temp/agent_harness/<label> directory."
        ),
    )
    return parser.parse_args(argv)


def _commit_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    if args.persistence != "sql":
        print(
            f"error: unsupported persistence mode '{args.persistence}'; "
            "this WIP checkpoint supports only 'sql'"
        )
        return 2
    if not SAFE_LABEL.fullmatch(args.label):
        print(
            "error: label may contain only letters, numbers, '.', '_' and '-'"
        )
        return 2

    # Force isolated process-local configuration before importing application
    # modules. No value is written to disk or inherited by another process.
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    os.environ["JWT_SECRET_KEY"] = "agent-harness-process-only-key"
    os.environ["PERSISTENCE"] = "sql"

    from .cases import run_required_cases
    from .reporting import make_report, write_reports

    output_dir = args.output_dir or (
        PROJECT_ROOT / "loadtest" / "temp" / "agent_harness" / args.label
    )
    results = run_required_cases(args.persistence)
    report = make_report(
        results,
        label=args.label,
        persistence=args.persistence,
        commit_sha=_commit_sha(),
    )
    json_path, markdown_path = write_reports(report, output_dir)

    for result in results:
        print(
            f"{'PASS' if result.passed else 'FAIL'} "
            f"{result.case_id}: {result.guardrail_outcome}"
        )
        for failure in result.assertion_failures:
            print(f"  - {failure}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    print(
        f"Result: {report['run']['passed']} passed, "
        f"{report['run']['failed']} failed"
    )
    return 0 if report["run"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
