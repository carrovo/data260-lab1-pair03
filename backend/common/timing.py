"""Request-scoped monotonic timing. Spans contain no prompts, SQL, or DB payloads."""
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
import time

_current = ContextVar("p03_stage_timing", default=None)
_active = ContextVar("p03_stage_parent", default=None)
_install_lock = Lock()
_installed = False


class RequestTiming:
    def __init__(self, trace_id, started=None, clock=time.perf_counter):
        self.trace_id = trace_id
        self.clock = clock
        self.started = clock() if started is None else started
        self.spans = []
        self._next_id = 0
        self.lock = Lock()
        self.dropped_spans = 0
        self.totals = {stage: {"count": 0, "elapsed_ms": 0.0} for stage in ("model", "tool", "database")}
        self.native_total = 0.0
        self.native_unknown = False
        self.database_inside_tool_ms = 0.0
        self.tool_ids = set()
        self.errors = set()

    def begin(self, stage, operation=None):
        with self.lock:
            self._next_id += 1
            identity = self._next_id
            if stage == "tool":
                self.tool_ids.add(identity)
        parent = _active.get()
        parent_id = parent[1] if parent and parent[0] is self else None
        return Span(self, identity, parent_id, stage, operation)

    def finish(self, span, error):
        ended = self.clock()
        item = {"id": span.id, "parent_id": span.parent, "stage": span.stage,
                "operation": span.operation, "start_ms": (span.started - self.started) * 1000,
                "end_ms": (ended - self.started) * 1000,
                "elapsed_ms": max(0, (ended - span.started) * 1000), "error": error}
        if span.stage == "model":
            item["native_inference_ms"] = span.native_inference_ms
        with self.lock:
            total = self.totals[span.stage]
            if item["error"]:
                self.errors.add(item["error"])
            total["count"] += 1
            total["elapsed_ms"] += item["elapsed_ms"]
            if span.stage == "model":
                self.native_unknown |= span.native_inference_ms is None
                self.native_total += span.native_inference_ms or 0
            if span.stage == "database" and span.parent in self.tool_ids:
                self.database_inside_tool_ms += item["elapsed_ms"]
            # Current Agent limits produce far fewer spans; an overlong trace is
            # explicitly incomplete, never silently presented as full attribution.
            if len(self.spans) < 256:
                self.spans.append(item)
            else:
                self.dropped_spans += 1

    def report(self, status, request_error=False):
        with self.lock:
            spans = sorted(self.spans, key=lambda span: span["id"])
        models, tools, database = (self.totals[stage] for stage in ("model", "tool", "database"))
        return {
            "trace_id": self.trace_id, "http_status": status,
            "server_elapsed_ms": max(0, (self.clock() - self.started) * 1000),
            "model_elapsed_ms": models["elapsed_ms"], "model_call_count": models["count"],
            "native_inference_ms": None if self.native_unknown else self.native_total,
            "tool_elapsed_ms": tools["elapsed_ms"], "tool_call_count": tools["count"],
            "database_elapsed_ms": database["elapsed_ms"] if database["count"] else None,
            "database_call_count": database["count"],
            "database_inside_tool_ms": self.database_inside_tool_ms,
            "queue_wait_ms": None, "request_error": "request_error" if request_error else None,
            "errors": sorted(self.errors),
            "dropped_spans": self.dropped_spans, "spans": spans,
        }


class Span:
    def __init__(self, recorder, identity, parent, stage, operation):
        self.recorder, self.id, self.parent = recorder, identity, parent
        self.stage, self.operation = stage, operation
        self.started = recorder.clock()
        self.closed = False
        self.error = None
        self.native_inference_ms = None

    def observe_model(self, response):
        if not isinstance(response, dict):
            self.error = "invalid_model_response"
            return
        if response.get("model_error"):
            self.error = "model_backend_error"
        runtime = response.get("runtime") if isinstance(response.get("runtime"), dict) else {}
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        values = [runtime.get(key) for key in ("prompt_eval_duration", "eval_duration")]
        if (usage.get("source") == "ollama"
                and all(type(value) is int and value >= 0 for value in values)):
            self.native_inference_ms = sum(values) / 1_000_000

    def close(self, error=None):
        if not self.closed:
            self.closed = True
            self.recorder.finish(self, error or self.error)


@contextmanager
def timed_span(stage, operation=None):
    recorder = _current.get()
    if recorder is None:
        yield None
        return
    span = recorder.begin(stage, operation)
    token = _active.set((recorder, span.id))
    error = None
    try:
        yield span
    except Exception:
        error = {"model": "model_exception", "tool": "tool_error", "database": "database_error"}[stage]
        raise
    finally:
        span.close(error)
        _active.reset(token)


def begin_request(trace_id, started):
    recorder = RequestTiming(trace_id, started)
    return recorder, _current.set(recorder), _active.set(None)


def end_request(token, parent_token):
    _active.reset(parent_token)
    _current.reset(token)


def install_database_timing():
    """Public driver hooks. No query/command contents are inspected or logged."""
    global _installed
    with _install_lock:
        if _installed:
            return
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        def before(conn, cursor, statement, parameters, context, executemany):
            recorder = _current.get()
            context._p03_timing_span = recorder.begin("database", "sql_cursor") if recorder else None

        def after(conn, cursor, statement, parameters, context, executemany):
            span = getattr(context, "_p03_timing_span", None)
            if span:
                span.close()

        def failed(context):
            span = getattr(context.execution_context, "_p03_timing_span", None)
            if span:
                span.close("database_error")

        event.listen(Engine, "before_cursor_execute", before)
        event.listen(Engine, "after_cursor_execute", after)
        event.listen(Engine, "handle_error", failed)
        try:
            from pymongo import monitoring
        except ImportError:
            monitoring = None
        if monitoring is not None:
            class Commands(monitoring.CommandListener):
                def __init__(self):
                    self.pending = {}
                    self.lock = Lock()

                def started(self, event):
                    recorder = _current.get()
                    if recorder:
                        key = (event.connection_id, event.request_id)
                        with self.lock:
                            self.pending[key] = recorder.begin("database", "mongo_command")

                def succeeded(self, event):
                    self._close(event, None)

                def failed(self, event):
                    self._close(event, "database_error")

                def _close(self, event, error):
                    with self.lock:
                        span = self.pending.pop((event.connection_id, event.request_id), None)
                    if span:
                        span.close(error)

            monitoring.register(Commands())
        _installed = True
