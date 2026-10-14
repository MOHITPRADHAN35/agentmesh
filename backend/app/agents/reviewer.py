import logging
from typing import List, Dict, Any, Optional
from app.services.graph_service import graph_service
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger("agentmesh.reviewer")

class ReviewerAgent:
    def __init__(self):
        self.name = "Reviewer"
        self.role = "Contradiction and consistency validator"
        self.llm = get_llm_provider()

    def process(
        self,
        candidate_memory: Dict[str, Any],
        project_id: str,
        persisted_memory_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Compares candidate memory with existing project memories.
        If a contradiction is detected, creates a Conflict node in FalkorDB
        and links the two memories with [:CONTRADICTS].
        """
        logger.info(f"Reviewer verifying consistency for memory: {persisted_memory_id}")

        # Fetch recent project memories to cross-examine
        existing_memories = graph_service.search_memories(project_id=project_id, limit=30)
        # Filter out the newly created memory itself
        other_memories = [m for m in existing_memories if m["id"] != persisted_memory_id]

        if not other_memories:
            return None

        conflict_eval = self.llm.evaluate_contradiction(candidate_memory["content"], other_memories)

        if conflict_eval:
            conflicting_id = conflict_eval["conflicting_memory_id"]
            explanation = conflict_eval["explanation"]
            logger.warning(f"Contradiction found! Memory {persisted_memory_id} clashes with {conflicting_id}")

            conflict_record = graph_service.create_conflict(
                explanation=explanation,
                project_id=project_id,
                memory_ids=[persisted_memory_id, conflicting_id]
            )
            return conflict_record

        return None

reviewer_agent = ReviewerAgent()
