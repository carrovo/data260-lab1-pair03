"""Mongo-only Assistant memory; no dependency on business persistence.

Each student's bounded entry list is one atomic document. Version compare-and-set
and durable event receipts make consolidation replay safe on standalone Mongo.
"""
from datetime import datetime, timedelta, timezone
import re
from uuid import uuid4


EVENT = "assistant.memory_consolidation_requested"
RULES = {
    "privacy": "Protect student privacy. Never reveal credentials or another student's data.",
    "eligibility": "State applicable opportunity eligibility requirements from verified tools.",
}
MAX_ENTRIES = 200
SESSION_HOURS = 8


def now():
    return datetime.now(timezone.utc)


def public_text(text):
    if re.search(
        r"(?i)\b(?:password|(?:access_|action_|refresh_)?token|secret|api[_ .-]?key|authorization)"
        r"[\"']?\s*(?:is\b|[:=])|bearer\s+\S+"
        r"|\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
        r"|BEGIN .*PRIVATE KEY|\b(?:AKIA|ASIA)[0-9A-Z]{16}\b|\b\w+://\S+",
        text,
    ):
        return "[Private content omitted]"
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[redacted email]", text)
    return text[:8000]


class MemoryConflict(RuntimeError):
    pass


class MemoryStore:
    def __init__(self, db):
        self.db = db

    def initialize(self):
        self.db.student_memory.create_index("student_id", unique=True)
        self.db.conversations.create_index([("student_id", 1), ("expires_at", 1)])
        self.db.conversations.create_index("expires_at", expireAfterSeconds=0)
        for key, description in RULES.items():
            # Only trusted server code writes rules. No learning/consolidation path does.
            self.db.assistant_rules.update_one(
                {"_id": key}, {"$setOnInsert": {"description": description}}, upsert=True,
            )

    def document(self, student_id):
        sid = str(student_id)
        self.db.student_memory.update_one(
            {"_id": sid}, {"$setOnInsert": {
                "student_id": sid, "version": 0, "entries": [], "completed_events": [],
            }}, upsert=True,
        )
        return self.db.student_memory.find_one({"_id": sid})

    def entries(self, student_id):
        return self.document(student_id)["entries"]

    def learn(self, student_id, message):
        # Deliberately narrow explicit grammar. Never learn retrieved text/model output.
        match = re.fullmatch(
            r"(?:Remember: )?[Mm]y preferred (city|role|work mode) is ([A-Za-z][A-Za-z .-]{0,79})[.!]?",
            message.strip(),
        )
        if not match:
            return
        key, value = match.group(1), match.group(2).rstrip(".!").strip()
        if any(word in value.lower() for word in ("instruction", "secret", "password", "token", "ignore")):
            return
        entry = {
            "id": uuid4().hex, "date": now().isoformat(), "category": "preference",
            "key": key, "value": value, "description": f"Preferred {key}: {value}",
            "provenance": "student_explicit",
        }
        self.document(student_id)
        result = self.db.student_memory.update_one(
            {"_id": str(student_id), f"entries.{MAX_ENTRIES - 1}": {"$exists": False}},
            {"$push": {"entries": entry}, "$inc": {"version": 1}},
        )
        if not result.matched_count:
            raise MemoryConflict("Memory full; request consolidation before learning more facts.")

    def start(self, student_id):
        document = {
            "_id": uuid4().hex, "student_id": str(student_id), "messages": [],
            "version": 0, "expires_at": now() + timedelta(hours=SESSION_HOURS),
        }
        self.db.conversations.insert_one(document)
        return document

    def conversation(self, student_id, conversation_id):
        return self.db.conversations.find_one({
            "_id": conversation_id, "student_id": str(student_id),
            "expires_at": {"$gt": now()},
        })

    def save_conversation(self, document, messages, *, usage=None, pending_confirmation=None, compaction=None):
        fields = {"messages": [
            {"role": item["role"], "content": public_text(item["content"])}
            for item in messages[-40:] if item["role"] in {"user", "assistant"}
        ]}
        if usage is not None:
            fields["last_usage"] = usage
        if pending_confirmation is not None:
            fields["pending_confirmation"] = bool(pending_confirmation)
        if compaction is not None:
            fields["last_compaction"] = compaction
        result = self.db.conversations.update_one(
            {"_id": document["_id"], "student_id": document["student_id"],
             "version": document["version"], "expires_at": {"$gt": now()}},
            {"$set": fields, "$inc": {"version": 1}},
        )
        if not result.matched_count:
            raise MemoryConflict("Conversation changed or expired; retry with current history.")

    def end(self, student_id, conversation_id):
        return self.db.conversations.delete_one({
            "_id": conversation_id, "student_id": str(student_id),
        }).deleted_count == 1


