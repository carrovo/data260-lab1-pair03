"""
Confirmation helpers for state-changing AI tools.

Read-only tools do not require confirmation.
save_job_or_event is the only state-changing tool in Lab 1.
"""

import re
from typing import Any, Dict, List, Optional


WRITE_TOOLS = {
    "save_job_or_event",
}


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
    arguments: Dict[str, Any],
    auto_approve: bool = False,
) -> Dict[str, Any]:
    """
    Decide whether a requested tool may execute.

    Returns:
        {
            "allowed": bool,
            "status": str,
            "message": str,
        }
    """

    # Read-only tools execute immediately.
    if tool_name not in WRITE_TOOLS:
        return {
            "allowed": True,
            "status": "not_required",
            "message": "",
        }

    # Used for deterministic testing / explicit application approval.
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
            f"This action changes stored data. "
            f"Approve the action before it runs."
        )

    return {
        "allowed": False,
        "status": "confirmation_required",
        "message": message,
    }


def is_decline_message(message: str) -> bool:
    """Return True when the user clearly declines a pending action."""

    if not message:
        return False

    normalized = message.lower().strip()

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
    conversation: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """
    Recover the most recent pending save confirmation from assistant history.

    Example:
        Confirmation required: save job #1?
    """

    if not conversation:
        return None

    pattern = re.compile(
        r"Confirmation required:\s*save\s+(job|event)\s+#(\d+)",
        re.IGNORECASE,
    )

    for message in reversed(conversation):
        if not isinstance(message, dict):
            continue

        if message.get("role") != "assistant":
            continue

        content = message.get("content")

        if not isinstance(content, str):
            continue

        match = pattern.search(content)

        if match:
            return {
                "tool_name": "save_job_or_event",
                "arguments": {
                    "item_type": match.group(1).lower(),
                    "item_id": int(match.group(2)),
                },
            }

    return None


def cancellation_message(arguments: Dict[str, Any]) -> str:
    """Create a clear cancellation result."""

    item_type = arguments.get("item_type", "item")
    item_id = arguments.get("item_id")

    if item_id is None:
        return "Save action cancelled. No stored data was changed."

    return (
        f"Cancelled saving {item_type} #{item_id}. "
        f"No stored data was changed."
    )