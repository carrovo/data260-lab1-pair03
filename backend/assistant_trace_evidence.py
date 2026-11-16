"""Live, sequential Assistant stage evidence over real loopback network HTTP.

Fresh synthetic Mongo namespace; production routers/Agent/tools/native Ollama.
The sole injected failure overrides the client endpoint only on this local app.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
from threading import Lock, Thread
import time
from urllib.parse import quote
from uuid import uuid4

from backend.assistant_timing_report import analyze, markdown

TITLE = "Pair03 Trace Data Intern"
WORKLOAD = f"Find jobs titled {TITLE} in San Jose using search_jobs. Reply with only the matching title and city."


class Reports:
    def __init__(self):
        self.lock = Lock()
        self.rows = {}

    def __call__(self, report):
        with self.lock:
            self.rows[report["trace_id"]] = report

    def wait(self, trace_id, timeout=10):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            with self.lock:
                report = self.rows.pop(trace_id, None)
            if report is not None:
                return report
            time.sleep(0.01)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="carol-stage50")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--model-timeout", type=float, default=60)
    parser.add_argument("--http-timeout", type=float, default=420)
    parser.add_argument("--output-root", default="loadtest/temp/assistant_trace")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,24}", args.label) or not 1 <= args.requests <= 50 or not 0 <= args.warmup <= 5:
        parser.error("label: 1-24 lowercase letters/digits/hyphens; requests: 1-50; warmup: 0-5")
    if args.model_timeout <= 0 or args.http_timeout < 6 * args.model_timeout + 30:
        parser.error("positive model timeout; HTTP timeout must cover six calls plus 30s")

    # Existing private connection configuration stays in process memory only.
    info = json.loads(subprocess.check_output(["docker", "inspect", "p03-mongo"], stderr=subprocess.DEVNULL))[0]
    private_env = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    user, password = private_env.get("MONGO_INITDB_ROOT_USERNAME"), private_env.get("MONGO_INITDB_ROOT_PASSWORD")
    auth = f"{quote(user, safe='')}:{quote(password, safe='')}@" if user and password else ""
    suffix = uuid4().hex[:10]
    namespace = f"p03_trace_{args.label.replace('-', '_')}_{suffix}"
    os.environ.update({"DATABASE_URL": "sqlite+pysqlite:///:memory:", "PERSISTENCE": "mongo",
                       "JWT_SECRET_KEY": "synthetic-trace-evidence-local-only",
                       "MONGO_URL": f"mongodb://{auth}127.0.0.1:9038/?authSource=admin",
                       "MONGO_DB": namespace, "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                       "OLLAMA_NUM_CTX": "4096", "OLLAMA_NUM_PREDICT": "128"})
    import httpx
    import uvicorn
    from fastapi import FastAPI, Request
    from pymongo import MongoClient
    from backend.common.timing import install_database_timing
    install_database_timing()
    from backend.common.tracing import TraceMiddleware
    from backend.common.runtime import configure_threadpool
    from backend.common.mongo_store import CompanyStore, JobStore
    from backend.common.assistant_memory import public_text
    from backend.app.routers import student_auth, assistant
    from backend.app.ai.ollama_client import OllamaClient
    from backend.app.config import settings

    tags = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5).json()
    if not any(model.get("name") == settings.ollama_model for model in tags.get("models", [])):
        raise RuntimeError("required_model_not_installed")
    mongo = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=3000)
    mongo.admin.command("ping")
    mongo_version = mongo.admin.command("buildInfo")["version"]
    database = mongo[namespace]
    company = CompanyStore(database).create(email="trace-company@example.com", password_hash="[UNUSED SYNTHETIC HASH]",
                                           name="Pair03 Trace Company", city="San Jose")
    job = JobStore(database).create(company.id, title=TITLE, description="Synthetic read-only timing fixture.", city="San Jose")

    output = Path(args.output_root) / f"{args.label}-{suffix}"
    output.mkdir(parents=True, exist_ok=False)
    source_paths = ["backend/common/timing.py", "backend/common/tracing.py", "backend/app/ai/agent.py",
                    "backend/app/ai/usage.py", "backend/app/ai/ollama_client.py", "backend/app/routers/assistant.py",
                    "backend/assistant_trace_evidence.py", "backend/assistant_timing_report.py"]
    environment = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "commit_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in source_paths},
        "method": "Real network HTTP, isolated Uvicorn; live Ollama and real Mongo; production auth/Agent/tools, no fake model or ASGI transport.",
        "host": {"system": platform.system(), "release": platform.release(), "architecture": platform.machine()},
        "ollama_version": subprocess.check_output(["ollama", "--version"], text=True).strip(),
        "mongo_version": mongo_version, "mongo_database": namespace, "persistence": "mongo",
        "model": settings.ollama_model, "num_ctx": settings.ollama_num_ctx, "num_predict": settings.ollama_num_predict,
        "temperature": 0.1, "think": False, "concurrency": 1, "warmup_requests": args.warmup,
        "measured_requests_requested": args.requests, "model_timeout_seconds": args.model_timeout,
        "http_timeout_seconds": args.http_timeout, "client_retries": 0, "workload": WORKLOAD,
        "synthetic_fixture": {"job_id": job.id, "title": TITLE, "city": "San Jose"},
        "controlled_failure": "Separate request outside measured set; dependency override only on isolated app uses reserved non-listening loopback port, 1s model timeout/0.25s connect; shared Ollama stays running.",
    }
    with (output / "environment.json").open("x") as file:
        json.dump(environment, file, indent=2)
    reports = Reports()
    application = FastAPI()
    configure_threadpool(application)
    application.add_middleware(TraceMiddleware, service="assistant-trace-isolated", timing_sink=reports)
    application.include_router(student_auth.router)
    application.include_router(assistant.router)
    reserved = socket.socket()
    reserved.bind(("127.0.0.1", 0))  # Reserved, deliberately not listening; cannot disrupt another service.

    def model_client(request: Request):
        failure = request.headers.get("X-Evidence-Failure") == "model-connect"
        client = OllamaClient(base_url=f"http://127.0.0.1:{reserved.getsockname()[1]}" if failure else settings.ollama_base_url)
        client.timeout = httpx.Timeout(1 if failure else args.model_timeout, connect=0.25 if failure else 5)
        return client
    application.dependency_overrides[assistant.get_model_client] = model_client
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=port, log_level="warning", access_log=False))
    thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    deadline = time.perf_counter() + 15
    while not server.started and thread.is_alive() and time.perf_counter() < deadline:
        time.sleep(0.01)
    if not server.started:
        raise RuntimeError("isolated_server_not_started")

    rows = []
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=args.http_timeout) as client:
            signup = client.post("/auth/signup", json={"email": "trace-student@example.com", "password": "Synthetic-trace-fixture-123!",
                                                      "full_name": "Synthetic Trace Student", "city": "San Jose"})
            signup.raise_for_status()
            token = signup.json()["access_token"]

            def request(index, phase, injected=False):
                trace_id = f"trace-{suffix}-{phase}-{index:02d}"
                headers = {"Authorization": f"Bearer {token}", "X-Trace-Id": trace_id}
                if injected:
                    headers["X-Evidence-Failure"] = "model-connect"
                started = time.perf_counter()
                status = None; data = {}; category = None; echoed = None
                try:
                    response = client.post("/assistant/chat", headers=headers, json={"message": WORKLOAD})
                    status = response.status_code
                    echoed = response.headers.get("X-Trace-Id")
                    try:
                        data = response.json()
                    except ValueError:
                        category = "non_json_response"
                except httpx.TimeoutException:
                    category = "http_timeout"
                except httpx.HTTPError:
                    category = "http_transport_error"
                elapsed = (time.perf_counter() - started) * 1000
                report = reports.wait(trace_id, timeout=6 * args.model_timeout + 30 if category == "http_timeout" else 10)
                reply = public_text(str(data.get("reply", "")))[:16000]
                real_read = report and any(s["stage"] == "tool" and s["operation"] == "search_jobs" for s in report["spans"])
                correlated = bool(report and report["trace_id"] == trace_id and echoed == trace_id and report["http_status"] == status)
                success = status == 200 and correlated and real_read and TITLE.casefold() in reply.casefold() and "san jose" in reply.casefold() and not data.get("pending_action")
                outcome = "success" if success else "safe_error" if status == 200 else "http_error"
                if category == "http_timeout": outcome = "timeout"
                return {"index": index, "phase": phase, "trace_id": trace_id, "echoed_trace_id": echoed,
                        "http_status": status, "outcome": outcome, "timeout": category == "http_timeout", "trace_correlated": correlated,
                        "end_to_end_ms": elapsed, "error_category": category or (None if success else "application_outcome_failed"),
                        "injected_failure": injected,
                        "response": {"reply": reply, "api_tool_calls": data.get("tool_calls"), "pending_confirmation": bool(data.get("pending_action"))},
                        "timing": report}

            with (output / "warmup.jsonl").open("x") as file:
                for index in range(1, args.warmup + 1):
                    row = request(index, "warmup")
                    file.write(json.dumps(row) + "\n"); file.flush()
                    print(json.dumps({"phase": "warmup", "index": index, "outcome": row["outcome"]}), flush=True)
            failure = request(1, "failure", injected=True)
            failure_timing = failure.get("timing") or {}
            failure["bounded_failure_verified"] = (
                failure["http_status"] == 200 and failure["outcome"] == "safe_error"
                and failure_timing.get("model_call_count") == 2
                and failure_timing.get("tool_call_count") == 0
                and "model_backend_error" in failure_timing.get("errors", [])
            )
            with (output / "failure_trace.json").open("x") as file:
                json.dump(failure, file, indent=2)
            with (output / "measurements.jsonl").open("x") as file:
                for index in range(1, args.requests + 1):
                    row = request(index, "measured")
                    rows.append(row)
                    file.write(json.dumps(row) + "\n"); file.flush()
                    print(json.dumps({"phase": "measured", "index": index, "status": row["http_status"], "outcome": row["outcome"],
                                      "elapsed_ms": round(row["end_to_end_ms"], 3), "output": str(output)}), flush=True)
                    if row["outcome"] == "success" and not (output / "success_trace.json").exists():
                        with (output / "success_trace.json").open("x") as trace_file:
                            json.dump(row, trace_file, indent=2)
                    if row["timing"] is None:
                        # Cannot safely assert concurrency one with an unresolved prior request.
                        raise RuntimeError("missing_server_trace_stopped_sequential_run")
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        reserved.close(); listener.close(); mongo.close()
        summary = analyze(rows, args.requests)
        with (output / "analysis.json").open("x") as file:
            json.dump(summary, file, indent=2)
        (output / "summary.md").write_text(markdown(summary, environment))
        print(json.dumps({"output": str(output), "measured_requests": len(rows), "summary": summary}), flush=True)
    return 0 if summary["complete"] and summary["successes"] == args.requests and failure["bounded_failure_verified"] else 1


if __name__ == "__main__":
    try:
        result = main()
    except Exception as exc:
        safe_codes = {"required_model_not_installed", "isolated_server_not_started", "missing_server_trace_stopped_sequential_run"}
        error_code = str(exc) if isinstance(exc, RuntimeError) and str(exc) in safe_codes else type(exc).__name__
        print(json.dumps({"error_type": error_code, "result": "verification blocked or incomplete"}), flush=True)
        result = 2
    raise SystemExit(result)
