"""Deterministic timing tests; fixture durations are not live performance evidence."""
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from backend.app.ai.ollama_client import ModelClient, OllamaClient
from backend.app.ai.usage import UsageModelClient
from backend.assistant_timing_report import analyze, nearest_rank
from backend.common.timing import RequestTiming, begin_request, end_request, timed_span
from backend.common.tracing import TraceMiddleware
from backend.harness.fixtures import HarnessContext, model_text, model_tool_call


def test_sql_cursor_spans_are_nested_and_query_contents_are_not_recorded():
    engine = create_engine('sqlite://')
    recorder, token, parent = begin_request('timing-sql', __import__('time').perf_counter())
    try:
        with timed_span('tool', 'search_jobs'):
            with engine.connect() as connection:
                connection.execute(text('SELECT :private'), {'private': 'PRIVATE_PAYLOAD'}).all()
        report = recorder.report(200)
    finally:
        end_request(token, parent); engine.dispose()
    assert report['tool_call_count'] == report['database_call_count'] == 1
    assert report['database_inside_tool_ms'] == report['database_elapsed_ms']
    assert report['database_elapsed_ms'] <= report['tool_elapsed_ms']
    database = next(s for s in report['spans'] if s['stage'] == 'database')
    tool = next(s for s in report['spans'] if s['stage'] == 'tool')
    assert database['parent_id'] == tool['id']
    assert report['queue_wait_ms'] is None
    assert 'PRIVATE_PAYLOAD' not in json.dumps(report) and 'SELECT' not in json.dumps(report)


def test_failed_database_cursor_is_measured_once():
    engine = create_engine('sqlite://')
    recorder, token, parent = begin_request('timing-db-fail', __import__('time').perf_counter())
    try:
        with pytest.raises(Exception):
            with timed_span('tool', 'search_jobs'):
                with engine.connect() as connection:
                    connection.execute(text('SELECT * FROM missing_synthetic_table'))
        report = recorder.report(200)
    finally:
        end_request(token, parent); engine.dispose()
    assert report['database_call_count'] == 1
    assert report['tool_call_count'] == 1
    assert report['errors'] == ['database_error', 'tool_error']
    assert 'missing_synthetic_table' not in json.dumps(report)


def test_model_and_real_tool_are_counted_once_through_production_agent():
    script = [model_tool_call('search_jobs', {}, call_id='timed-search'), model_text('Synthetic result')]
    reports = []
    context = HarnessContext(script)
    # Configure the existing middleware before TestClient builds the app stack.
    middleware = next(m for m in context.app.user_middleware if m.cls is TraceMiddleware)
    middleware.kwargs['timing_sink'] = reports.append
    with context:
        response = context.chat({'message': 'Find jobs'}, trace_id='timing-real-tool')
        assert response.status_code == 200
    assert len(reports) == 1
    observed = reports[0]
    assert observed['trace_id'] == response.headers['X-Trace-Id'] == 'timing-real-tool'
    assert observed['model_call_count'] == response.json()['usage']['model_calls'] == 2
    assert observed['tool_call_count'] == 1
    assert observed['database_call_count'] >= 1
    assert observed['native_inference_ms'] is None  # Fake-model timing is not Ollama inference.


def test_raised_and_safe_model_failures_are_timed_without_error_messages():
    class Failing(ModelClient):
        def complete(self, messages, tools): raise RuntimeError('PRIVATE_ERROR_MESSAGE')
    recorder, token, parent = begin_request('timing-model-fail', __import__('time').perf_counter())
    try:
        with pytest.raises(RuntimeError): UsageModelClient(Failing()).complete([], [])
        class SafeFailure(ModelClient):
            def complete(self, messages, tools):
                return {**model_text('Synthetic unavailable'), 'model_error': 'PRIVATE_ERROR_MESSAGE'}
        UsageModelClient(SafeFailure()).complete([], [])
        report = recorder.report(200)
    finally:
        end_request(token, parent)
    assert report['model_call_count'] == 2
    assert report['errors'] == ['model_backend_error', 'model_exception']
    assert report['native_inference_ms'] is None
    assert 'PRIVATE_ERROR_MESSAGE' not in json.dumps(report)


def test_native_inference_uses_only_actual_reported_durations(monkeypatch):
    original = httpx.Client
    def respond(request):
        return httpx.Response(200, json={'message': {'content': 'Ready'}, 'prompt_eval_count': 10, 'eval_count': 2,
            'prompt_eval_duration': 3_000_000, 'eval_duration': 5_000_000, 'load_duration': 20_000_000,
            'total_duration': 30_000_000})
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    recorder, token, parent = begin_request('timing-native-fixture', __import__('time').perf_counter())
    try:
        UsageModelClient(OllamaClient()).complete([], [])
        report = recorder.report(200)
    finally:
        end_request(token, parent)
    assert report['native_inference_ms'] == 8  # Excludes load/other server work.
    assert report['model_call_count'] == 1
    assert report['queue_wait_ms'] is None  # Never infer 30 - 20 - 3 - 5 as queue wait.


def test_http_failure_and_concurrent_requests_keep_correlated_private_free_reports():
    reports = []
    application = FastAPI()
    application.add_middleware(TraceMiddleware, service='timing-test', timing_sink=reports.append)
    @application.post('/assistant/chat')
    def endpoint():
        with timed_span('model', 'agent'):
            raise RuntimeError('PRIVATE_FAILURE')
    with TestClient(application, raise_server_exceptions=False) as client:
        def request(index):
            return client.post('/assistant/chat', headers={'X-Trace-Id': f'timing-concurrent-{index}'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(request, [1, 2]))
    assert all(response.status_code == 500 for response in responses)
    assert {r['trace_id'] for r in reports} == {'timing-concurrent-1', 'timing-concurrent-2'}
    assert all(r['model_call_count'] == 1 and r['request_error'] == 'request_error' for r in reports)
    assert 'PRIVATE_FAILURE' not in json.dumps(reports)


def test_span_budget_preserves_aggregate_counts_and_marks_truncation():
    recorder = RequestTiming('timing-budget')
    for _ in range(280):
        span = recorder.begin('database', 'mongo_command'); span.close(); span.close()
    report = recorder.report(200)
    assert report['database_call_count'] == 280
    assert len(report['spans']) == 256 and report['dropped_spans'] == 24


def test_summary_counts_all_fifty_including_errors_timeouts_and_does_not_add_nested_times():
    rows = [{'end_to_end_ms': index, 'outcome': 'success', 'timeout': False,
             'timing': {'model_elapsed_ms': 30, 'native_inference_ms': 20, 'tool_elapsed_ms': 10,
                        'database_elapsed_ms': 6, 'database_inside_tool_ms': 6,
                        'model_call_count': 2, 'tool_call_count': 1, 'database_call_count': 1}}
            for index in range(1, 51)]
    rows[0].update(outcome='safe_error')
    rows[-1].update(outcome='timeout', timeout=True, timing=None)
    report = analyze(rows)
    assert report['measured_requests'] == 50 and report['complete']
    assert (report['successes'], report['errors'], report['timeouts']) == (48, 1, 1)
    assert report['end_to_end_ms'] == {'p50': 25, 'p95': 48, 'p99': 50}
    assert report['stages']['tool_elapsed_ms']['total_ms'] == 490
    assert report['stages']['database_elapsed_ms']['total_ms'] == 294
    assert report['queue_wait_ms'] is None and nearest_rank([], 50) is None
    assert report['stages']['model_elapsed_ms']['available_requests'] == 49
