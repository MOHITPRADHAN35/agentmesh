from fastapi import APIRouter
from app.services.graph_service import graph_service
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def get_health():
    """Verify live FalkorDB connectivity and health."""
    health_data = graph_service.check_health()
    return HealthResponse(**health_data)