def consolidate(envelope, db):
    """Latest explicit dated fact wins per category/key; exact duplicates merge.

    CAS retries re-read all entries, so concurrent new entries cannot be lost.
    The receipt and replacement are a single document write, before processed_events.
    """
    store = MemoryStore(db)
    sid = str(envelope.payload["student_id"])
    for _ in range(5):
        document = store.document(sid)
        if envelope.event_id in document["completed_events"]:
            return
        groups = {}
        opaque = []
        entries = document["entries"]
        for entry in entries:
            # Invalid/untrusted entries survive unchanged; never interpret their text.
            if (entry.get("provenance") not in {"student_explicit", "synthetic_demo"}
                    or not all(isinstance(entry.get(k), str) for k in
                               ("id", "category", "key", "value", "date", "description"))):
                opaque.append(entry)
                continue
            datetime.fromisoformat(entry["date"])
            groups.setdefault((entry["category"], entry["key"]), []).append(entry)
        retained, decisions = list(opaque), []
        for group in groups.values():
            def order(entry):
                date = datetime.fromisoformat(entry.get("date", "1970-01-01T00:00:00+00:00"))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                return date, entry.get("id", "")

            winner = max(group, key=order)
            retained.append(winner)
            if len(group) > 1:
                decisions.append({
                    "retained_id": winner["id"],
                    "merged_ids": sorted(e["id"] for e in group if e["id"] != winner["id"]),
                    "reason": "latest dated explicit fact" if len({e.get("value") for e in group}) > 1 else "duplicate fact",
                })
        retained.sort(key=lambda e: e.get("id", ""))
        result = db.student_memory.update_one(
            {"_id": sid, "version": document["version"]},
            {"$set": {"entries": retained, "last_consolidation": {
                "event_id": envelope.event_id, "trace_id": envelope.trace_id,
                "before_count": len(entries), "after_count": len(retained),
                "decisions": decisions,
            }}, "$inc": {"version": 1}, "$push": {"completed_events": envelope.event_id}},
        )
        if result.matched_count:
            return
    raise MemoryConflict("Concurrent memory updates; consolidation must retry.")


def seed_demo(db, student_id="pair03-memory-demo"):
    """63 synthetic entries -> 30 facts: 30 duplicate pairs + 3 corrections."""
    store = MemoryStore(db)
    store.initialize()
    entries = []
    for index in range(30):
        for duplicate in range(2):
            entries.append({
                "id": f"demo-{index:02d}-{duplicate}", "date": "2026-01-01T00:00:00+00:00",
                "category": "synthetic", "key": f"topic-{index:02d}",
                "value": f"original-{index}", "description": f"Synthetic preference {index}: original-{index}",
                "provenance": "synthetic_demo",
            })
    for index in range(3):
        entries.append({
            "id": f"correction-{index}", "date": "2026-02-01T00:00:00+00:00",
            "category": "synthetic", "key": f"topic-{index:02d}",
            "value": f"corrected-{index}", "description": f"Synthetic preference {index}: corrected-{index}",
            "provenance": "synthetic_demo",
        })
    db.student_memory.update_one({"_id": str(student_id)}, {"$setOnInsert": {
        "student_id": str(student_id), "version": 0, "entries": entries, "completed_events": [],
    }}, upsert=True)
    return store.entries(student_id)
