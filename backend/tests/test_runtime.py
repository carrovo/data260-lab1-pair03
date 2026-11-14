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


def test_health_checks_run_on_the_event_loop_not_the_worker_pool():
    """A sync /health waits for a free worker thread. Under a login burst (bcrypt)
    that wait exceeded the Kubernetes probe timeout and the pod was restarted."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    mains = [root / "app" / "main.py", *sorted((root / "services").glob("*/main.py"))]
    assert len(mains) == 7
    for main in mains:
        text = main.read_text()
        assert "async def health_check" in text, main
        assert "\ndef health_check" not in text, main
