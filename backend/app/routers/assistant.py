from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ChatRequest, ChatResponse
from app.ai.agent import run_assistant
from app.ai.ollama_client import OllamaClient

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_model_client = OllamaClient()  # single shared client instance


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    No auth guard here on purpose — in the real app this sits behind student
    auth (student_id comes from the JWT, not the request body). Left as a
    request field for now so the loop/tools are easy to test directly from
    Swagger. Tighten this when wiring the real student auth in from
    Xuanhua's side.
    """
    result = run_assistant(
    db=db,
    user_message=payload.message,
    conversation=payload.conversation,
    model_client=_model_client,
    student_id=payload.student_id,
    auto_approve=payload.auto_approve,
    )
    return ChatResponse(**result)
