from typing import List, Optional
from fastapi import APIRouter, Query
from app.services.graph_service import graph_service
from app.models.schemas import MemoryItem
from app.config import settings

router = APIRouter(tags=["Memories"])

@router.get("/memories", response_model=List[MemoryItem])
def search_memories(
    query: Optional[str] = Query(default=None, description="Keyword to filter memory content"),
    project_id: str = Query(default=settings.DEFAULT_PROJECT_ID),
    limit: int = Query(default=20, le=100)
):
    """Retrieve memories from FalkorDB scoped by project."""
    memories = graph_service.search_memories(
        project_id=project_id,
        query_str=query,
        limit=limit
    )
    return [MemoryItem(**m) for m in memories]
