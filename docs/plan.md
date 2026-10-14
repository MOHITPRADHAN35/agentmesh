# AGENTMESH BACKEND — HACKATHON IMPLEMENTATION BRIEF

You are the backend engineer for AgentMesh, a demo-first multi-agent persistent-memory application for the FalkorDB Graph Hacks hackathon.

## Objective

Build a working FastAPI backend in which FalkorDB is the primary persistent memory and relationship engine. The application must demonstrate cross-session memory, shared agent state, graph-based retrieval, contradiction detection, and evidence-backed answers.

## Technology

* Python 3.11+
* FastAPI and Uvicorn
* Pydantic
* Official FalkorDB Python client and supported Cypher queries
* An LLM provider abstraction for structured extraction and response synthesis
* Docker Compose for reproducible local setup

Verify the currently supported client APIs and query syntax against the official documentation. Do not invent client methods.

## Required modules

Create a maintainable structure similar to:

backend/
app/
main.py
config.py
api/
health.py
sessions.py
chat.py
memories.py
graph.py
conflicts.py
services/
graph_service.py
memory_service.py
retrieval_service.py
conflict_service.py
agent_orchestrator.py
llm_provider.py
models/
schemas.py
agents/
researcher.py
planner.py
reviewer.py
tests/
Dockerfile
requirements.txt
.env.example

Adjust the structure if needed, but maintain clear separation between HTTP routes, business logic, graph access, and LLM calls.

## Graph data model

Implement these nodes with stable unique IDs:

* Memory: content, memory_type, timestamp, confidence, source, project_id
* Agent: name, role
* Session: session_id, created_at, project_id
* Task: title, status, priority, project_id
* Conflict: status, explanation, project_id

Implement relationships:

* Agent -[:CREATED]-> Memory
* Session -[:CONTAINS]-> Memory
* Memory -[:RELATES_TO]-> Memory
* Memory -[:SUPPORTS]-> Memory
* Memory -[:CONTRADICTS]-> Memory
* Memory -[:INFORMS]-> Task
* Conflict -[:INVOLVES]-> Memory

Use stable identifiers and idempotent writes. Create indexes or constraints where supported. Scope all queries by project_id. Never interpolate user input into Cypher strings.

## Agent workflow

Implement a deterministic orchestrator with three specialized agents:

1. Researcher: extracts candidate facts, decisions, evidence, and questions from the current message.
2. Planner: retrieves related graph memories and creates or updates tasks based on the current context.
3. Reviewer: compares new information with related existing memories and identifies possible contradictions.

Persist validated memories and their relationships in FalkorDB. Retrieve relevant context through graph traversal before synthesizing an answer.

Do not claim that the LLM performed a graph query unless the backend actually executed that query. Do not report a memory as persisted until the graph write succeeds.

## Contradiction handling

Implement a conservative MVP:

* Compare new candidate facts with relevant existing memories.
* Use explicit relationship types and a conflict record when a contradiction is sufficiently supported.
* Preserve both original memories and their provenance.
* Mark the conflict as open.
* Allow a user to resolve it by accepting one fact, retaining both with context, or marking it unresolved.
* Do not silently overwrite historical decisions.
* Return the supporting memory IDs and explanations to the frontend.

If LLM access is unavailable, use a deterministic demo provider that supports the same interfaces and produces clearly labeled demo results. Never pretend the fallback is a live model.

## Required API

Implement and document:

* GET /api/health
* POST /api/sessions
* GET /api/sessions
* POST /api/chat
* GET /api/memories?query=...
* GET /api/graph?session_id=...
* GET /api/conflicts
* POST /api/conflicts/{id}/resolve

Follow the shared API contract defined by the project owner. Use Pydantic request and response models, consistent errors, and appropriate HTTP status codes. Enable CORS only for configured frontend origins.

## Quality requirements

* Use environment variables for database configuration and LLM credentials.
* Never commit secrets.
* Add unit tests for conflict detection, graph serialization, and response validation.
* Add integration tests for graph persistence and cross-session retrieval.
* Include a health check that verifies actual FalkorDB connectivity.
* Provide seed/demo data through an explicit development command, not hidden startup side effects.
* Log failures and agent steps without leaking API keys or sensitive prompt content.
* Add structured provenance to all memory-backed answers.
* Keep the implementation small enough to finish and test within the hackathon.

## Definition of done

1. Docker Compose starts FalkorDB and the backend.
2. /api/health reports the real database status.
3. A message creates persistent graph memories.
4. A second session retrieves memories from the first session.
5. A contradictory statement creates a visible conflict while preserving both facts.
6. The graph endpoint returns connected nodes and edges.
7. The frontend can call every required endpoint.
8. README instructions and tests work from a clean checkout.

Build in small, testable increments. Explain important architecture choices, run tests, and report actual failures. Do not merely generate files and claim success.
