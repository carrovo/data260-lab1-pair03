from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.app.ai.agent import MAX_HISTORY_MESSAGES, run_assistant
from backend.app.ai.compaction import CompactionError, compact
from backend.app.ai.usage import UsageModelClient, UsageRecorder
from backend.app.config import settings
from backend.app.ai.confirm_action import cancellation_message
from backend.app.ai.confirmation_token import (
    ConfirmationTokenError,
    ConfirmationTokenExpired,
    ConfirmationTokenReplay,
    ConfirmationTokenStudentMismatch,
    create_confirmation_token,
    register_confirmation_decision,
    verify_confirmation_token,
)
from backend.app.ai.ollama_client import ModelClient, OllamaClient
from backend.app.ai.tools import TOOL_IMPLEMENTATIONS, TOOL_SCHEMAS
from backend.app.ai.memory import get_memory_store, MemoryModelClient, publish_consolidation
from backend.common.assistant_memory import MemoryConflict
from backend.app.models import Student
from backend.app.routers.student_auth import get_current_student, get_db
from backend.app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantUsage,
    CompactionReport,
    ConversationMessage,
    MAX_ASSISTANT_REPLY_LENGTH,
    PendingAction,
)


router = APIRouter(prefix="/assistant", tags=["student assistant"])


def get_model_client() -> ModelClient:
    return OllamaClient()


def _bounded_reply(reply: Any) -> str:
    text = str(reply or "The assistant returned no response.").strip()
    if not text:
        text = "The assistant returned no response."
    return text[:MAX_ASSISTANT_REPLY_LENGTH]


def _public_conversation(
    messages: list[dict[str, Any]],
) -> list[ConversationMessage]:
    public_messages = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        public_messages.append(
            ConversationMessage(role=role, content=content)
        )
    return public_messages[-MAX_HISTORY_MESSAGES:]


def _confirmation_conversation(
    request: AssistantChatRequest,
    reply: str,
) -> list[ConversationMessage]:
    return [
        *request.conversation,
        ConversationMessage(role="assistant", content=reply),
    ][-MAX_HISTORY_MESSAGES:]


def _pending_action(
    student_id: int,
    pending_call: Any,
) -> PendingAction | None:
    if not isinstance(pending_call, dict):
        return None

    tool_name = pending_call.get("tool_name")
    arguments = pending_call.get("arguments")
    if not isinstance(arguments, dict):
        return None

    try:
        action_token = create_confirmation_token(
            student_id,
            tool_name,
            arguments,
        )
        item_type = arguments["item_type"]
        item_id = int(arguments["item_id"])
        return PendingAction(
            action_token=action_token,
            tool_name=tool_name,
            summary=f"Save {item_type} #{item_id}?",
            item_type=item_type,
            item_id=item_id,
        )
    except (ConfirmationTokenError, KeyError, TypeError, ValueError):
        return None


def _confirmation_http_error(error: ConfirmationTokenError) -> HTTPException:
    if isinstance(error, ConfirmationTokenStudentMismatch):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(error, ConfirmationTokenReplay):
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_400_BAD_REQUEST

    return HTTPException(status_code=status_code, detail=str(error))


def _handle_confirmation(
    request: AssistantChatRequest,
    current_student: Student,
    db: Session,
) -> AssistantChatResponse:
    confirmation = request.confirmation
    if confirmation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation decision is missing.",
        )

    try:
        action = verify_confirmation_token(
            confirmation.action_token,
            current_student.id,
        )
        register_confirmation_decision(
            action.token_id,
            confirmation.approved,
        )
    except ConfirmationTokenExpired as error:
        raise _confirmation_http_error(error) from error
    except ConfirmationTokenError as error:
        raise _confirmation_http_error(error) from error

    if not confirmation.approved:
        reply = cancellation_message(action.arguments)
        return AssistantChatResponse(
            reply=reply,
            conversation=_confirmation_conversation(request, reply),
            tool_calls=0,
        )

    implementation = TOOL_IMPLEMENTATIONS[action.tool_name]
    reply = _bounded_reply(
        implementation(
            db,
            student_id=current_student.id,
            **action.arguments,
        )
    )
    return AssistantChatResponse(
        reply=reply,
        conversation=_confirmation_conversation(request, reply),
        tool_calls=1,
    )


