from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.ai.agent import MAX_HISTORY_MESSAGES, run_assistant
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
from backend.app.models import Student
from backend.app.routers.student_auth import get_current_student, get_db
from backend.app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
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
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    model_client: ModelClient = Depends(get_model_client),
) -> AssistantChatResponse:
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
    )
