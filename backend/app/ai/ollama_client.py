"""Model client interface and the application's only Ollama transport."""

from abc import ABC, abstractmethod
from copy import deepcopy
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
        self.timeout = httpx.Timeout(
            timeout_seconds,
            connect=10.0,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "role": "assistant",
                "content": f"[model backend unreachable: {exc}]",
                "tool_calls": None,
            }

        message = data.get("message", {})
        return {
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls"),
        }


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
