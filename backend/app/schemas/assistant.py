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


class AssistantChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = Field(min_length=1, max_length=MAX_ASSISTANT_REPLY_LENGTH)
    conversation: list[ConversationMessage] = Field(
        max_length=MAX_HISTORY_MESSAGES,
    )
    tool_calls: int = Field(ge=0)
    pending_action: PendingAction | None = None