@router.post("/chat", response_model=AssistantChatResponse)
def chat_with_assistant(
    request: AssistantChatRequest,
    response: Response,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    model_client: ModelClient = Depends(get_model_client),
    memory=Depends(get_memory_store),
) -> AssistantChatResponse:
    session = None
    manual = request.message == "/compact"
    if manual and memory is None:
        raise HTTPException(503, "Persistent conversation compaction requires MONGO_URL.")
    if manual and not request.conversation_id:
        raise HTTPException(400, "Start a server-backed conversation before /compact.")
    if memory is not None:
        session = (
            memory.conversation(current_student.id, request.conversation_id)
            if request.conversation_id else memory.start(current_student.id)
        )
        if session is None:
            raise HTTPException(404, "Conversation not found or expired.")
        if request.conversation_id:
            request = request.model_copy(update={
                "conversation": [ConversationMessage(**item) for item in session["messages"]],
            })
        response.headers["X-Conversation-Id"] = session["_id"]
        if session.get("pending_confirmation") and request.confirmation is None and request.message != "/memory":
            raise HTTPException(409, "Resolve the pending confirmation or end this conversation before continuing/compacting.")
        if request.message and not manual and request.message != "/memory":
            memory.learn(current_student.id, request.message)
        model_client = MemoryModelClient(
            model_client, memory.entries(current_student.id), request.message or "",
        )
    elif request.conversation_id or request.message == "/memory":
        raise HTTPException(503, "Persistent Assistant memory requires MONGO_URL.")

    recorder = UsageRecorder()
    tracked = UsageModelClient(model_client, recorder)
    if manual:
        original = [message.model_dump() for message in request.conversation]
        candidate, report = _compact_safely(original, model_client, recorder, automatic=False)
        if report["status"] == "compacted":
            try:
                memory.save_conversation(session, candidate, usage=recorder.report(),
                                         pending_confirmation=False, compaction=report)
            except MemoryConflict as exc:
                raise HTTPException(409, str(exc)) from exc
        counts = (f"{report['before_prompt_tokens']} → {report['after_prompt_tokens']} prompt tokens"
                  if report["measurement_source"] != "unknown" else "token reduction unavailable")
        reply = (f"Conversation compacted ({counts}; {report['measurement_source']})."
                 if report["status"] == "compacted" else
                 "Compaction not performed; original history retained.")
        return AssistantChatResponse(reply=reply, conversation=candidate, tool_calls=0,
                                     usage=recorder.report(), compaction=report)

    if request.message == "/memory":
        entries = memory.entries(current_student.id)
        reply = _bounded_reply("\n".join(
            f"{entry['date']} [{entry['category']}] {entry['description']}" for entry in entries[-40:]
        ) or "No learned memory entries.")
        result = AssistantChatResponse(reply=reply, conversation=[
            *request.conversation, ConversationMessage(role="user", content="/memory"),
            ConversationMessage(role="assistant", content=reply),
        ][-MAX_HISTORY_MESSAGES:], tool_calls=0)
    else:
        result = _chat(request, current_student, db, tracked)

    if session is not None:
        candidate = [message.model_dump() for message in result.conversation]
        occupancy = recorder.report()["context_percent"]
        report = None
        if (not result.pending_action and not session.get("pending_confirmation")
                and occupancy is not None and occupancy > settings.assistant_compact_threshold_percent):
            candidate, report = _compact_safely(candidate, model_client, recorder, automatic=True)
            result.conversation = [ConversationMessage(**message) for message in candidate]
            result.compaction = CompactionReport(**report)
        pending = (session.get("pending_confirmation", False) if request.message == "/memory"
                   else result.pending_action is not None)
        try:
            memory.save_conversation(session, candidate, usage=recorder.report(),
                                     pending_confirmation=pending, compaction=report)
        except MemoryConflict as exc:
            raise HTTPException(409, str(exc)) from exc
    result.usage = AssistantUsage(**recorder.report())
    return result


def _compact_safely(original, model_client, recorder, *, automatic):
    start = len(recorder.calls)
    try:
        candidate, report = compact(original, model_client, recorder)
    except CompactionError as exc:
        candidate = original
        observed = recorder.calls[start:]
        before = next((call for call in observed if call["purpose"] == "compaction_measure_before"), {})
        after = next((call for call in observed if call["purpose"] == "compaction_measure_after"), {})
        report = {"status": "failed", "before_prompt_tokens": before.get("prompt_tokens"),
                  "after_prompt_tokens": after.get("prompt_tokens"),
                  "measurement_source": before.get("source") if before.get("source") == after.get("source") and before.get("source") in {"ollama", "synthetic"} else "unknown",
                  "before_messages": len(original),
                  "after_messages": len(original), "error": str(exc)}
    report["automatic"] = automatic
    return candidate, report


def _chat(request, current_student, db, model_client):
    if request.confirmation is not None:
        return _handle_confirmation(request, current_student, db)

    result = run_assistant(
        db,
        request.message or "",
        [message.model_dump() for message in request.conversation],
        model_client,
        student_id=current_student.id,
        auto_approve=False,
        tool_schemas=TOOL_SCHEMAS,
        tool_implementations=TOOL_IMPLEMENTATIONS,
    )
    pending_action = _pending_action(
        current_student.id,
        result.get("pending_action"),
    )
    reply = _bounded_reply(result.get("reply"))
    if result.get("pending_action") is not None and pending_action is None:
        reply = "The requested save action was invalid and was not executed."

    return AssistantChatResponse(
        reply=reply,
        conversation=_public_conversation(result.get("conversation", [])),
        tool_calls=result.get("tool_calls", 0),
        pending_action=pending_action,
        usage=result.get("usage"),
    )


@router.get("/memory")
def list_memory(current_student=Depends(get_current_student), memory=Depends(get_memory_store)):
    if memory is None:
        raise HTTPException(503, "Persistent Assistant memory requires MONGO_URL.")
    entries = memory.entries(current_student.id)
    return {"entries": entries[-40:], "total": len(entries), "limit": 40}


@router.post("/conversations/{conversation_id}/end")
def end_conversation(conversation_id: str, current_student=Depends(get_current_student),
                     memory=Depends(get_memory_store)):
    if memory is None:
        raise HTTPException(503, "Persistent Assistant memory requires MONGO_URL.")
    if not memory.end(current_student.id, conversation_id):
        raise HTTPException(404, "Conversation not found.")
    if not publish_consolidation(current_student.id):
        raise HTTPException(503, {
            "ended": True, "consolidation_enqueued": False,
            "message": "Conversation ended; consolidation delivery unconfirmed. Retry /memory/consolidate.",
        })
    return {"ended": True, "consolidation_enqueued": True}


@router.post("/memory/consolidate", status_code=202)
def request_consolidation(current_student=Depends(get_current_student), memory=Depends(get_memory_store)):
    if memory is None:
        raise HTTPException(503, "Persistent Assistant memory requires MONGO_URL.")
    if not publish_consolidation(current_student.id):
        raise HTTPException(503, "Consolidation delivery unconfirmed; retry.")
    return {"consolidation_enqueued": True}
