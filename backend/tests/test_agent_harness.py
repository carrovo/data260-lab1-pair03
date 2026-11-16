import json
import re
from dataclasses import fields
from datetime import datetime, timezone

import pytest

from backend.harness import runner
from backend.harness.cases import (
    CASE_DEFINITIONS,
    REQUIRED_CASE_IDS,
    CaseResult,
    HarnessMutations,
    run_case,
    run_required_cases,
)
from backend.harness.fixtures import (
    ExternalServiceAccessError,
    HarnessContext,
    model_text,
)
from backend.harness.reporting import (
    make_report,
    normalized_report,
    safe_value,
    write_reports,
)


REQUIRED_EVIDENCE_FIELDS = {
    "case_id",
    "category",
    "safe_input",
    "assistant_messages",
    "tool_names",
    "sanitized_tool_arguments",
    "sanitized_tool_results",
    "final_answer",
    "guardrail_outcome",
    "errors",
    "retry_count",
    "iteration_count",
    "tool_call_count",
    "elapsed_ms",
    "passed",
    "trace_id_present",
    "persistence_mode",
    "expected_result",
    "actual_result",
    "input_tokens",
    "output_tokens",
    "context_tokens",
    "context_percent",
}


@pytest.fixture(scope="module")
def harness_results():
    return run_required_cases("sql")


def _by_id(results):
    return {result.case_id: result for result in results}


def test_exactly_ten_required_cases_exist_in_stable_order():
    assert len(REQUIRED_CASE_IDS) == 10
    assert tuple(definition.case_id for definition in CASE_DEFINITIONS) == REQUIRED_CASE_IDS


def test_every_required_evidence_field_is_present(harness_results):
    field_names = {field.name for field in fields(CaseResult)}
    assert REQUIRED_EVIDENCE_FIELDS <= field_names
    assert len(harness_results) == 10
    assert all(REQUIRED_EVIDENCE_FIELDS <= result.__dict__.keys() for result in harness_results)


def test_results_are_sorted_and_every_required_case_ran(harness_results):
    ids = [result.case_id for result in harness_results]
    assert ids == sorted(REQUIRED_CASE_IDS)
    assert set(ids) == set(REQUIRED_CASE_IDS)
    assert all(result.passed is True for result in harness_results)


def test_each_case_has_isolated_sql_state(harness_results):
    results = _by_id(harness_results)
    assert results["H02_ACCEPT_WRITE"].details["saved_item_count"] == 1
    assert results["H03_DECLINE_WRITE"].details["saved_item_count"] == 0
    assert all(result.persistence_mode == "sql" for result in harness_results)


def test_external_network_is_blocked_by_the_case_fixture():
    import socket

    with HarnessContext([model_text("safe")]):
        with pytest.raises(ExternalServiceAccessError):
            socket.create_connection(("127.0.0.1", 11434))


def test_safe_serialization_redacts_credentials_pii_and_database_urls():
    unsafe = {
        "action_token": "opaque-confirmation-value",
        "student_id": 42,
        "message": (
            "Bearer private-token student@private.example.com "
            "mysql://user:password@db/private "
            "aaaaaaaa.bbbbbbbb.cccccccc"
        ),
        "input_tokens": None,
    }
    serialized = json.dumps(safe_value(unsafe), sort_keys=True)
    assert "opaque-confirmation-value" not in serialized
    assert "student@private.example.com" not in serialized
    assert "mysql://" not in serialized
    assert "aaaaaaaa.bbbbbbbb.cccccccc" not in serialized
    assert '"input_tokens": null' in serialized


def test_confirmation_and_tool_guardrail_counts(harness_results):
    results = _by_id(harness_results)
    accepted = results["H02_ACCEPT_WRITE"]
    declined = results["H03_DECLINE_WRITE"]
    malformed = results["H04_MALFORMED_ARGUMENTS"]
    unknown = results["H05_UNKNOWN_TOOL"]

    assert accepted.details["saved_item_count"] == 1
    assert accepted.details["tool_execution_count"] == 1
    assert accepted.actual_result["confirmation_state"] == "approved"
    assert accepted.actual_result["requested_confirmation_decisions"] == [True]
    assert accepted.actual_result["confirmation_token_attempt_count"] == 1
    assert accepted.actual_result["issued_confirmation_token_count"] == 1
    assert accepted.actual_result["observed_confirmation_outcome"] == "approved"
    assert accepted.actual_result["database_write_count"] == 1
    assert declined.details["saved_item_count"] == 0
    assert declined.details["tool_execution_count"] == 0
    assert declined.actual_result["confirmation_state"] == "declined"
    assert declined.actual_result["requested_confirmation_decisions"] == [False]
    assert declined.actual_result["issued_confirmation_token_count"] == 1
    assert malformed.details["tool_execution_count"] == 0
    assert malformed.actual_result["confirmation_token_attempt_count"] == 0
    assert malformed.actual_result["repair_count"] == 1
    assert malformed.actual_result["error_type"] == (
        "typed_argument_validation"
    )
    assert unknown.details["tool_execution_count"] == 0


def test_recovery_has_one_retry_and_bounded_stop_uses_the_limit(harness_results):
    results = _by_id(harness_results)
    recovery = results["H10_RECOVERY_RETRY"]
    bounded = results["H09_BOUNDED_STOP"]
    assert recovery.retry_count == 1
    assert recovery.tool_call_count == 2
    assert recovery.iteration_count == 3
    assert bounded.iteration_count == bounded.details["configured_iteration_limit"]
    assert bounded.tool_call_count == bounded.details["configured_iteration_limit"]


