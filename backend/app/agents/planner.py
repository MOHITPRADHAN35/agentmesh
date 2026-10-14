import logging
from typing import List, Dict, Any
from app.services.graph_service import graph_service
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger("agentmesh.planner")

class PlannerAgent:
    def __init__(self):
        self.name = "Planner"
        self.role = "Context retriever and task coordinator"
        self.llm = get_llm_provider()

    def process(
        self,
        message: str,
        project_id: str,
        active_memory_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Retrieves graph memories related to the active memories,
        and derives actionable tasks, linking Memory -[:INFORMS]-> Task.
        """
        logger.info(f"Planner recalling multi-hop context for project {project_id}")

        # 1. Multi-hop traversal in FalkorDB
        related_memories = graph_service.get_related_memories(project_id, active_memory_ids)

        # 2. Plan new tasks if indicated
        planned_task_specs = self.llm.plan_tasks(message, related_memories)
        created_tasks = []

        for spec in planned_task_specs:
            task = graph_service.create_task(
                title=spec["title"],
                priority=spec.get("priority", "medium"),
                project_id=project_id,
                informing_memory_ids=active_memory_ids
            )
            created_tasks.append(task)
            logger.info(f"Planner registered task: {task['id']} - {task['title']}")

        return {
            "related_memories": related_memories,
            "created_tasks": created_tasks
        }

planner_agent = PlannerAgent()
