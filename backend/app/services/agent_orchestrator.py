import uuid
import logging
from datetime import datetime
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

    def process_chat(self, message: str, session_id: str, project_id: str = "default_project") -> Dict[str, Any]:
        # Always pick up active configured LLM provider
        self.llm = get_llm_provider()
        now = datetime.utcnow().isoformat()
        user_msg_id = f"msg_{uuid.uuid4().hex[:6]}"
        assistant_msg_id = f"msg_{uuid.uuid4().hex[:6]}"

        # Save user message
        graph_service.save_message(session_id, {
            "id": user_msg_id,
            "role": "user",
            "content": message,
            "created_at": now
        })

        steps = []
        created_memories = []
        evidence_list = []
        retrieved_ids = []

        # 1. Researcher Step (Memory Extraction)
        candidates = researcher_agent.process(message)
        steps.append({
            "agent": "Researcher",
            "status": "done",
            "output": f"Extracted {len(candidates)} candidate memories from message."
        })

        for cand in candidates:
            mem = graph_service.create_memory(
                text=cand["content"],
                memory_type=cand["memory_type"],
                confidence=cand["confidence"],
                source="user",
                project_id=project_id,
                agent_name="Researcher",
                session_id=session_id
            )
            created_memories.append(mem)

        created_ids = [m["id"] for m in created_memories]

        # 2. Reviewer Step (Contradiction Check)
        conflict_detected = None
        for mem in created_memories:
            existing = [m for m in graph_service.search_memories() if m["id"] != mem["id"]]
            conflict_eval = self.llm.evaluate_contradiction(mem["text"], existing)
            if conflict_eval:
                conflicting_mem = next((m for m in existing if m["id"] == conflict_eval["conflicting_memory_id"]), None)
                if conflicting_mem:
                    conflict_detected = graph_service.create_conflict(
                        reason=conflict_eval["explanation"],
                        memory_a=conflicting_mem,
                        memory_b=mem
                    )
                    break

        if conflict_detected:
            steps.append({
                "agent": "Reviewer",
                "status": "done",
                "output": f"Contradiction flagged! Reviewer logged conflict #{conflict_detected['id']}."
            })
        else:
            steps.append({
                "agent": "Reviewer",
                "status": "done",
                "output": "Consistency verified. No contradictions found with historical decisions."
            })

        # 3. Planner Step (Graph Context Retrieval)
        all_memories = graph_service.search_memories()
        related_memories = [m for m in all_memories if m["id"] not in created_ids]

        # Find most relevant memories (keyword/semantic overlap)
        words = set(message.lower().split())
        scored = []
        for m in related_memories:
            m_words = set(m.get("text", "").lower().split())
            score = len(words & m_words)
            scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        relevant_memories = [m for _, m in scored[:4]] if scored else related_memories[:4]

        for m in relevant_memories:
            retrieved_ids.append(m["id"])
            evidence_list.append({
                "memory_id": m["id"],
                "text": m["text"],
                "source": m.get("source", "graph")
            })

        steps.append({
            "agent": "Planner",
            "status": "done",
            "output": f"Recalled {len(evidence_list)} historical facts from FalkorDB graph."
        })

        # 4. LLM Synthesis
        conflicts_for_synth = []
        if conflict_detected:
            conflicts_for_synth.append({
                "explanation": conflict_detected.get("reason"),
                "conflict_id": conflict_detected.get("id")
            })

        tasks = self.llm.plan_tasks(message, relevant_memories)

        synth_result = self.llm.synthesize_response(
            message=message,
            retrieved_memories=relevant_memories,
            conflicts=conflicts_for_synth,
            tasks=tasks
        )

        content = synth_result.get("response", "")
        if not content:
            if conflict_detected:
                content = f"I've recorded your update, but flagged an architectural conflict with an earlier decision:\n\n• {conflict_detected['reason']}\n\nBoth facts are preserved in FalkorDB with a CONTRADICTS link."
            elif evidence_list:
                content = f"Based on cross-session context in FalkorDB:\n\n" + "\n".join([f"• [{e['memory_id']}] {e['text']}" for e in evidence_list])
            else:
                content = f"Noted. I've committed this knowledge to the FalkorDB graph under session {session_id}."

        assistant_message = {
            "id": assistant_msg_id,
            "role": "assistant",
            "content": content,
            "created_at": datetime.utcnow().isoformat(),
            "evidence": evidence_list,
            "steps": steps,
            "provider": "live" if "Gemini" in getattr(self.llm, "provider_name", "") else "deterministic",
            "retrieved_memory_ids": retrieved_ids
        }

        # Save assistant message
        graph_service.save_message(session_id, assistant_message)

        # Update session title if it's currently a generic name
        sessions = graph_service.list_sessions(project_id)
        curr_session = next((s for s in sessions if s["id"] == session_id), None)
        if curr_session and (curr_session.get("title", "").startswith("Session ") or curr_session.get("title", "").startswith("sess_")):
            clean_title = message.strip()
            if len(clean_title) > 35:
                clean_title = clean_title[:32] + "..."
            graph_service.update_session_title(session_id, clean_title)

        return {
            "session_id": session_id,
            "message": assistant_message,
            "created_memory_ids": created_ids
        }

orchestrator = AgentOrchestrator()
