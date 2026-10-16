from typing import List, Optional
from fastapi import APIRouter, Path
from app.services.graph_service import graph_service
from app.models.schemas import SessionCreate, SessionResponse, SessionUpdate, ChatMessage

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

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str = Path(..., description="Session ID")):
    """Delete a session, its messages, associated memories, and residue from FalkorDB."""
    success = graph_service.delete_session(session_id)
    return {"status": "ok", "deleted_session_id": session_id, "success": success}

@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def rename_session(payload: SessionUpdate, session_id: str = Path(..., description="Session ID")):
    """Rename an existing session in FalkorDB."""
    session = graph_service.update_session_title(session_id, payload.title)
    return SessionResponse(**session)
