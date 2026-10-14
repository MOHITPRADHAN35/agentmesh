import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.graph_service import graph_service
from app.services.agent_orchestrator import orchestrator

def seed():
    print("🌱 Initializing FalkorDB indices...")
    graph_service.init_indices()

    print("\n--- 1. Simulating Session 1 (Architecture Setup) ---")
    s1 = graph_service.create_session(title="Architecture Setup")
    msg1 = "We decided to use PostgreSQL for our persistent database and FastAPI for the backend."
    res1 = orchestrator.process_chat(message=msg1, session_id=s1["id"])
    print(f"Session 1 Processed: {len(res1['created_memory_ids'])} memories persisted.")

    print("\n--- 2. Simulating Session 2 (Cross-Session Contradiction) ---")
    s2 = graph_service.create_session(title="Revision & Contradiction")
    msg2 = "We switched to MongoDB for our database because of dynamic document schema."
    res2 = orchestrator.process_chat(message=msg2, session_id=s2["id"])
    conflicts = graph_service.list_conflicts()
    print(f"Session 2 Processed: {len(conflicts)} contradiction(s) registered in graph!")

    health = graph_service.check_health()
    print(f"\n✅ Seed completed! Database health: {health['status']}, Mode: {health['mode']}")

if __name__ == "__main__":
    seed()
