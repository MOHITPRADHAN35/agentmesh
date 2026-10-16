# 🕸️ AgentMesh: Multi-Agent Persistent Memory on FalkorDB

[![Hackathon Track](https://img.shields.io/badge/Track-Agent%20Memory%20%26%20Coordination-6366f1.svg?style=for-the-badge)](#-hackathon-tracks-entered)
[![Secondary Track](https://img.shields.io/badge/Track-Company%20Brain-ec4899.svg?style=for-the-badge)](#-hackathon-tracks-entered)
[![Graph Database](https://img.shields.io/badge/Database-FalkorDB%20(Latest)-dc2626.svg?style=for-the-badge)](https://github.com/FalkorDB/FalkorDB)
[![Repository](https://img.shields.io/badge/GitHub-MOHITPRADHAN35%2Fagentmesh-181717.svg?style=for-the-badge&logo=github)](https://github.com/MOHITPRADHAN35/agentmesh)
[![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.11+-009688.svg?style=for-the-badge)](https://fastapi.tiangolo.com)
[![Frontend](https://img.shields.io/badge/Frontend-React%2019%20%7C%20XYFlow%20%7C%20Tailwind-3b82f6.svg?style=for-the-badge)](https://react.dev)

> **AgentMesh** is an active persistent-memory and relationship engine for autonomous multi-agent teams. Built natively on **FalkorDB**, AgentMesh transforms ephemeral chat sessions into a living, interconnected knowledge graph. It enables cross-session memory recall, multi-agent state coordination, automatic contradiction detection, and evidence-backed answers with strict graph provenance.

---

## 🏆 Hackathon Tracks Entered

1. **Primary Track: Agent Memory and Coordination**  
   *Enables specialized agents (Researcher, Planner, Reviewer) to share a unified graph state, preserve decisions across isolated sessions, and track how knowledge evolves over time.*
2. **Secondary Track: Company Brain**  
   *Maintains institutional knowledge, traces the historical lineage of architectural choices, and surfaces organizational contradictions before they turn into costly mistakes.*

---

## 📋 Hackathon Submission Deliverables (Rule #10 Compliance)

| Submission Requirement | Implementation / Status | Reference Link |
| :--- | :--- | :--- |
| **1. Public Source-Code Repository** | Open-source repository with full Git history | [github.com/MOHITPRADHAN35/agentmesh](https://github.com/MOHITPRADHAN35/agentmesh) |
| **2. Setup Instructions & Graph Data Model** | Complete instructions + full ASCII schema diagram and node/edge tables | [Jump to Graph Data Model](#-graph-data-model) |
| **3. Cypher Queries & Algorithms** | Multi-hop traversal, contradiction linking, and idempotent ingestion | [Jump to Cypher Queries](#-core-cypher-queries-used-by-agents) |
| **4. Demo Video** | Video walkthrough showing cross-session continuity & contradiction detection | *(Insert your YouTube/Loom/Drive link here)* |
| **5. Live Deployment / Local Setup** | Docker Compose (`docker compose up -d`) & local dev commands verified | [Jump to Setup Instructions](#-quickstart--local-setup) |
| **6. Track Specified** | **Agent Memory and Coordination** (Primary) & **Company Brain** (Secondary) | [Jump to Tracks](#-hackathon-tracks-entered) |

---

## 💡 The Core Problem & FalkorDB Solution

### The Problem
* **Session Amnesia:** Agents lose context the moment a session closes.
* **Factual & Architectural Drift:** As teams converse across multiple days, agents accept conflicting statements (e.g. *"We use Postgres"* on Monday vs *"We use MongoDB"* on Wednesday) without realizing they contradict earlier decisions.
* **Black-Box Reasoning:** Standard LLMs hallucinate answers without verifiable evidence trails or provenance.

### The Shift: FalkorDB as the Context Engine
Instead of treating memory as passive vector text, **FalkorDB acts as an active relational engine**. When an agent learns something new:
1. It traverses historical graph paths across earlier sessions.
2. It detects clashes and links them with `[:CONTRADICTS]`.
3. It preserves both facts with full provenance rather than silently overwriting historical decisions.
4. It connects actionable work with `[:INFORMS]->(:Task)`.

> **FalkorDB is load-bearing:** If you remove FalkorDB, cross-session continuity, contradiction resolution, and task lineage completely collapse. The graph is the engine, not decoration.

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

### Node Schema
| Node Label | Key Properties | Description |
| :--- | :--- | :--- |
| **`Session`** | `id`, `title`, `created_at` | Represents a distinct conversation or workspace session. |
| **`Agent`** | `name`, `role` | Specialized agent identity (`Researcher`, `Planner`, `Reviewer`). |
| **`Memory`** | `id`, `text`, `type`, `confidence`, `source`, `session_id`, `created_at` | Atomic knowledge statement, decision, or constraint. |
| **`Conflict`** | `id`, `reason`, `status` (`open` \| `resolved`), `created_at`, `resolution` | Tracks contradictory assertions between memories. |
| **`Task`** | `id`, `title`, `status`, `priority` | Actionable work items derived from confirmed memories. |

### Edge Schema
* `(:Session)-[:CONTAINS]->(:Memory)`: Chronological containment across user sessions.
* `(:Agent)-[:CREATED]->(:Memory)`: Agent provenance of who extracted or verified the memory.
* `(:Memory)-[:RELATES_TO]->(:Memory)`: Semantic and topic adjacency.
* `(:Memory)-[:SUPPORTS]->(:Memory)`: Validating or reinforcing evidence.
* `(:Memory)-[:CONTRADICTS]->(:Memory)`: Direct clash between incompatible facts/decisions.
* `(:Conflict)-[:INVOLVES]->(:Memory)`: Connects contradiction records to both opposing memories.
* `(:Memory)-[:INFORMS]->(:Task)`: Lineage connecting decisions to executable tasks.

---

## 🤖 Multi-Agent Triad Workflow

```
                        [ User Input ]
                               │
                               ▼
                    [ 1. Researcher Agent ]
             • Extracts facts, decisions, and constraints.
             • Merges new Memory nodes into FalkorDB.
                               │
                               ▼
                    [ 2. Reviewer Agent ]
             • Queries historical memories in FalkorDB.
             • Identifies contradictions (e.g. Postgres vs Mongo).
             • Creates Conflict node & links [:CONTRADICTS] without destroying history.
                               │
                               ▼
                    [ 3. Planner Agent ]
             • Recalls multi-hop graph context across sessions.
             • Derives and links actionable Tasks: Memory -[:INFORMS]-> Task.
                               │
                               ▼
                   [ Grounded Response ]
             • Synthesizes answer citing exact Memory IDs and graph paths.
```

---

## 🔍 Core Cypher Queries Used by Agents

### 1. Ingestion & Provenance Linking (Researcher)
```cypher
MERGE (s:Session {id: $session_id})
MERGE (m:Memory {id: $id})
ON CREATE SET 
  m.text = $text,
  m.type = $type,
  m.confidence = $confidence,
  m.source = $source,
  m.created_at = $created_at,
  m.agent = $agent,
  m.session_id = $session_id
MERGE (s)-[:CONTAINS]->(m)
WITH m
MATCH (a:Agent {name: $agent})
MERGE (a)-[:CREATED]->(m)
```

### 2. Multi-Hop Memory Retrieval across Sessions (Planner)
```cypher
MATCH (m:Memory)
WHERE toLower(m.text) CONTAINS toLower($query) OR m.id IN $seed_ids
OPTIONAL MATCH (m)-[r:RELATES_TO|SUPPORTS]-(related:Memory)
OPTIONAL MATCH (s:Session)-[:CONTAINS]->(m)
RETURN 
  m.id AS id, 
  m.text AS text, 
  m.type AS type,
  collect(DISTINCT related.text) AS related_facts,
  collect(DISTINCT s.id) AS historical_sessions
LIMIT 20
```

### 3. Contradiction Detection & Linking (Reviewer)
```cypher
MATCH (ma:Memory {id: $mem_a_id}), (mb:Memory {id: $mem_b_id})
MERGE (ma)-[:CONTRADICTS]->(mb)
MERGE (mb)-[:CONTRADICTS]->(ma)
CREATE (c:Conflict {
  id: $conflict_id,
  reason: $reason,
  status: 'open',
  created_at: datetime()
})
MERGE (c)-[:INVOLVES]->(ma)
MERGE (c)-[:INVOLVES]->(mb)
RETURN c.id AS conflict_id
```

### 4. Non-Destructive Conflict Resolution
```cypher
MATCH (c:Conflict {id: $conflict_id})
SET c.status = 'resolved', c.resolution = $resolution, c.note = $note
RETURN c.id, c.status
```

---

## 🖥️ Page Tour & Reviewer Guide (UI Analysis)

The AgentMesh interface is engineered as a developer-first, **VS Code-style 4-way resizable workspace** designed for real-time observability of multi-agent reasoning:

```
┌──────────────────┬────────────────────────────────────────────────┬──────────────────┐
│  LEFT SIDEBAR    │  CENTER TOP: CHAT & AGENT TRIAD TIMELINE       │  RIGHT PANEL     │
│                  │  • Active Workspace Title (Inline Editable)    │                  │
│  • Project Select│  • Live Agent Triad Steps (Researcher/Planner) │  • CONFLICTS     │
│  • + New session │  • Assistant Grounded Responses [mem_xxx]      │    Accept A / B  │
│  • Session List  │  • Evidence Citation Tray [Show in Graph]      │    or Keep Both  │
│    - Rename ✏️    │────────────────────────────────────────────────│                  │
│    - Delete 🗑️    │  CENTER BOTTOM: FALKORDB KNOWLEDGE GRAPH       │  • RECALLED      │
│                  │  • Node Types: Session, Agent, Memory, Conflict│    CROSS-SESSION │
│  • Live Health:  │  • Edges: CONTAINS, CREATED, CONTRADICTS       │                  │
│    API & DB      │  • Resolved Edges: SUPERSEDES (Green Arrow)    │  • SEARCHABLE    │
│    Status Dot    │  • 4-Way Resizable Splitter Handle             │    MEMORIES      │
└──────────────────┴────────────────────────────────────────────────┴──────────────────┘
```

### 1. Left Sidebar: Session Lifecycle & Graph Hygiene
* **`+ New session`**: Spawns an isolated session node in FalkorDB with an auto-incremented title (`Session N`).
* **Auto-Titling**: Once the first prompt is sent, the session automatically renames itself to reflect the topic of conversation.
* **Inline Rename (✏️ / Double-Click)**: Hover over any session and click the pencil icon (or double-click) to rename it. Persists directly to FalkorDB via `PATCH /api/sessions/{id}`.
* **Residue-Purging Delete (🗑️)**: Deleting a session executes a cascade delete in FalkorDB—purging the session node, its message history, all associated memories, and orphan conflict links to keep the knowledge graph clean.
* **Live Health Indicator**: Continuously polls `GET /api/health` every 5s; displays `API ok · DB connected` with auto-recovery if services reboot.

### 2. Center-Top: Multi-Agent Triad Execution
* **Researcher Agent**: Scans user input, decomposes statements, and extracts atomic facts, decisions, and constraints with confidence scores.
* **Reviewer Agent**: Evaluates new statements against the entire historical graph to flag contradictions before they cause architectural drift.
* **Planner Agent**: Recalls multi-hop graph context from past sessions to ground answers in verified decisions.
* **Grounded LLM Synthesis**: Powered by Google Gemini (`gemini-2.5-flash`), synthesizing natural, conversational replies citing exact memory bracket tags (e.g. `[mem_c81eefa1]`).
* **Evidence Tray**: Clicking `Evidence · N → show in graph` highlights the cited memory nodes and their dependency chains in the knowledge graph below.

### 3. Center-Bottom: Interactive FalkorDB Graph Canvas
Built with `@xyflow/react` and auto-flexing to any panel height via the drag handle:
* **Node Color Semantics**:
  * 🟢 **Memory** (`#10b981`): Atomic decisions, constraints, or facts.
  * 🟠 **Agent** (`#f97316`): Specialized agent nodes (`Researcher`, `Planner`, `Reviewer`).
  * 🔵 **Session** (`#3b82f6`): Conversation workspace containers.
  * 🔴 **Conflict** (`#ef4444`): Active contradiction records.
* **Edge Semantics**:
  * `[:CONTAINS]`: Session contains memory.
  * `[:CREATED]`: Agent authorship provenance.
  * `[:CONTRADICTS]`: **Red animated edge** highlighting direct clashes between conflicting assertions.
  * `[:SUPERSEDES]`: **Vibrant green directional arrow** created when a conflict is resolved, showing the winning decision superseding the deprecated one!
* **Scope & Filters**: Filter nodes by label (Session, Memory, Agent, Conflict) or switch between `All sessions` and `This session`.

### 4. Right Panel: Context, Contradictions & Memory Explorer
* **Contradiction Cards**: Shows conflicting assertions side-by-side (`Statement A` vs `Statement B`) with the Reviewer's rationale.
* **One-Click Resolution**: Click `Accept A`, `Accept B`, or `Keep both` and confirm to resolve the conflict in FalkorDB.
* **Recalled from Earlier Sessions**: Real-time provenance displaying facts pulled from other workspaces.
* **Live Memory Search**: Filter the entire memory bank across all sessions with instant keyword matching.

---

## ⚡ Reviewer Quick-Test Protocol (2-Minute Evaluation)

Follow these copy-paste steps to test the entire multi-agent cycle in under 2 minutes:

### Test 1: Ingest Technical Decisions (Researcher)
1. In the active session, paste:
   > *"We decided our mobile app will be developed using Flutter, our API rate limit will be set to 100 requests per minute per IP, and our beta testing phase begins on December 1st."*
2. **Observe**:
   - The **Researcher** extracts 3 candidate memories.
   - The session auto-renames to your topic.
   - 3 green `Memory` nodes appear in the Knowledge Graph connected to your session and the `Researcher`.

### Test 2: Trigger Contradiction Detection (Reviewer)
1. In the same or a new session, paste:
   > *"We changed our mind: our mobile app will NOT use Flutter; we must build native iOS and Android apps with Swift and Kotlin."*
2. **Observe**:
   - The **Reviewer** flags an architectural conflict between Flutter and Native Swift/Kotlin.
   - A red animated **`CONTRADICTS`** link connects both memories in the Knowledge Graph.
   - The **Conflicts** badge in the right panel displays an open contradiction card.

### Test 3: Resolve Contradiction & Observe `SUPERSEDES` Link
1. In the right panel, under **Conflicts**, click **Accept B** (Native Swift/Kotlin) and click **Confirm**.
2. **Observe**:
   - The red `CONTRADICTS` link vanishes.
   - A green **`SUPERSEDES`** edge appears pointing from the Native decision &rarr; Flutter decision!
   - The open conflict badge clears to 0.

### Test 4: Cross-Session Grounded Recall (Planner)
1. Click **`+ New session`** in the left sidebar to start a clean workspace.
2. Ask:
   > *"What mobile architecture and API rate limit did we decide on?"*
3. **Observe**:
   - The **Planner** recalls historical facts across sessions from FalkorDB.
   - Gemini synthesizes the answer, correctly stating Native Swift/Kotlin (citing the superseding memory) and the 100 req/min rate limit.
   - Click `Evidence → show in graph` to highlight the exact provenance nodes.

### Test 5: Session Management & Residue Cleanup
1. **Rename**: Hover over your session in the sidebar, click the **Pencil icon** (or double-click), rename it to `Mobile Architecture Plan`, and press Enter.
2. **Delete**: Click the **Trash icon** on any session. Notice that the session, its messages, memories, and graph residue are completely cleaned out of FalkorDB.

---

## ⚙️ Configuration & Environment Variables

### Where to Add API Keys
All backend configuration lives in `backend/.env` (or passed via `docker-compose.yml`):

| Variable | Default | Purpose / Recommended Value |
| :--- | :--- | :--- |
| **`LLM_PROVIDER`** | `gemini` | Choose between `gemini`, `openai`, or `mock` (deterministic offline demo). |
| **`GEMINI_API_KEY`** | *(empty)* | Your Google AI Studio API key (starts with `AIza...`). |
| **`GEMINI_MODEL`** | `gemini-2.5-flash` | Target model for semantic extraction & conversational synthesis. |
| **`OPENAI_API_KEY`** | *(empty)* | Optional: OpenAI key if using `LLM_PROVIDER=openai`. |
| **`FALKORDB_HOST`** | `localhost` (`falkordb` in Docker) | Hostname for the FalkorDB instance. |
| **`FALKORDB_PORT`** | `6379` | Default Redis/FalkorDB port. |
| **`FALKORDB_GRAPH`** | `agentmesh` | Graph namespace in FalkorDB. |

> **Offline / Demo Mode**: Setting `LLM_PROVIDER=mock` enables 100% deterministic, zero-external-dependency execution using local heuristic evaluation and regex contradiction matrices.

---

## 🚀 Quickstart & Local Setup

### System Prerequisites
* **Docker & Docker Desktop** (Windows, macOS, or Linux)
* **Python 3.11+** (for local backend development)
* **Node.js 20+** (for local frontend development)

---

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/MOHITPRADHAN35/agentmesh.git
cd agentmesh

# 2. Add your Gemini API Key in backend/.env (Optional: runs on mock if omitted)
# GEMINI_API_KEY=your_key_here
# LLM_PROVIDER=gemini

# 3. Launch FalkorDB and Backend
docker compose up -d --build
```

Access points:
* 🌐 **Frontend UI:** [http://localhost:8081](http://localhost:8081)
* ⚙️ **Backend API:** [http://localhost:8000](http://localhost:8000)
* 📖 **Swagger OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* 🗄️ **FalkorDB Instance:** `localhost:6379`

---

### Option 2: Local Development Setup

#### Step 1: Start FalkorDB
```bash
docker run -p 6379:6379 -it --name agentmesh-falkordb --rm falkordb/falkordb:latest
```

#### Step 2: Start Backend (FastAPI)
```bash
cd backend
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Step 3: Start Frontend (React 19 + TanStack)
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
# The app opens on http://localhost:8081
```

---

## 🧪 Testing & Verification

### 1. Run Unit & Schema Tests
```bash
cd backend
python -m pytest -v
```
Validates Pydantic contract serialization, contradiction logic, and task planning.

### 2. Query FalkorDB Directly via Redis CLI
```bash
docker exec agentmesh-falkordb redis-cli GRAPH.QUERY agentmesh "MATCH (n) RETURN labels(n)[0] AS Label, count(n) AS Count"
```

---

## 📡 API Reference Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Live database ping and status (`status: "ok"`, `database: true`, `mode: "live"`). |
| `POST` | `/api/sessions` | Create or register a persistent session node in FalkorDB. |
| `GET` | `/api/sessions` | List all sessions with live message and memory counts. |
| `PATCH` | `/api/sessions/{id}` | Rename session title with immediate FalkorDB persistence. |
| `DELETE` | `/api/sessions/{id}` | Cascade-delete session, messages, memories, and orphan conflict edges. |
| `GET` | `/api/sessions/{id}/messages` | Retrieve conversation history with agent execution traces. |
| `POST` | `/api/chat` | Run Researcher ➔ Reviewer ➔ Planner ➔ Synthesizer cycle. |
| `GET` | `/api/memories` | Search and filter memories by query string across all sessions. |
| `GET` | `/api/graph` | Serialize nodes and edges for `@xyflow/react` Knowledge Graph explorer. |
| `GET` | `/api/conflicts` | List open and resolved contradiction pairs (`a` vs `b`). |
| `POST` | `/api/conflicts/{id}/resolve` | Resolve conflict: removes `CONTRADICTS` and links `SUPERSEDES` in FalkorDB. |
| `GET` | `/docs` | Interactive Swagger documentation. |

---

## 📂 Project Structure

```
hackathon/
├── docker-compose.yml                   # FalkorDB + Backend + Frontend compose
├── README.md                            # Comprehensive project guide & Cypher docs
├── overview.md                          # Hackathon challenge overview
├── rules.md                             # Hackathon constraints & deliverables
├── backend/
│   ├── Dockerfile                       # Python 3.11 container
│   ├── requirements.txt                 # FastAPI, FalkorDB, Pydantic, Pytest
│   ├── .env.example & .env              # Environment configurations
│   ├── app/
│   │   ├── main.py                      # FastAPI entrypoint & CORS
│   │   ├── config.py                    # Settings configuration
│   │   ├── models/schemas.py            # Pydantic models for API contracts
│   │   ├── services/
│   │   │   ├── graph_service.py         # Official FalkorDB client & Cypher engine
│   │   │   ├── agent_orchestrator.py    # Researcher -> Reviewer -> Planner cycle
│   │   │   └── llm_provider.py          # Deterministic engine + provider abstraction
│   │   ├── agents/
│   │   │   ├── researcher.py            # Candidate extraction
│   │   │   ├── reviewer.py              # Contradiction detection
│   │   │   └── planner.py               # Context retrieval & task planning
│   │   └── api/
│   │       ├── health.py, sessions.py, chat.py
│   │       ├── memories.py, graph.py, conflicts.py
│   │   └── scripts/seed_demo.py         # Demo data seed script
│   └── tests/
│       ├── test_conflicts.py            # Contradiction evaluation tests
│       └── test_graph.py                # Graph serialization tests
└── frontend/
    ├── Dockerfile                       # Node 22 container
    ├── package.json                     # React 19, @xyflow/react, Tailwind v4
    ├── vite.config.ts                   # TanStack Start / Vite config
    └── src/
        ├── routes/index.tsx             # 4-way VS Code resizable dashboard
        ├── components/
        │   ├── chat/Workspace.tsx       # Multi-agent chat interface
        │   ├── graph/GraphExplorer.tsx  # @xyflow/react Knowledge Graph
        │   ├── conflicts/ConflictPanel.tsx # Contradiction resolution cards
        │   └── ui/resizable.tsx         # VS Code splitters
        └── services/api.ts              # API client connecting to backend
```

---

## 👥 Contributors & Team

* **Mohit Pradhan** — [@MOHITPRADHAN35](https://github.com/MOHITPRADHAN35)
* **Aditya** — [@Aditya-ha11](https://github.com/Aditya-ha11)

---

## ⚖️ Hackathon Compliance Disclosure
* **Required Technology:** FalkorDB is the primary, load-bearing database.
* **AI Tool Disclosure:** Antigravity AI assistant was used for scaffolding, refactoring, and test authoring. All architecture, Cypher design, and graph data modeling have been thoroughly verified and tested.

