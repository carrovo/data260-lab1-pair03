"""Model client interface and the application's only Ollama transport."""

from abc import ABC, abstractmethod
from copy import copy, deepcopy
from typing import Any

import httpx

from backend.app.config import settings


class ModelClient(ABC):
    """Interface implemented by real and deterministic model clients."""

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return assistant content and optional tool calls."""

    @property
    def context_capacity(self):
        return None  # An unsupported client must not imply a model context size.

    @property
    def output_limit(self):
        return None

    def prepare_messages(self, messages):
        """Preview model-visible messages for offline budgeting, without inference."""
        return deepcopy(messages)

    def with_response_schema(self, schema: dict[str, Any], *, num_predict=None):
        """Optional native constraint; unsupported clients still require validation."""
        return self


class OllamaClient(ModelClient):
    """Synchronous Ollama implementation backed by the existing httpx dependency."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 240.0,
    ):
        self.base_url = (
            base_url or settings.ollama_base_url
        ).rstrip("/")
        self.model = model or settings.ollama_model
        self.num_predict = settings.ollama_num_predict
        self.num_ctx = settings.ollama_num_ctx
        self.response_schema = None
        self.timeout = httpx.Timeout(
            timeout_seconds,
            connect=10.0,
        )

    @property
    def context_capacity(self):
        return self.num_ctx

    @property
    def output_limit(self):
        return self.num_predict

    def with_response_schema(self, schema: dict[str, Any], *, num_predict=None):
        # A per-call copy prevents format settings leaking into probes/chat or
        # concurrent calls using the original client.
        configured = copy(self)
        configured.response_schema = deepcopy(schema)
        if num_predict is not None:
            if type(num_predict) is not int or num_predict <= 0:
                raise ValueError("invalid_output_budget")
            configured.num_predict = num_predict
        return configured

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        options = {
            "temperature": 0.1,
            "num_ctx": self.num_ctx,
        }
        if self.num_predict is not None:
            options["num_predict"] = self.num_predict

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "think": False,
            "options": options,
        }

        if self.response_schema is not None:
            payload["format"] = deepcopy(self.response_schema)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError):
            return {
                "role": "assistant",
                "content": "[model backend unavailable]",
                "tool_calls": None,
                "model_error": "backend_unavailable",
                "usage": {"prompt_tokens": None, "completion_tokens": None,
                          "context_capacity": self.num_ctx, "capacity_source": "request.options.num_ctx", "source": "unknown"},
            }

        message = data.get("message", {})
        result = {
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls"),
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count"),
                "completion_tokens": data.get("eval_count"),
                "context_capacity": self.num_ctx,
                "capacity_source": "request.options.num_ctx", "source": "ollama",
            },
        }
        keys = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")
        if any(key in data for key in keys):
            result["runtime"] = {key: data.get(key) for key in keys}
        return result


class FakeModelClient(ModelClient):
    """Deterministic scripted client used by tests without network access."""

    def __init__(self, script: list[dict[str, Any]] | None = None):
        self.script = script or []
        self.calls: list[dict[str, Any]] = []
        self._index = 0

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.calls.append({
            "messages": deepcopy(messages),
            "tools": deepcopy(tools),
        })

        if self._index < len(self.script):
            turn = self.script[self._index]
            self._index += 1
            return deepcopy(turn)

        return {
            "role": "assistant",
            "content": "(fake model: no more scripted turns)",
            "tool_calls": None,
        }
