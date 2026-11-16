from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from backend.app.ai.agent import (
    MAX_HISTORY_CONTENT_LENGTH,
    MAX_HISTORY_MESSAGES,
)


MAX_ASSISTANT_REPLY_LENGTH = 16000
MAX_CONFIRMATION_TOKEN_LENGTH = 4096


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(
        min_length=1,
        max_length=MAX_HISTORY_CONTENT_LENGTH,
    )


class AssistantConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action_token: str = Field(
        min_length=1,
        max_length=MAX_CONFIRMATION_TOKEN_LENGTH,
    )
    approved: bool


class AssistantChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_HISTORY_CONTENT_LENGTH,
    )
    conversation: list[ConversationMessage] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_MESSAGES,
    )
    confirmation: AssistantConfirmation | None = None
    conversation_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_one_action(self):
        if (self.message is None) == (self.confirmation is None):
            raise ValueError(
                "Provide exactly one of message or confirmation."
            )
        return self


class PendingAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_token: str = Field(
        min_length=1,
        max_length=MAX_CONFIRMATION_TOKEN_LENGTH,
    )
    tool_name: Literal["save_job_or_event"]
    summary: str = Field(min_length=1, max_length=500)
    item_type: Literal["job", "event"]
    item_id: int = Field(gt=0)


class ModelCallUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int = Field(ge=1)
    purpose: str
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    context_capacity: int | None = Field(default=None, gt=0)
    source: Literal["ollama", "synthetic", "unknown"]
    capacity_source: Literal["request.options.num_ctx", "unknown"]


class AssistantUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calls: list[ModelCallUsage]
    model_calls: int = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latest_context_tokens: int | None = Field(default=None, ge=0)
    context_capacity: int | None = Field(default=None, gt=0)
    context_percent: float | None = Field(default=None, ge=0)
    warning: bool
    context_call_index: int | None = None
    capacity_source: Literal["request.options.num_ctx", "unknown"]
    context_source: Literal["latest_call_prompt_plus_completion", "unknown"]
    context_is_estimate: bool


class CompactionBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["estimated_utf8_bytes_div2_ascii_plus_framing"]
    estimated_input_tokens: int = Field(ge=0)
    reserved_output_tokens: int = Field(gt=0, le=512)
    context_capacity: int = Field(gt=0)


class CompactionQuoteSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    message_index: int = Field(ge=0)
    excerpt_index: int = Field(ge=0)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    role: Literal["user", "assistant"]
    equivalent_message_indices: list[int] = Field(max_length=40)
    categories: list[str] = Field(max_length=8)


class CompactionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["compacted", "not_needed", "failed"]
    before_prompt_tokens: int | None = None
    after_prompt_tokens: int | None = None
    measurement_source: Literal["ollama", "synthetic", "unknown"] = "unknown"
    before_messages: int
    after_messages: int
    error: str | None = None
    automatic: bool = False
    budget: CompactionBudget | None = None
    source_history_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_provenance: list[CompactionQuoteSource] = Field(default_factory=list, max_length=96)


class AssistantChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = Field(min_length=1, max_length=MAX_ASSISTANT_REPLY_LENGTH)
    conversation: list[ConversationMessage] = Field(
        max_length=MAX_HISTORY_MESSAGES,
    )
    tool_calls: int = Field(ge=0)
    pending_action: PendingAction | None = None
    usage: AssistantUsage | None = None
    compaction: CompactionReport | None = None
