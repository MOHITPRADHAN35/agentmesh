import pytest
from app.models.schemas import (
    MemoryItem,
    SessionCreate,
    ConflictResolveRequest,
    GraphNode,
    GraphEdge,
    GraphResponse
)

def test_pydantic_schema_serialization():
    node = GraphNode(
        id="mem_123",
        type="Memory",
        label="PostgreSQL database",
        data={"confidence": 0.95}
    )
    edge = GraphEdge(
        id="edge_1",
        source="session_1",
        target="mem_123",
        label="CONTAINS"
    )
    graph = GraphResponse(nodes=[node], edges=[edge])
    assert len(graph.nodes) == 1
    assert len(graph.edges) == 1
    assert graph.nodes[0].type == "Memory"
    assert graph.edges[0].label == "CONTAINS"

def test_conflict_resolve_request_validation():
    req = ConflictResolveRequest(
        resolution="accept_b",
        note="Accepted latest database decision"
    )
    assert req.resolution == "accept_b"
