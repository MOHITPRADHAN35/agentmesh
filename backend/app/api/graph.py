from typing import Optional
from fastapi import APIRouter, Query
from app.services.graph_service import graph_service
from app.models.schemas import GraphResponse

router = APIRouter(tags=["Graph"])

@router.get("/graph", response_model=GraphResponse)
def get_graph(
    session_id: Optional[str] = Query(default=None, description="Optional session filter")
):
    """
    Retrieve all nodes and edges for GraphExplorer / ReactFlow visualization.
    """
    data = graph_service.get_full_graph(session_id=session_id)
    return GraphResponse(**data)
