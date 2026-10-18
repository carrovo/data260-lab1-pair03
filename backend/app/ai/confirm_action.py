"""Confirmation helpers for state-changing assistant tools."""

import re
from typing import Any


WRITE_TOOLS = frozenset({"save_job_or_event"})

DECLINE_WORDS = (
    "no",
    "nope",
    "cancel",
    "cancel it",
    "don't",
    "do not",
    "never mind",
    "nevermind",
    "stop",
    "decline",
)


def confirm_action(
    tool_name: str,
    arguments: dict[str, Any],
    auto_approve: bool = False,
) -> dict[str, Any]:
    """Return a decision without executing the requested action."""

    if tool_name not in WRITE_TOOLS:
        return {
            "allowed": True,
            "status": "not_required",
            "message": "",
        }

    if auto_approve:
        return {
            "allowed": True,
            "status": "approved",
            "message": "Action approved.",
        }

    item_type = arguments.get("item_type", "item")
    item_id = arguments.get("item_id")

    if item_id is None:
        message = (
            "Confirmation required before this save action can run. "
            "This action changes stored data."
        )
    else:
        message = (
            f"Confirmation required: save {item_type} #{item_id}? "
            "This action changes stored data. "
            "Approve the action before it runs."
        )

    return {
        "allowed": False,
        "status": "confirmation_required",
        "message": message,
    }


def is_decline_message(message: str) -> bool:
    """Return whether a message clearly declines a pending action."""

    if not message:
        return False

    normalized = re.sub(r"[^\w']+", " ", message.lower()).strip()

    if normalized in DECLINE_WORDS:
        return True

    return any(
        normalized.startswith(prefix)
        for prefix in (
            "no ",
            "cancel ",
            "don't ",
            "do not ",
            "never mind",
            "nevermind",
            "stop ",
            "decline ",
        )
    )


def find_pending_confirmation(
    conversation: list[dict[str, str]] | None,
) -> dict[str, Any] | None:
    """Recover the most recent pending save from assistant history."""

    if not conversation:
        return None

    pattern = re.compile(
        r"Confirmation required:\s*save\s+(job|event)\s+#(\d+)",
        re.IGNORECASE,
    )

    for message in reversed(conversation):
        if message.get("role") != "assistant":
            continue

        match = pattern.search(message.get("content", ""))
        if match:
            return {
                "tool_name": "save_job_or_event",
                "arguments": {
                    "item_type": match.group(1).lower(),
                    "item_id": int(match.group(2)),
                },
            }

    return None


def cancellation_message(arguments: dict[str, Any]) -> str:
    """Return a clear result for a declined save."""

    item_type = arguments.get("item_type", "item")
    item_id = arguments.get("item_id")

    if item_id is None:
        return "Save action cancelled. No stored data was changed."

    return (
        f"Cancelled saving {item_type} #{item_id}. "
        "No stored data was changed."
    )
