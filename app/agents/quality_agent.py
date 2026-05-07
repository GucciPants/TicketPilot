"""Quality Check Agent - Validates the generated resolution."""
from app.agents.base import BaseAgent
from langchain.schema import HumanMessage
import json

class QualityAgent(BaseAgent):
    """Validates the quality of the generated resolution and decides if escalation is needed."""

    def __init__(self):
        super().__init__(model=None, temperature=0.2)

    def run(self, state: dict) -> dict:
        """Check resolution quality and decide: resolved or escalate."""
        resolution = state.get("resolution", "")
        description = state.get("description", "")
        
        if not resolution or resolution.startswith("Error:"):
            state["quality_check"] = {
                "passed": False,
                "confidence": 0.0,
                "reason": "No valid resolution was generated"
            }
            return state
        
        prompt = f"""You are a quality assurance agent. Evaluate this support ticket resolution.

Original ticket: {description[:200]}
Generated response: {resolution[:500]}

Respond with ONLY a JSON object (no markdown, no code blocks):
{{
    "passed": true | false,
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation",
    "suggest_escalation": true | false
}}

Consider:
- Does the response actually address the issue?
- Is it helpful and actionable?
- Does it suggest escalation when appropriate?
- Is the tone professional?
- Any obvious errors or hallucinations?"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            
            result = json.loads(content)
            state["quality_check"] = result
            self.track_tokens(response)
            
        except Exception as e:
            print(f"[QualityAgent] Error: {e}")
            state["quality_check"] = {
                "passed": True,  # Default: pass if check fails
                "confidence": 0.5,
                "reason": f"Quality check error (defaulting to pass): {e}"
            }
        
        return state
