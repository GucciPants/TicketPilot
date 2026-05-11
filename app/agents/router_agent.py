"""Router Agent - Classifies tickets into categories."""
from app.agents.base import BaseAgent
from langchain.schema import HumanMessage
import json
import logging

logger = logging.getLogger(__name__)

class RouterAgent(BaseAgent):
    """Classifies tickets to determine category, priority, and required context."""

    def __init__(self):
        super().__init__(model=None, temperature=0.2)  # Low temp for consistent classification

    def run(self, state: dict) -> dict:
        """Classify the ticket and update state with category and priority."""
        prompt = f"""You are a ticket routing agent. Analyze the following support ticket and classify it.

Ticket: {state['description']}

Respond with ONLY a JSON object (no markdown, no code blocks):
{{
    "category": "access" | "billing" | "technical" | "account" | "general",
    "priority": "low" | "medium" | "high",
    "requires_rag": true | false,
    "reason": "brief explanation"
}}

Examples:
- "I can't log in" → access, high
- "My bill is wrong" → billing, medium
- "The website is slow" → technical, medium
- "How do I update my email?" → account, low"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            # Clean response
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            
            result = json.loads(content)
            state["category"] = result.get("category", "general")
            state["priority"] = result.get("priority", "medium")
            state["requires_rag"] = result.get("requires_rag", True)
            
            self.track_tokens(response)
            
        except Exception as e:
            logger.warning("Route classification failed: %s", str(e))
            state["category"] = "general"
            state["priority"] = "medium"
            state["requires_rag"] = True
        
        return state
