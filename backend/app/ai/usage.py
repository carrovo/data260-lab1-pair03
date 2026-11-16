"""Request-local numeric observations; never retain model inputs or outputs."""
import logging

from backend.app.ai.ollama_client import ModelClient
from backend.common.tracing import get_trace_id
from backend.common.timing import timed_span

# Reuse the existing trace/access logger and its configured safe sink.
logger = logging.getLogger("p03.http")


def count(value):
    return value if type(value) is int and value >= 0 else None


class UsageRecorder:
    def __init__(self):
        self.calls = []

    def record(self, metadata, purpose):
        data = metadata if isinstance(metadata, dict) else {}
        capacity = count(data.get("context_capacity")) or None
        item = {
            "index": len(self.calls) + 1, "purpose": purpose,
            "prompt_tokens": count(data.get("prompt_tokens")),
            "completion_tokens": count(data.get("completion_tokens")),
            "context_capacity": capacity,
            "source": data.get("source") if data.get("source") in {"ollama", "synthetic"} else "unknown",
            "capacity_source": "request.options.num_ctx" if data.get("capacity_source") == "request.options.num_ctx" else "unknown",
        }
        self.calls.append(item)
        logger.info("model_usage trace_id=%s call=%s purpose=%s prompt=%s completion=%s capacity=%s source=%s",
                    get_trace_id(), item["index"], purpose, item["prompt_tokens"],
                    item["completion_tokens"], capacity, item["source"])
        return item

    def report(self):
        def total(key):
            values = [item[key] for item in self.calls]
            return sum(values) if all(value is not None for value in values) else None

        latest = self.calls[-1] if self.calls else None
        context_tokens = (
            latest["prompt_tokens"] + latest["completion_tokens"]
            if latest and latest["prompt_tokens"] is not None and latest["completion_tokens"] is not None else None
        )
        capacity = latest["context_capacity"] if latest else None
        percent = context_tokens / capacity * 100 if context_tokens is not None and capacity else None
        prompt, completion = total("prompt_tokens"), total("completion_tokens")
        return {
            "calls": list(self.calls), "model_calls": len(self.calls),
            "prompt_tokens": prompt, "completion_tokens": completion,
            "total_tokens": prompt + completion if prompt is not None and completion is not None else None,
            "latest_context_tokens": context_tokens, "context_capacity": capacity,
            "context_percent": percent, "warning": percent is not None and percent > 70,
            "context_call_index": latest["index"] if latest else None,
            "capacity_source": latest["capacity_source"] if latest else "unknown",
            "context_source": "latest_call_prompt_plus_completion" if context_tokens is not None else "unknown",
            "context_is_estimate": percent is not None,
        }


class UsageModelClient(ModelClient):
    def __init__(self, delegate, recorder=None, purpose="agent"):
        self.delegate = delegate
        self.recorder = recorder if recorder is not None else UsageRecorder()
        self.purpose = purpose

    def complete(self, messages, tools):
        try:
            with timed_span("model", self.purpose) as span:
                response = self.delegate.complete(messages, tools)
                if span is not None:
                    span.observe_model(response)
        except Exception:
            self.recorder.record(None, self.purpose)
            raise
        self.recorder.record(response.get("usage") if isinstance(response, dict) else None, self.purpose)
        return response
