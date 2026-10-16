"""
The ONE place in the application allowed to talk to Ollama directly.
Everything else (the agent loop, the chat endpoint) goes through
ModelClient.complete(messages, tools) — never calls Ollama itself.
"""
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import requests

from app.config import OLLAMA_HOST, OLLAMA_MODEL


class ModelClient(ABC):
    """Interface every model backend must implement."""

    @abstractmethod
    def complete(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Returns a dict shaped like:
          {"role": "assistant", "content": "<text or None>", "tool_calls": [...] or None}
        tool_calls, when present, is a list of:
          {"id": str, "function": {"name": str, "arguments": dict}}
        """
        raise NotImplementedError


class OllamaClient(ModelClient):
    def __init__(
        self,
        host: str = OLLAMA_HOST,
        model: str = OLLAMA_MODEL,
        timeout: int = 240,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        url = f"{self.host}/api/chat"

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,

            # Qwen3 can spend a long time reasoning before simple
            # tool-selection calls. The lab agent does not need that.
            "think": False,

            # Keep generation predictable and reasonably small.
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096,
            },
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=(10, self.timeout),
            )

            resp.raise_for_status()

        except requests.RequestException as exc:
            return {
                "role": "assistant",
                "content": f"[model backend unreachable: {exc}]",
                "tool_calls": None,
            }

        data = resp.json()
        message = data.get("message", {})

        return {
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls"),
        }


class FakeModelClient(ModelClient):
    """
    Deterministic stand-in used for local testing without Ollama running.
    Not used in the real assistant — swap OllamaClient back in for actual
    transcripts. Useful to sanity-check the loop/tool wiring quickly.
    """

    def __init__(self, script: Optional[List[Dict[str, Any]]] = None):
        self.script = script or []
        self._i = 0

    def complete(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self._i < len(self.script):
            turn = self.script[self._i]
            self._i += 1
            return turn
        return {"role": "assistant", "content": "(fake model: no more scripted turns)", "tool_calls": None}
