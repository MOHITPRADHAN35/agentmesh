from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

NodeType = Literal["Session", "Agent", "Memory", "Task", "Conflict"]
AgentName = Literal["Researcher", "Planner", "Reviewer"]

class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"] = "ok"
    database: bool = True
    mode: Literal["live", "demo"] = "live"

class SessionCreate(BaseModel):
    title: Optional[str] = None
    project_id: str = "default_project"

class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    message_count: int = 0

class Evidence(BaseModel):
    memory_id: str
    text: str
    source: str

class AgentStep(BaseModel):
    agent: AgentName
    status: Literal["idle", "running", "done", "error"] = "done"
    output: str

class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    evidence: Optional[List[Evidence]] = Field(default_factory=list)
    steps: Optional[List[AgentStep]] = Field(default_factory=list)
    provider: Optional[Literal["live", "demo"]] = "live"
    retrieved_memory_ids: Optional[List[str]] = Field(default_factory=list)

class ChatRequest(BaseModel):
    session_id: str
    message: str
    project_id: str = "default_project"

class ChatResponse(BaseModel):
    session_id: str
    message: ChatMessage
    created_memory_ids: List[str] = Field(default_factory=list)

class MemoryItem(BaseModel):
    id: str
    text: str
    type: str = "fact"
    source: str = "user"
    session_id: str
    agent: Optional[AgentName] = "Researcher"
    created_at: str
    confidence: float = 1.0

class GraphNode(BaseModel):
    id: str
    type: NodeType
    label: str
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class ConflictItem(BaseModel):
    id: str
    reason: str
    status: Literal["open", "resolved"] = "open"
    a: MemoryItem
    b: MemoryItem

class ConflictResolveRequest(BaseModel):
    resolution: Literal["accept_a", "accept_b", "keep_both", "unresolved"] = "accept_b"
    note: Optional[str] = None
