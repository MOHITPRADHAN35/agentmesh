import logging
from typing import List, Dict, Any
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger("agentmesh.researcher")

class ResearcherAgent:
    def __init__(self):
        self.name = "Researcher"
        self.role = "Fact and decision extractor"
        self.llm = get_llm_provider()

    def process(self, message: str) -> List[Dict[str, Any]]:
        """
        Extracts candidate facts, decisions, constraints, and observations
        from the incoming user message.
        """
        logger.info(f"Researcher analyzing message: {message[:60]}...")
        candidates = self.llm.extract_candidates(message)
        logger.info(f"Researcher identified {len(candidates)} candidate memories.")
        return candidates

researcher_agent = ResearcherAgent()
