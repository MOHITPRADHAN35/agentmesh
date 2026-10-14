from fastapi import APIRouter
from app.services.agent_orchestrator import orchestrator
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["Chat"])

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest):
    """
    Execute multi-agent cycle:
    1. Researcher extracts candidates.
    2. Reviewer detects conflicts & creates CONTRADICTS links.
    3. Planner recalls multi-hop graph context & updates tasks.
    4. Synthesizer generates grounded response citing Memory IDs.
    """
    result = orchestrator.process_chat(
        message=payload.message,
        session_id=payload.session_id,
        project_id=payload.project_id
    )
    return ChatResponse(**result)
