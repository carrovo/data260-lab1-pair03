"""Runtime tuning shared by every FastAPI service."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import anyio.to_thread
from fastapi import FastAPI

# FastAPI runs every plain `def` endpoint, and the clean-up of every `yield` dependency
# (get_db closing its session), on one shared pool of 40 threads. When all 40 threads are busy
# waiting for a database connection, the finished requests that would return a connection
# cannot get a thread to do it, and the service stalls until the pool timeout. A bigger thread
# pool than connection pool (20 + 20) removes that.
DEFAULT_THREADS = 120


def configure_threadpool(app: FastAPI) -> None:
    threads = int(os.environ.get("WORKER_THREADS", DEFAULT_THREADS))
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        anyio.to_thread.current_default_thread_limiter().total_tokens = threads
        async with original(application) as state:
            yield state

    app.router.lifespan_context = lifespan
