"""Small opt-in live Ollama/Mongo check, through authenticated local ASGI routes.

Uses a new synthetic Mongo namespace and isolated SQLite business/auth data.
Does not deploy/restart services, use existing students, or delete databases.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="local-check")
    parser.add_argument("--output-dir", default="loadtest/temp/observability")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,40}", args.label):
        parser.error("label must contain 1–40 lowercase letters/digits/hyphens")
    # Process-only settings for the isolated HTTP auth fixture; no environment file edits.
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    os.environ["JWT_SECRET_KEY"] = "synthetic-observability-local-only"
    os.environ["PERSISTENCE"] = "sql"
    from fastapi.testclient import TestClient
    from pymongo import MongoClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from backend.app.main import app
    from backend.app.database import Base
    from backend.app.models import Student
    from backend.app.security import create_access_token
    from backend.app.routers import assistant, student_auth
    from backend.app.ai.ollama_client import OllamaClient
    from backend.app.config import settings
    from backend.common.assistant_memory import MemoryStore, public_text

    # Read existing container credentials in memory only; never print or persist them.
    info = json.loads(subprocess.check_output(["docker", "inspect", "p03-mongo"], stderr=subprocess.DEVNULL))[0]
    environment = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    mongo = MongoClient("127.0.0.1", 9038,
                        username=environment.get("MONGO_INITDB_ROOT_USERNAME"),
                        password=environment.get("MONGO_INITDB_ROOT_PASSWORD"),
                        authSource="admin", serverSelectionTimeoutMS=3000)
    mongo.admin.command("ping")
    suffix = uuid4().hex[:10]
    database_name = f"p03_observability_{args.label.replace('-', '_')}_{suffix}"
    memory = MemoryStore(mongo[database_name]); memory.initialize()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        student = Student(email="observability@example.com", full_name="Synthetic Observability Student",
                          password_hash="[UNUSED SYNTHETIC HASH]", city="San Jose")
        db.add(student); db.commit(); sid = student.id
    def database():
        with Session(engine) as db:
            yield db
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[student_auth.get_db] = database
    app.dependency_overrides[assistant.get_memory_store] = lambda: memory
    app.dependency_overrides[assistant.get_model_client] = lambda: OllamaClient(base_url="http://127.0.0.1:11434")
    original = memory.start(sid)
    facts = ("My preferred city is San Jose. Job #7 belongs to company #3. "
             "Event #9 is discussed. Application #4 status is unknown. "
             "Next step: check eligibility with tools.")
    messages = [{"role": role, "content": text} for _ in range(5)
                for role, text in [("user", facts), ("assistant", "We must verify the historical identifiers before using them.")]]
    messages += [{"role": "user", "content": "Please recall my preferred city and the unresolved next step."},
                 {"role": "assistant", "content": "We will continue after checking the facts."}]
    memory.save_conversation(original, messages)
    headers = {"Authorization": f"Bearer {create_access_token(sid, 'student')}"}
    before = memory.conversation(sid, original["_id"])["messages"]
    try:
        with TestClient(app) as client:
            response = client.post("/assistant/chat", json={"message": "/compact", "conversation_id": original["_id"]},
                                   headers={**headers, "X-Trace-Id": f"obs-compact-{suffix}"})
            result = response.json()
            compacted = response.status_code == 200 and result.get("compaction", {}).get("status") == "compacted"
            after = memory.conversation(sid, original["_id"])["messages"]
            follow = None
            if compacted:
                follow = client.post("/assistant/chat", headers={**headers, "X-Trace-Id": f"obs-recall-{suffix}"},
                                     json={"message": "Repeat the city and unresolved next step stated earlier. Do not infer opportunity details.",
                                           "conversation_id": original["_id"]})
            answer = public_text(follow.json().get("reply", "")) if follow is not None else ""
            evidence = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "commit_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "working_tree_code": "uncommitted observability checkpoint",
                "method": "Authenticated production ASGI routes via TestClient; live host Ollama and Mongo; isolated SQLite auth/business fixtures. Not a deployed API/browser check.",
                "model": settings.ollama_model, "ollama_location": "host loopback:11434",
                "requested_num_ctx": settings.ollama_num_ctx, "num_predict": settings.ollama_num_predict,
                "mongo_database": database_name, "synthetic_only": True,
                "conversation_id": original["_id"], "trace_id": response.headers.get("X-Trace-Id"),
                "before_count": len(before), "before_messages": before,
                "after_count": len(after), "after_messages": after,
                "compaction_http_status": response.status_code, "compaction": result.get("compaction"),
                "compaction_usage": result.get("usage"),
                "recall_http_status": follow.status_code if follow is not None else None,
                "recall_answer": answer, "recall_usage": follow.json().get("usage") if follow is not None else None,
                "learned_memory_count": len(memory.entries(sid)),
                "recall_passed": compacted and "san jose" in answer.lower() and "eligibility" in answer.lower(),
            }
        output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
        destination = output / f"live-{args.label}-{suffix}.json"
        with destination.open("x") as file:
            json.dump(evidence, file, indent=2)
        print(json.dumps({"output": str(destination), "compacted": compacted, "recall_passed": evidence["recall_passed"],
                          "compaction": evidence["compaction"]}, indent=2))
        return 0 if evidence["recall_passed"] else 1
    finally:
        app.dependency_overrides.clear(); app.dependency_overrides.update(original_overrides)
        engine.dispose(); mongo.close()


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        # Connection/driver exceptions may contain configuration; never print them.
        print(json.dumps({"error_type": type(exc).__name__, "result": "verification failed"}))
        code = 2
    raise SystemExit(code)
