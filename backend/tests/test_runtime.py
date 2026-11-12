import anyio.to_thread
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common.runtime import configure_threadpool


def test_startup_raises_the_thread_limit(monkeypatch):
    monkeypatch.setenv("WORKER_THREADS", "77")
    app = FastAPI()
    configure_threadpool(app)
    seen = {}

    @app.get("/limit")
    async def limit():
        seen["tokens"] = anyio.to_thread.current_default_thread_limiter().total_tokens
        return {}

    with TestClient(app) as client:
        client.get("/limit")
    assert seen["tokens"] == 77
