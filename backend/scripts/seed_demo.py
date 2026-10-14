"""
Explicit seed script for AgentMesh hackathon demonstration.
Fulfills plan.md quality requirement:
"Provide seed/demo data through an explicit development command, not hidden startup side effects."
"""
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.graph_service import graph_service
from app.services.agent_orchestrator import orchestrator

def seed():
    print("🌱 Initializing FalkorDB indices...")
    graph_service.init_indices()

    project_id = "default_project"

    print("\n--- 1. Simulating Session 1 (Architecture Setup) ---")
    msg1 = "We decided to use PostgreSQL for our persistent database and FastAPI for the backend."
    res1 = orchestrator.process_chat(message=msg1, session_id="session-1", project_id=project_id)
    print(f"Session 1 Processed: {len(res1['persisted_memories'])} memories persisted.")

    print("\n--- 2. Simulating Session 2 (Cross-Session Contradiction) ---")
    msg2 = "We switched to MongoDB for our database because of dynamic document schema."
    res2 = orchestrator.process_chat(message=msg2, session_id="session-2", project_id=project_id)
    print(f"Session 2 Processed: {len(res2['conflicts_detected'])} contradiction(s) detected across sessions!")

    print("\n--- 3. Simulating Session 3 (Task Creation) ---")
    msg3 = "We need to implement the conflict resolution endpoint and write unit tests."
    res3 = orchestrator.process_chat(message=msg3, session_id="session-3", project_id=project_id)
    print(f"Session 3 Processed: {len(res3['new_tasks'])} task(s) generated.")

    health = graph_service.check_health()
    print(f"\n✅ Seed completed! Database health: {health['status']}, Nodes: {health['node_count']}, Edges: {health['edge_count']}")

if __name__ == "__main__":
    seed()
