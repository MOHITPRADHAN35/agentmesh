import logging
from typing import List, Dict, Any
from app.services.graph_service import graph_service
from app.services.llm_provider import get_llm_provider
from app.agents.researcher import researcher_agent
from app.agents.reviewer import reviewer_agent
from app.agents.planner import planner_agent

logger = logging.getLogger("agentmesh.orchestrator")

class AgentOrchestrator:
    def __init__(self):
        self.llm = get_llm_provider()

    def process_chat(self, message: str, session_id: str, project_id: str) -> Dict[str, Any]:
        agent_steps = []
        persisted_memories = []
        conflicts_detected = []

        # Ensure session exists in graph
        graph_service.create_session(session_id, project_id)

        # ----------------------------------------------------
        # STEP 1: Researcher extracts candidate knowledge
        # ----------------------------------------------------
        candidates = researcher_agent.process(message)
        agent_steps.append({
            "agent": "Researcher",
            "action": "extracted_candidates",
            "details": {"count": len(candidates), "candidates": [c["content"] for c in candidates]}
        })

        # ----------------------------------------------------
        # STEP 2: Persist new candidate memories in FalkorDB
        # ----------------------------------------------------
        for cand in candidates:
            mem = graph_service.create_memory(
                content=cand["content"],
                memory_type=cand["memory_type"],
                confidence=cand["confidence"],
                source=cand["source"],
                project_id=project_id,
                agent_name=researcher_agent.name,
                session_id=session_id
            )
            persisted_memories.append(mem)

        persisted_ids = [m["id"] for m in persisted_memories]

        # Link sequential memories if multiple extracted
        if len(persisted_ids) > 1:
            for i in range(len(persisted_ids) - 1):
                graph_service.link_memories(persisted_ids[i], persisted_ids[i + 1], "RELATES_TO")

        # ----------------------------------------------------
        # STEP 3: Reviewer checks for contradictions
        # ----------------------------------------------------
        for mem in persisted_memories:
            conflict = reviewer_agent.process(mem, project_id, mem["id"])
            if conflict:
                conflicts_detected.append(conflict)
                agent_steps.append({
                    "agent": "Reviewer",
                    "action": "detected_contradiction",
                    "details": {
                        "conflict_id": conflict["id"],
                        "explanation": conflict["explanation"],
                        "involved_memories": conflict["involved_memory_ids"]
                    }
                })

        # ----------------------------------------------------
        # STEP 4: Planner retrieves graph context & updates tasks
        # ----------------------------------------------------
        planner_result = planner_agent.process(message, project_id, persisted_ids)
        retrieved_memories = planner_result["related_memories"]
        new_tasks = planner_result["created_tasks"]

        agent_steps.append({
            "agent": "Planner",
            "action": "retrieved_and_planned",
            "details": {
                "retrieved_count": len(retrieved_memories),
                "tasks_created": [t["title"] for t in new_tasks]
            }
        })

        # ----------------------------------------------------
        # STEP 5: Response Synthesis with Provenance
        # ----------------------------------------------------
        # Combine all relevant memories for grounded synthesis
        all_context_memories = persisted_memories + retrieved_memories
        synthesis = self.llm.synthesize_response(
            message=message,
            retrieved_memories=all_context_memories,
            conflicts=conflicts_detected,
            tasks=new_tasks
        )

        return {
            "response": synthesis["response"],
            "session_id": session_id,
            "project_id": project_id,
            "persisted_memories": persisted_memories,
            "retrieved_memories": retrieved_memories,
            "new_tasks": new_tasks,
            "conflicts_detected": conflicts_detected,
            "agent_steps": agent_steps,
            "provenance": synthesis["provenance"]
        }

orchestrator = AgentOrchestrator()
