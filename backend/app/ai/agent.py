"""
Hand-built agent loop (no LangChain/CrewAI/LlamaIndex).

run_assistant() is the whole loop: send prompt+history+tools to the model,
execute any requested tool calls, append results, repeat until a final
text answer or the iteration ceiling is hit.
"""
import json
import logging
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.ai.ollama_client import ModelClient
from app.ai.tools import TOOL_SCHEMAS, TOOL_IMPLEMENTATIONS
from app.config import AGENT_MAX_ITERATIONS

logger = logging.getLogger("assistant")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

SYSTEM_PROMPT = (
    "You are the Handshake career-platform assistant. You help students find "
    "jobs and events using ONLY the tools provided — never invent a job, "
    "company, or event that a tool search didn't return. If a search comes "
    "back empty, tell the user plainly that nothing matched; do not guess. "
    "When a request depends on the student's own preferences (e.g. 'in my "
    "city'), call get_student_preferences before searching. Keep answers "
    "concise and cite specific job/event ids when relevant."
)


def _execute_tool_call(db: Session, student_id: Optional[int], name: str, arguments: Dict[str, Any]) -> str:
    """Runs one tool call and ALWAYS returns a string — tool functions are
    already exception-safe, but this is a second safety net."""
    impl = TOOL_IMPLEMENTATIONS.get(name)
    if impl is None:
        return f"Unknown tool '{name}'."

    # auto-fill student_id into tools that need it if the model omitted it
    if "student_id" in impl.__code__.co_varnames and "student_id" not in arguments and student_id is not None:
        arguments = {**arguments, "student_id": student_id}

    try:
        return impl(db, **arguments)
    except TypeError as exc:
        return f"Malformed arguments for tool '{name}': {exc}"
    except Exception as exc:  # belt-and-suspenders; impls already catch
        return f"Unexpected error running tool '{name}': {exc}"


def run_assistant(
    db: Session,
    user_message: str,
    conversation: Optional[List[Dict[str, Any]]],
    model_client: ModelClient,
    student_id: Optional[int] = None,
    max_iterations: int = AGENT_MAX_ITERATIONS,
) -> Dict[str, Any]:
    """
    Returns {"reply": str, "conversation": [...], "tool_calls": int}.
    `conversation` is the prior message list (without system prompt); this
    function appends to a copy and returns the updated list so the caller
    can persist it for the next turn (used by the follow-up/refine test).
    """
    messages: List[Dict[str, Any]] = []
    if not conversation:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
    else:
        messages.extend(conversation)
    messages.append({"role": "user", "content": user_message})

    tool_call_count = 0
    final_reply = None

    for iteration in range(1, max_iterations + 1):
        result = model_client.complete(messages, TOOL_SCHEMAS)
        messages.append({
            "role": "assistant",
            "content": result.get("content"),
            **({"tool_calls": result["tool_calls"]} if result.get("tool_calls") else {}),
        })

        tool_calls = result.get("tool_calls")
        if not tool_calls:
            final_reply = result.get("content") or ""
            break

        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            raw_args = fn.get("arguments", {})
            arguments = raw_args if isinstance(raw_args, dict) else json.loads(raw_args or "{}")

            logger.info("tool_call iteration=%d name=%s args=%s", iteration, name, arguments)
            tool_call_count += 1

            tool_result = _execute_tool_call(db, student_id, name, arguments)

            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", f"call_{tool_call_count}"),
                "name": name,
                "content": tool_result,
            })
    else:
        # Hit the iteration ceiling without a final answer — stop safely.
        final_reply = (
            "I wasn't able to finish that request within the allotted number "
            "of steps. Could you narrow the search a bit?"
        )
        messages.append({"role": "assistant", "content": final_reply})

    logger.info("run_assistant complete: %d tool call(s) across this run", tool_call_count)

    return {
        "reply": final_reply,
        "conversation": messages,
        "tool_calls": tool_call_count,
    }
