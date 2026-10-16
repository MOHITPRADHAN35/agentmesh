import re
import json
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import httpx
from app.config import settings

logger = logging.getLogger("agentmesh.llm_provider")

class BaseLLMProvider(ABC):
    provider_name: str = "Base Provider"

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
        nf_lower = new_fact.lower()

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
            existing_content = (mem.get("text") or mem.get("content") or "").lower()

            for term_a, term_b in incompatibilities:
                if (term_a in nf_lower and term_b in existing_content) or (term_b in nf_lower and term_a in existing_content):
                    return {
                        "conflicting_memory_id": mem["id"],
                        "explanation": f"Conflict detected between '{term_a}' and '{term_b}' choices. Existing memory claims '{mem.get('text') or mem.get('content')}' while new statement asserts '{new_fact}'."
                    }

            words_new = set(re.findall(r"\w+", nf_lower))
            words_exist = set(re.findall(r"\w+", existing_content))
            common_keywords = (words_new & words_exist) - {"we", "the", "a", "is", "are", "will", "use", "for", "to", "in", "on", "our"}

            if len(common_keywords) >= 2:
                for neg, pos in negation_patterns:
                    if (re.search(neg, nf_lower) and not re.search(neg, existing_content)) or \
                       (re.search(neg, existing_content) and not re.search(neg, nf_lower)):
                        return {
                            "conflicting_memory_id": mem["id"],
                            "explanation": f"Opposing assertions regarding {list(common_keywords)[:3]}: '{mem.get('text') or mem.get('content')}' vs '{new_fact}'."
                        }

        return None

    def plan_tasks(self, message: str, context_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks = []
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["todo", "need to", "implement", "create", "build", "fix", "setup", "configure"]):
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
        provenance = [m.get("id") for m in retrieved_memories if m.get("id")]
        lines = []

        if conflicts:
            lines.append("⚠️ **Architectural Conflict Detected**")
            for c in conflicts:
                reason = c.get("explanation") or c.get("reason", "Incompatible decisions detected.")
                lines.append(f"• {reason}")
            lines.append("\nBoth decisions have been recorded in FalkorDB with a `CONTRADICTS` link. You can review and resolve this conflict in the right panel.")
        elif retrieved_memories:
            lines.append("Based on our project's persistent knowledge graph in FalkorDB:")
            for m in retrieved_memories[:4]:
                mid = m.get("id", "mem")
                mtext = m.get("text") or m.get("content") or ""
                lines.append(f"• [{mid}] {mtext}")
            lines.append("\nI've linked this context into our conversation.")
        else:
            lines.append("I've analyzed your input and committed these facts into the FalkorDB knowledge graph for cross-session recall.")

        if tasks:
            lines.append("\n**Action Items Identified:**")
            for t in tasks:
                lines.append(f"• [{t.get('priority', 'medium').upper()}] {t['title']}")

        return {
            "response": "\n".join(lines),
            "provenance": provenance
        }


