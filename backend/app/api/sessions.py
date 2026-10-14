from typing import List, Optional
from fastapi import APIRouter, Query
from app.services.graph_service import graph_service
from app.models.schemas import SessionCreate, SessionResponse
from app.config import settings

router = APIRouter(tags=["Sessions"])

@router.post("/sessions", response_model=SessionResponse)
def create_session(payload: SessionCreate):
    """Create or register a persistent session."""
    session = graph_service.create_session(
        session_id=payload.session_id,
        project_id=payload.project_id
    )
    return SessionResponse(**session)

@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(project_id: str = Query(default=settings.DEFAULT_PROJECT_ID)):
    """List all sessions recorded for a project."""
    sessions = graph_service.list_sessions(project_id=project_id)
    return [SessionResponse(**s) for s in sessions]
