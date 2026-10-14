import re
import json
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from app.config import settings

logger = logging.getLogger("agentmesh.llm_provider")

class BaseLLMProvider(ABC):
    @abstractmethod
    def extract_candidates(self, message: str) -> List[Dict[str, Any]]:
        """Extract candidate facts, decisions, and constraints from the message."""
        pass

    @abstractmethod
    def evaluate_contradiction(self, new_fact: str, existing_memories: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Check if new_fact contradicts any existing memory."""
        pass

    @abstractmethod
    def plan_tasks(self, message: str, context_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify actionable tasks implied by the message or context."""
        pass

    @abstractmethod
    def synthesize_response(
        self,
        message: str,
        retrieved_memories: List[Dict[str, Any]],
        conflicts: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate response grounded in retrieved memories."""
        pass


class MockDeterministicProvider(BaseLLMProvider):
    """
    Deterministic offline demo provider.
    Fulfills hackathon requirement: reproducible, zero external dependency,
    clearly labeled demo outputs.
    """
    def __init__(self):
        self.provider_name = "Deterministic Demo Provider (Offline)"

    def extract_candidates(self, message: str) -> List[Dict[str, Any]]:
        candidates = []
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", message) if len(s.strip()) > 3]

        for s in sentences:
            s_lower = s.lower()
            # Classify type
            if any(w in s_lower for w in ["decide", "we chose", "chosen", "agreed on", "will use", "selected", "switched to"]):
                mtype = "decision"
                confidence = 0.95
            elif any(w in s_lower for w in ["must", "cannot", "never", "only", "require", "limit", "restriction"]):
                mtype = "constraint"
                confidence = 0.90
            else:
                mtype = "fact"
                confidence = 0.85

            candidates.append({
                "content": s,
                "memory_type": mtype,
                "confidence": confidence,
                "source": "user"
            })
        return candidates

    def evaluate_contradiction(self, new_fact: str, existing_memories: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Detects opposing claims or incompatible tech choices.
        e.g. "We will use PostgreSQL" vs "We will use MongoDB"
        """
        nf_lower = new_fact.lower()

        # Incompatible domain pairs
        incompatibilities = [
            ("postgresql", "mongodb"),
            ("postgres", "mysql"),
            ("python", "rust"),
            ("fastapi", "django"),
            ("fastapi", "flask"),
            ("react", "vue"),
            ("port 8000", "port 3000"),
            ("port 8080", "port 8000"),
            ("falkordb", "neo4j"),
            ("redis", "memcached"),
            ("aws", "gcp"),
            ("aws", "azure"),
            ("single-node", "distributed"),
            ("remote", "in-person")
        ]

        negation_patterns = [
            (r"\bnot\b", r"\bis\b"),
            (r"\bdisabled\b", r"\benabled\b"),
            (r"\btrue\b", r"\bfalse\b"),
            (r"\bforbidden\b", r"\ballowed\b")
        ]

        for mem in existing_memories:
            existing_content = mem.get("content", "").lower()

            # Check incompatibility pairs
            for term_a, term_b in incompatibilities:
                if (term_a in nf_lower and term_b in existing_content) or (term_b in nf_lower and term_a in existing_content):
                    return {
                        "conflicting_memory_id": mem["id"],
                        "explanation": f"Conflict detected between '{term_a}' and '{term_b}' choices. Existing memory claims '{mem['content']}' while new statement asserts '{new_fact}'."
                    }

            # Check direct negation of shared subject
            words_new = set(re.findall(r"\w+", nf_lower))
            words_exist = set(re.findall(r"\w+", existing_content))
            common_keywords = (words_new & words_exist) - {"we", "the", "a", "is", "are", "will", "use", "for", "to", "in", "on", "our"}

            if len(common_keywords) >= 2:
                for neg, pos in negation_patterns:
                    if (re.search(neg, nf_lower) and not re.search(neg, existing_content)) or \
                       (re.search(neg, existing_content) and not re.search(neg, nf_lower)):
                        return {
                            "conflicting_memory_id": mem["id"],
                            "explanation": f"Opposing assertions regarding {list(common_keywords)[:3]}: '{mem['content']}' vs '{new_fact}'."
                        }

        return None

    def plan_tasks(self, message: str, context_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks = []
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["todo", "need to", "implement", "create", "build", "fix", "setup", "configure"]):
            # Derive action
            title = message.strip()
            if len(title) > 60:
                title = title[:57] + "..."
            tasks.append({
                "title": f"Action: {title}",
                "priority": "high" if "urgent" in msg_lower or "critical" in msg_lower else "medium"
            })
        return tasks

    def synthesize_response(
        self,
        message: str,
        retrieved_memories: List[Dict[str, Any]],
        conflicts: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        provenance = [m["id"] for m in retrieved_memories]

        lines = []
        if conflicts:
            lines.append("⚠️ **Attention: Architectural Conflict Detected!**")
            for c in conflicts:
                lines.append(f"- {c['explanation']}")
            lines.append("\nBoth memories have been preserved in FalkorDB with a `CONTRADICTS` link. You can resolve this via `/api/conflicts`.")

        lines.append("\n### Context Recalled from FalkorDB:")
        if retrieved_memories:
            for m in retrieved_memories[:4]:
                lines.append(f"- `[{m['id']}]` ({m.get('memory_type', 'fact').upper()}) *{m['content']}* (from Session `{m.get('session_id', 'unknown')}`)")
        else:
            lines.append("- *(No prior related memories found. This statement seeds fresh context.)*")

        if tasks:
            lines.append("\n### Tasks Created & Linked:")
            for t in tasks:
                lines.append(f"- **[{t.get('priority', 'medium').upper()}]** {t['title']}")

        lines.append(f"\n*(Generated via {self.provider_name}. Citing {len(provenance)} graph memory sources)*")

        return {
            "response": "\n".join(lines),
            "provenance": provenance
        }


def get_llm_provider() -> BaseLLMProvider:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "mock":
        return MockDeterministicProvider()
    # Default to MockDeterministicProvider for zero-friction hackathon demos
    return MockDeterministicProvider()
