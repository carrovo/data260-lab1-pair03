"""Signed one-time confirmation tokens for assistant save actions.

Replay decisions are stored in process memory. They are deterministic and
resettable for tests, but are not shared between processes and are cleared on
application restart. A multi-worker deployment should replace this registry
with shared durable storage before relying on cross-process replay prevention.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.config import settings


CONFIRMATION_TOKEN_LIFETIME_SECONDS = 300
CONFIRMATION_TOKEN_USE = "assistant_confirmation"
SUPPORTED_CONFIRMATION_TOOL = "save_job_or_event"


class ConfirmationTokenError(ValueError):
    pass


class ConfirmationTokenExpired(ConfirmationTokenError):
    pass


class ConfirmationTokenStudentMismatch(ConfirmationTokenError):
    pass


class ConfirmationTokenReplay(ConfirmationTokenError):
    pass


class _SaveArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: Literal["job", "event"]
    item_id: int = Field(gt=0)


@dataclass(frozen=True)
class ConfirmedAction:
    student_id: int
    tool_name: Literal["save_job_or_event"]
    arguments: dict[str, Any]
    expires_at: int
    token_id: str


_decision_lock = Lock()
_token_decisions: dict[str, bool] = {}


def _validated_action(
    student_id: int,
    tool_name: str,
    arguments: Any,
    expires_at: int,
    token_id: str,
) -> ConfirmedAction:
    if student_id < 1:
        raise ConfirmationTokenError("Confirmation student is invalid.")
    if tool_name != SUPPORTED_CONFIRMATION_TOOL:
        raise ConfirmationTokenError("Confirmation tool is unsupported.")
    if not token_id:
        raise ConfirmationTokenError("Confirmation token ID is missing.")

    try:
        validated_arguments = _SaveArguments.model_validate(arguments)
    except ValidationError as exc:
        raise ConfirmationTokenError(
            "Confirmation arguments are invalid."
        ) from exc

    return ConfirmedAction(
        student_id=student_id,
        tool_name=SUPPORTED_CONFIRMATION_TOOL,
        arguments=validated_arguments.model_dump(),
        expires_at=expires_at,
        token_id=token_id,
    )


def create_confirmation_token(
    student_id: int,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    now: datetime | None = None,
    lifetime_seconds: int = CONFIRMATION_TOKEN_LIFETIME_SECONDS,
) -> str:
    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    expires_at = issued_at + timedelta(seconds=lifetime_seconds)
    token_id = uuid4().hex
    action = _validated_action(
        student_id,
        tool_name,
        arguments,
        int(expires_at.timestamp()),
        token_id,
    )

    payload = {
        "sub": str(action.student_id),
        "token_use": CONFIRMATION_TOKEN_USE,
        "tool": action.tool_name,
        "arguments": action.arguments,
        "iat": int(issued_at.timestamp()),
        "exp": action.expires_at,
        "jti": action.token_id,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_confirmation_token(
    token: str,
    authenticated_student_id: int,
) -> ConfirmedAction:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={
                "require_sub": True,
                "require_iat": True,
                "require_exp": True,
            },
        )
    except ExpiredSignatureError as exc:
        raise ConfirmationTokenExpired(
            "Confirmation token has expired."
        ) from exc
    except JWTError as exc:
        raise ConfirmationTokenError(
            "Confirmation token is invalid."
        ) from exc

    if payload.get("token_use") != CONFIRMATION_TOKEN_USE:
        raise ConfirmationTokenError("Confirmation token type is invalid.")

    try:
        student_id = int(payload["sub"])
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfirmationTokenError(
            "Confirmation token claims are invalid."
        ) from exc

    if student_id != authenticated_student_id:
        raise ConfirmationTokenStudentMismatch(
            "Confirmation token belongs to another student."
        )

    return _validated_action(
        student_id,
        payload.get("tool", ""),
        payload.get("arguments"),
        expires_at,
        str(payload.get("jti") or ""),
    )


def register_confirmation_decision(
    token_id: str,
    approved: bool,
) -> Literal["accepted", "repeated_decline"]:
    with _decision_lock:
        existing_decision = _token_decisions.get(token_id)
        if existing_decision is None:
            _token_decisions[token_id] = approved
            return "accepted"
        if existing_decision is False and approved is False:
            return "repeated_decline"

    raise ConfirmationTokenReplay(
        "Confirmation token has already been resolved."
    )


def reset_confirmation_token_state() -> None:
    """Clear process-local replay state for deterministic tests."""

    with _decision_lock:
        _token_decisions.clear()