class GeminiLLMProvider(BaseLLMProvider):
    """
    Live Google Gemini LLM Provider using Google AI Studio API key.
    Provides semantic reasoning, candidate memory extraction, and conflict evaluation.
    """
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.provider_name = f"Google Gemini ({model})"
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        self.fallback = MockDeterministicProvider()

    def _call_gemini(self, prompt: str, system_instruction: str = "", json_mode: bool = False) -> Optional[str]:
        try:
            payload: Dict[str, Any] = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                }
            }
            if json_mode:
                payload["generationConfig"]["responseMimeType"] = "application/json"

            if system_instruction:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_instruction}]
                }

            headers = {"Content-Type": "application/json"}
            resp = httpx.post(self.endpoint, headers=headers, json=payload, timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
            else:
                logger.warning(f"Gemini API error (status {resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
        return None

    def extract_candidates(self, message: str) -> List[Dict[str, Any]]:
        prompt = (
            "Analyze the following user statement and extract atomic facts, decisions, and constraints.\n"
            "Return a JSON array of objects with keys:\n"
            "- \"content\": string (the atomic extracted statement)\n"
            "- \"memory_type\": one of \"decision\", \"constraint\", or \"fact\"\n"
            "- \"confidence\": float between 0.8 and 1.0\n"
            "- \"source\": \"user\"\n\n"
            f"User statement: \"{message}\""
        )
        resp_text = self._call_gemini(
            prompt,
            system_instruction="You are an expert knowledge extraction agent for a multi-agent system. Output only raw JSON array.",
            json_mode=True
        )
        if resp_text:
            try:
                parsed = json.loads(resp_text)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except Exception as e:
                logger.warning(f"Failed to parse Gemini candidate extraction: {e}. Falling back.")
        return self.fallback.extract_candidates(message)

    def evaluate_contradiction(self, new_fact: str, existing_memories: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not existing_memories:
            return None

        mem_summaries = []
        for m in existing_memories:
            mid = m.get("id")
            mtext = m.get("text") or m.get("content") or ""
            mem_summaries.append(f"Memory [{mid}]: {mtext}")

        prompt = (
            "You are an architectural consistency reviewer for an engineering team.\n"
            f"NEW STATEMENT: \"{new_fact}\"\n\n"
            "EXISTING RECORDED MEMORIES:\n" + "\n".join(mem_summaries) + "\n\n"
            "Check if NEW STATEMENT contradicts, conflicts with, or reverses ANY of the existing recorded memories.\n"
            "Return a JSON object with this exact schema:\n"
            "{\n"
            "  \"has_conflict\": boolean,\n"
            "  \"conflicting_memory_id\": string or null,\n"
            "  \"explanation\": string or null\n"
            "}"
        )
        resp_text = self._call_gemini(prompt, json_mode=True)
        if resp_text:
            try:
                parsed = json.loads(resp_text)
                if isinstance(parsed, dict):
                    if parsed.get("has_conflict") and parsed.get("conflicting_memory_id"):
                        return {
                            "conflicting_memory_id": parsed["conflicting_memory_id"],
                            "explanation": parsed.get("explanation") or f"Conflict detected with memory {parsed['conflicting_memory_id']}"
                        }
                    elif not parsed.get("has_conflict"):
                        return None
            except Exception as e:
                logger.warning(f"Failed to parse Gemini contradiction evaluation: {e}. Falling back.")

        return self.fallback.evaluate_contradiction(new_fact, existing_memories)

    def plan_tasks(self, message: str, context_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prompt = (
            f"Given the user message: \"{message}\"\n"
            "Identify if there are any concrete tasks or TODO action items implied.\n"
            "Return a JSON array: [{\"title\": \"Action: ...\", \"priority\": \"high\"|\"medium\"|\"low\"}]\n"
            "If no tasks are implied, return []."
        )
        resp_text = self._call_gemini(prompt, json_mode=True)
        if resp_text:
            try:
                parsed = json.loads(resp_text)
                if isinstance(parsed, list):
                    return parsed
            except Exception as e:
                logger.warning(f"Failed to parse Gemini tasks: {e}. Falling back.")
        return self.fallback.plan_tasks(message, context_memories)

    def synthesize_response(
        self,
        message: str,
        retrieved_memories: List[Dict[str, Any]],
        conflicts: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        provenance = [m.get("id") for m in retrieved_memories if m.get("id")]

        context_lines = []
        for m in retrieved_memories:
            mid = m.get("id", "mem")
            mtext = m.get("text") or m.get("content") or ""
            mtype = m.get("type") or m.get("memory_type") or "fact"
            context_lines.append(f"- [{mid}] ({mtype}): {mtext}")

        conflict_lines = []
        for c in conflicts:
            conflict_lines.append(f"- Conflict: {c.get('explanation') or c.get('reason')}")

        task_lines = []
        for t in tasks:
            task_lines.append(f"- [{t.get('priority', 'medium').upper()}] {t.get('title')}")

        prompt = (
            f"User message: \"{message}\"\n\n"
            f"Context recalled from project FalkorDB graph:\n" + ("\n".join(context_lines) if context_lines else "None") + "\n\n"
            f"Detected architectural conflicts:\n" + ("\n".join(conflict_lines) if conflict_lines else "None") + "\n\n"
            f"Identified tasks:\n" + ("\n".join(task_lines) if task_lines else "None") + "\n\n"
            "Instructions:\n"
            "1. Answer the user conversationally and directly like a helpful, intelligent AI engineering assistant.\n"
            "2. If answering a question based on the recalled context, directly state the answer and cite the memory bracket tag (e.g. [mem_xxx]).\n"
            "3. If an architectural conflict was detected, alert the user about the conflict and mention that it's flagged in the conflict panel.\n"
            "4. Keep the tone professional, friendly, and concise without robotic boilerplate."
        )

        resp_text = self._call_gemini(
            prompt,
            system_instruction="You are AgentMesh, an intelligent engineering team assistant backed by persistent FalkorDB memory."
        )

        if resp_text and len(resp_text.strip()) > 5:
            return {
                "response": resp_text.strip(),
                "provenance": provenance
            }

        return self.fallback.synthesize_response(message, retrieved_memories, conflicts, tasks)


def get_llm_provider() -> BaseLLMProvider:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini" and settings.GEMINI_API_KEY:
        model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        logger.info(f"Using GeminiLLMProvider with model {model}")
        return GeminiLLMProvider(api_key=settings.GEMINI_API_KEY, model=model)
    return MockDeterministicProvider()
