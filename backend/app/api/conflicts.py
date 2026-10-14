from typing import List, Optional
from fastapi import APIRouter, Path, HTTPException
from app.services.graph_service import graph_service
from app.models.schemas import ConflictItem, ConflictResolveRequest

router = APIRouter(tags=["Conflicts"])

@router.get("/conflicts", response_model=List[ConflictItem])
def list_conflicts():
    """Retrieve open and resolved contradiction pairs."""
    conflicts = graph_service.list_conflicts()
    return [ConflictItem(**c) for c in conflicts]

@router.post("/conflicts/{id}/resolve", response_model=ConflictItem)
def resolve_conflict(
    id: str = Path(..., description="Conflict ID"),
    payload: ConflictResolveRequest = ...
):
    """
    Resolve contradiction while preserving provenance.
    """
    res = graph_service.resolve_conflict(
        conflict_id=id,
        resolution=payload.resolution,
        note=payload.note
    )
    if not res:
        raise HTTPException(status_code=404, detail="Conflict not found")
    return ConflictItem(**res)
