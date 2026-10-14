from typing import List, Optional
from fastapi import APIRouter, Path
from app.services.graph_service import graph_service
from app.models.schemas import SessionCreate, SessionResponse, ChatMessage

router = APIRouter(tags=["Sessions"])

@router.post("/sessions", response_model=SessionResponse)
def create_session(payload: SessionCreate):
    """Create or register a persistent session."""
    session = graph_service.create_session(
        title=payload.title,
        project_id=payload.project_id
    )
    return SessionResponse(**session)

@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions():
    """List all sessions recorded for project."""
    sessions = graph_service.list_sessions()
    return [SessionResponse(**s) for s in sessions]

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessage])
def get_session_messages(session_id: str = Path(..., description="Session ID")):
    """Get all chat messages recorded for a session."""
    messages = graph_service.get_messages(session_id)
    return [ChatMessage(**m) for m in messages]
