# AgentMesh: Persistent Multi-Agent Context Engine on FalkorDB

[![Track](https://img.shields.io/badge/Track-Agent%20Memory%20%26%20Coordination-6366f1.svg)](#)
[![Graph Database](https://img.shields.io/badge/Database-FalkorDB-dc2626.svg)](https://github.com/FalkorDB/FalkorDB)
[![Backend](https://img.shields.io/badge/FastAPI-Python%203.11+-009688.svg)](https://fastapi.tiangolo.com)

**AgentMesh** is an active persistent-memory and relationship engine for autonomous multi-agent teams. Built on **FalkorDB**, AgentMesh turns ephemeral conversations into an evolving, connected knowledge graph. It preserves historical decisions across sessions, shares state between specialized agents (Researcher, Reviewer, Planner), detects architectural contradictions, and provides evidence-backed answers with strict graph provenance.

---

## 🏆 Hackathon Tracks Entered
- **Primary Track:** **Agent Memory and Coordination**
- **Secondary Track:** **Company Brain**

---

## 💡 The Core Problem & FalkorDB Solution
* **The Problem:** Modern LLM agents have amnesia. Across sessions, they lose context, contradict earlier decisions, fail to coordinate across roles, and hallucinate without provenance.
* **The Solution:** Rather than treating memory as passive vector text, FalkorDB acts as an **active relationship engine**. When an agent learns something new, it traverses historical decisions, detects clashes (`CONTRADICTS`), links supporting evidence (`SUPPORTS`), and binds actionable tasks (`INFORMS`).

If you remove FalkorDB, the product cannot function—the graph is the core context engine.

---

## 📐 Graph Data Model

```
       (Agent) ──[:CREATED]──> (Memory) ──[:INFORMS]──> (Task)
                                  │   ▲
                     [:CONTAINS]  │   │ [:RELATES_TO | SUPPORTS | CONTRADICTS]
                                  ▼   │
      (Session) ──────────────> (Memory)
                                  ▲
                                  │ [:INVOLVES]
                                  │
                              (Conflict)
```

### Node Labels
* **`Memory`**: `id`, `content`, `memory_type` (fact/decision/constraint), `confidence`, `source`, `project_id`, `timestamp`
* **`Agent`**: `name`, `role`
* **`Session`**: `session_id`, `created_at`, `project_id`
* **`Task`**: `id`, `title`, `status`, `priority`, `project_id`
* **`Conflict`**: `id`, `status` (open/resolved/acknowledged), `explanation`, `project_id`, `created_at`

### Relationships
* `(:Agent)-[:CREATED]->(:Memory)`: Provenance of which agent generated or extracted the memory.
* `(:Session)-[:CONTAINS]->(:Memory)`: Cross-session chronological containment.
* `(:Memory)-[:RELATES_TO]->(:Memory)`: Semantic adjacency between statements.
* `(:Memory)-[:SUPPORTS]->(:Memory)`: Supporting validation.
* `(:Memory)-[:CONTRADICTS]->(:Memory)`: Direct architectural or factual conflicts.
* `(:Memory)-[:INFORMS]->(:Task)`: Concrete work derived from verified facts.
* `(:Conflict)-[:INVOLVES]->(:Memory)`: Preserves both sides of contradictory claims.

---

## 🔍 Key Cypher Queries

### 1. Multi-Hop Graph Memory Retrieval (Cross-Session Recall)
```cypher
MATCH (m:Memory {project_id: $project_id})
WHERE m.content CONTAINS $keyword OR m.id IN $seed_ids
OPTIONAL MATCH (m)-[r:RELATES_TO|SUPPORTS]-(related:Memory)
OPTIONAL MATCH (m)-[:INFORMS]->(t:Task)
OPTIONAL MATCH (s:Session)-[:CONTAINS]->(m)
RETURN 
  m.id AS id, 
  m.content AS content, 
  m.memory_type AS type,
  collect(DISTINCT related.content) AS related_facts,
  collect(DISTINCT t.title) AS informed_tasks,
  collect(DISTINCT s.session_id) AS historical_sessions
```

### 2. Contradiction Detection & Conflict Graph Ingestion
```cypher
MATCH (m1:Memory {id: $new_id}), (m2:Memory {id: $existing_id})
MERGE (m1)-[:CONTRADICTS]->(m2)
MERGE (m2)-[:CONTRADICTS]->(m1)
CREATE (c:Conflict {
  id: $conflict_id,
  status: 'open',
  explanation: $explanation,
  project_id: $project_id,
  created_at: datetime()
})
MERGE (c)-[:INVOLVES]->(m1)
MERGE (c)-[:INVOLVES]->(m2)
RETURN c.id AS conflict_id
```

### 3. Non-Destructive Conflict Resolution
```cypher
MATCH (c:Conflict {id: $conflict_id, project_id: $project_id})
SET c.status = $resolution_status, c.resolution_note = $resolution_note
WITH c
MATCH (c)-[:INVOLVES]->(m:Memory)
RETURN c.id, c.status, collect(m.id) AS involved_memories
```

---

## 🚀 Quickstart & Local Setup

### Prerequisites
* Docker & Docker Compose **OR** Python 3.11+ with local FalkorDB instance.

### Option A: Docker Compose (Recommended)
```bash
# Clone the repository
git clone https://github.com/your-username/agentmesh.git
cd agentmesh

# Start FalkorDB and the FastAPI backend
docker compose up --build
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser to access the live dashboard with interactive Cytoscape graph visualization.

### Option B: Local Python Setup
```bash
# 1. Start FalkorDB in Docker
docker run -p 6379:6379 -it --rm falkordb/falkordb:latest

# 2. In a separate terminal, set up the backend
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

---

## 🧪 Seeding & Running Tests

### Seed Demo Scenarios
Run the explicit seed script to simulate 3 cross-session agent interactions with conflict detection:
```bash
cd backend
python scripts/seed_demo.py
```

### Run Unit Tests
```bash
cd backend
pytest -v
```

---

## 📡 API Reference Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Live database ping, node count, and edge count |
| `POST` | `/api/sessions` | Create or register a persistent session |
| `GET` | `/api/sessions` | List all sessions recorded for project |
| `POST` | `/api/chat` | Execute Researcher -> Reviewer -> Planner cycle |
| `GET` | `/api/memories` | Filter memories by keyword or project |
| `GET` | `/api/graph` | Serialize nodes & edges for visual Cytoscape graph |
| `GET` | `/api/conflicts` | List open/resolved contradictions |
| `POST` | `/api/conflicts/{id}/resolve` | Resolve contradiction without destroying facts |
| `GET` | `/docs` | Interactive Swagger / OpenAPI documentation |
