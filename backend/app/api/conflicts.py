from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException, Path
from app.services.graph_service import graph_service
from app.models.schemas import ConflictItem, ConflictResolveRequest
from app.config import settings

router = APIRouter(tags=["Conflicts"])

@router.get("/conflicts", response_model=List[ConflictItem])
def list_conflicts(
    status: Optional[str] = Query(default=None, description="Filter by status: open, resolved, acknowledged"),
    project_id: str = Query(default=settings.DEFAULT_PROJECT_ID)
):
    """Retrieve conflicts and contradictory memory groups."""
    conflicts = graph_service.list_conflicts(project_id=project_id, status=status)
    return [ConflictItem(**c) for c in conflicts]

@router.post("/conflicts/{id}/resolve", response_model=ConflictItem)
def resolve_conflict(
    id: str = Path(..., description="Conflict ID"),
    payload: ConflictResolveRequest = ...
):
    """
    Resolve an active contradiction without deleting provenance.
    Preserves both facts in graph while marking state as resolved.
    """
    res = graph_service.resolve_conflict(
        conflict_id=id,
        status=payload.status,
        resolution_note=payload.resolution_note,
        winning_memory_id=payload.winning_memory_id
    )
    if not res:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return ConflictItem(**res)
