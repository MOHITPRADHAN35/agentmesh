from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class MemoryType(str):
    FACT = "fact"
    DECISION = "decision"
    CONSTRAINT = "constraint"

class SessionCreate(BaseModel):
    session_id: Optional[str] = None
    project_id: str = "default_project"

class SessionResponse(BaseModel):
    session_id: str
    created_at: str
    project_id: str
    memory_count: int = 0

class MemoryItem(BaseModel):
    id: str
    content: str
    memory_type: str = "fact"
    confidence: float = 1.0
    source: str = "user"
    project_id: str
    timestamp: str
    created_by_agent: Optional[str] = None
    session_id: Optional[str] = None

class TaskItem(BaseModel):
    id: str
    title: str
    status: str = "todo"
    priority: str = "medium"
    project_id: str
    informing_memory_ids: List[str] = Field(default_factory=list)

class ConflictItem(BaseModel):
    id: str
    status: str = "open"  # "open", "resolved", "acknowledged"
    explanation: str
    project_id: str
    created_at: Optional[str] = None
    involved_memory_ids: List[str] = Field(default_factory=list)
    resolution_note: Optional[str] = None

class ConflictResolveRequest(BaseModel):
    status: str = "resolved"  # "resolved", "acknowledged"
    resolution_note: str
    winning_memory_id: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    session_id: str
    project_id: str = "default_project"

class AgentStep(BaseModel):
    agent: str
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)

class ChatResponse(BaseModel):
    response: str
    session_id: str
    project_id: str
    persisted_memories: List[MemoryItem] = Field(default_factory=list)
    retrieved_memories: List[MemoryItem] = Field(default_factory=list)
    new_tasks: List[TaskItem] = Field(default_factory=list)
    conflicts_detected: List[ConflictItem] = Field(default_factory=list)
    agent_steps: List[AgentStep] = Field(default_factory=list)
    provenance: List[str] = Field(default_factory=list)

class GraphNode(BaseModel):
    id: str
    label: str  # "Memory", "Agent", "Session", "Task", "Conflict"
    properties: Dict[str, Any]

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str  # "CREATED", "CONTAINS", "RELATES_TO", "SUPPORTS", "CONTRADICTS", "INFORMS", "INVOLVES"
    properties: Dict[str, Any] = Field(default_factory=dict)

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    graph_name: str
    node_count: int
    edge_count: int
    error: Optional[str] = None