def test_wrong_saved_row_observation_fails_h02():
    result = run_case(
        "H02_ACCEPT_WRITE",
        mutations=HarnessMutations(h02_saved_count_override=0),
    )
    assert result.passed is False
    assert result.actual_result["database_write_count"] == 0
    assert any(
        "exactly one saved item" in item
        for item in result.assertion_failures
    )


def test_missing_production_trace_header_fails_case():
    result = run_case(
        "H01_READ_SEARCH",
        mutations=HarnessMutations(drop_trace_case="H01_READ_SEARCH"),
    )
    assert result.passed is False
    assert result.trace_id_present is False
    assert result.actual_result["trace_headers"] == [None]


def test_raw_model_visible_injection_fails_h08():
    result = run_case(
        "H08_PROMPT_INJECTION",
        mutations=HarnessMutations(h08_disable_sanitizer=True),
    )
    assert result.passed is False
    assert result.actual_result["error_type"] == (
        "raw_prompt_injection_reached_model"
    )
    assert "ignore all previous instructions" in (
        result.actual_result["model_visible_tool_messages"][0].lower()
    )


def test_extra_repair_observation_fails_h10():
    result = run_case(
        "H10_RECOVERY_RETRY",
        mutations=HarnessMutations(h10_inject_extra_repair=True),
    )
    assert result.passed is False
    assert result.actual_result["repair_count"] == 2
    assert result.retry_count == 2


def test_missing_first_turn_context_fails_h07():
    result = run_case(
        "H07_HISTORY_FOLLOWUP",
        mutations=HarnessMutations(h07_drop_first_context=True),
    )
    assert result.passed is False
    assert result.actual_result["error_type"] == "history_context_missing"
    assert result.final_answer == "HISTORY_CONTEXT_MISSING"


def test_malformed_arguments_reaching_confirmation_fails_h04():
    result = run_case(
        "H04_MALFORMED_ARGUMENTS",
        mutations=HarnessMutations(h04_disable_typed_validation=True),
    )
    assert result.passed is False
    assert result.actual_result["confirmation_token_attempt_count"] == 1
    assert result.actual_result["issued_confirmation_token_count"] == 0
    assert result.actual_result["observed_confirmation_outcome"] == "not_requested"
    assert result.actual_result["repair_count"] == 0
    assert result.actual_result["database_write_count"] == 0


def test_runner_returns_nonzero_for_a_corrupted_production_observation(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        "backend.harness.cases.run_required_cases",
        lambda _persistence: run_required_cases(
            "sql",
            mutations=HarnessMutations(
                h04_disable_typed_validation=True,
            ),
        ),
    )
    exit_code = runner.main([
        "--persistence",
        "sql",
        "--label",
        "failure-check",
        "--output-dir",
        str(tmp_path),
    ])
    assert exit_code == 1


def test_h07_uses_client_carried_history_from_two_http_requests(
    harness_results,
):
    result = _by_id(harness_results)["H07_HISTORY_FOLLOWUP"]
    assert result.expected_result["outcome"] == "client_carried_history"
    assert result.actual_result["http_statuses"] == [200, 200]
    assert result.actual_result["http_request_count"] == 2
    assert result.actual_result["model_call_count"] == 4
    assert result.actual_result["observed_behavior"] == (
        "client_carried_history"
    )
    assert result.guardrail_outcome == "client_carried_history"
    second_request_messages = result.actual_result["model_calls"][2][
        "messages"
    ]
    assert any(
        message.get("role") == "assistant"
        and "Data Analyst Intern" in message.get("content", "")
        and "job #" in message.get("content", "")
        for message in second_request_messages
    )
    assert result.details["history_behavior"] == "client_carried_history"
    assert result.details["server_persistent_memory"] is False


def test_h08_reports_exact_model_visible_defended_message(harness_results):
    result = _by_id(harness_results)["H08_PROMPT_INJECTION"]
    visible = result.actual_result["model_visible_tool_messages"]
    assert visible == [result.defense_evidence["after_defense"]]
    assert "<UNTRUSTED_DATABASE_CONTENT" in visible[0]
    assert "Unsafe instruction-like content removed" in visible[0]
    assert "ignore all previous instructions" not in visible[0].lower()
    assert result.actual_result["observed_behavior"] == (
        "prompt_injection_defended"
    )


def test_normalized_repeat_runs_are_identical(monkeypatch):
    monkeypatch.setattr("backend.app.ai.agent._utc_now",
                        lambda: datetime(2026, 11, 16, tzinfo=timezone.utc))
    first = make_report(
        run_required_cases("sql"),
        label="repeat",
        persistence="sql",
        commit_sha="fixed-sha",
        timestamp_utc="2030-01-01T00:00:00+00:00",
    )
    second = make_report(
        run_required_cases("sql"),
        label="repeat",
        persistence="sql",
        commit_sha="fixed-sha",
        timestamp_utc="2031-01-01T00:00:00+00:00",
    )
    assert normalized_report(first) == normalized_report(second)


def test_temporary_json_and_markdown_are_created_safely(harness_results, tmp_path):
    report = make_report(
        harness_results,
        label="pytest",
        persistence="sql",
        commit_sha="fixed-sha",
    )
    json_path, markdown_path = write_reports(report, tmp_path)
    assert json_path == tmp_path / "agent_harness_pytest.json"
    assert markdown_path == tmp_path / "agent_harness_pytest.md"
    payload = json_path.read_text(encoding="utf-8")
    assert len(json.loads(payload)["cases"]) == 10
    assert not re.search(
        r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
        payload,
    )
    assert "mysql://" not in payload
    assert "@harness.invalid" not in payload


def test_unsupported_persistence_is_rejected():
    with pytest.raises(ValueError, match="supports only 'sql'"):
        run_required_cases("mongo")
