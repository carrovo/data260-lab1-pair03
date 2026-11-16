import httpx
import pytest
from pydantic import ValidationError

from backend.app.ai.ollama_client import OllamaClient
from backend.app.config import Settings, settings


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "message": {
                "content": "Model response",
                "tool_calls": None,
            }
        }


def capture_payload(monkeypatch):
    captured = {}

    class FakeHttpClient:
        def __init__(self, *, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def post(self, url, *, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeHttpClient)
    return captured


def complete_once(client):
    return client.complete(
        [{"role": "user", "content": "Find data jobs."}],
        [{"type": "function", "function": {"name": "search_jobs"}}],
    )


def test_unset_num_predict_does_not_add_an_override(monkeypatch):
    monkeypatch.setattr(settings, "ollama_num_predict", None)
    captured = capture_payload(monkeypatch)

    result = complete_once(OllamaClient())

    assert "num_predict" not in captured["json"]["options"]
    assert captured["json"]["think"] is False
    assert result == {
        "role": "assistant",
        "content": "Model response",
        "tool_calls": None,
        "usage": {"prompt_tokens": None, "completion_tokens": None,
                  "context_capacity": 4096, "capacity_source": "request.options.num_ctx", "source": "ollama"},
    }


def test_configured_num_predict_is_sent_as_an_integer(monkeypatch):
    monkeypatch.setattr(settings, "ollama_num_predict", 256)
    captured = capture_payload(monkeypatch)

    complete_once(OllamaClient())

    value = captured["json"]["options"]["num_predict"]
    assert value == 256
    assert isinstance(value, int)


def test_num_predict_preserves_existing_ollama_options(monkeypatch):
    monkeypatch.setattr(settings, "ollama_num_predict", 128)
    captured = capture_payload(monkeypatch)

    complete_once(OllamaClient())

    assert captured["json"]["options"] == {
        "temperature": 0.1,
        "num_ctx": 4096,
        "num_predict": 128,
    }
    assert captured["json"]["think"] is False


@pytest.mark.parametrize("value", ["0", "-1", "not-an-integer"])
def test_invalid_num_predict_environment_values_are_rejected(
    monkeypatch,
    value,
):
    monkeypatch.setenv("OLLAMA_NUM_PREDICT", value)

    with pytest.raises(ValidationError):
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            jwt_secret_key="test-only-secret",
            _env_file=None,
        )


def test_num_predict_setting_defaults_to_none(monkeypatch):
    monkeypatch.delenv("OLLAMA_NUM_PREDICT", raising=False)

    configured = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-only-secret",
        _env_file=None,
    )

    assert configured.ollama_num_predict is None
