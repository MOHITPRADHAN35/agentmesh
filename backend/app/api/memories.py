from typing import List, Optional
from fastapi import APIRouter, Query
from app.services.graph_service import graph_service
from app.models.schemas import MemoryItem

router = APIRouter(tags=["Memories"])

@router.get("/memories", response_model=List[MemoryItem])
def search_memories(
    query: Optional[str] = Query(default=None, description="Search term for memories")
):
    """Retrieve memories from FalkorDB."""
    memories = graph_service.search_memories(query_str=query)
    return [MemoryItem(**m) for m in memories]
