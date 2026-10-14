from typing import Optional
from fastapi import APIRouter, Query
from app.services.graph_service import graph_service
from app.models.schemas import GraphResponse
from app.config import settings

router = APIRouter(tags=["Graph"])

@router.get("/graph", response_model=GraphResponse)
def get_graph(
    session_id: Optional[str] = Query(default=None, description="Optional session filter"),
    project_id: str = Query(default=settings.DEFAULT_PROJECT_ID)
):
    """
    Retrieve all nodes and edges for visual interactive graph rendering.
    Returns:
    - Nodes (Memory, Agent, Session, Task, Conflict)
    - Edges (CREATED, CONTAINS, RELATES_TO, SUPPORTS, CONTRADICTS, INFORMS, INVOLVES)
    """
    data = graph_service.get_full_graph(project_id=project_id, session_id=session_id)
    return GraphResponse(**data)
