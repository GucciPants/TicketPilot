"""Quality Check Agent - Validates resolution with hallucination detection and citation checking."""
import logging

logger = logging.getLogger(__name__)
from app.agents.base import BaseAgent
from langchain.schema import HumanMessage
import json
import re

class QualityAgent(BaseAgent):
    """Validates resolution quality using citation check, hallucination detection, and confidence scoring."""

    def __init__(self):
        super().__init__(model=None, temperature=0.2)

    def run(self, state: dict) -> dict:
        """Evaluate resolution quality and produce a structured quality check result."""
        resolution = state.get("resolution", "")
        description = state.get("description", "")
        context_docs = state.get("context_docs", [])

        # Early exit for empty/error resolutions
        if not resolution or resolution.startswith("Error:"):
            state["quality_check"] = {
                "passed": False,
                "confidence": 0.0,
                "reason": "No valid resolution was generated",
                "citation_score": 0.0,
                "hallucination_warnings": ["Empty or error response"]
            }
            return state

        # Step 1: Citation check — does the response reference relevant content?
        citation_check = self._check_citations(resolution, context_docs)

        # Step 2: Hallucination detection — extract claims, verify against context
        hallucination_check = self._detect_hallucinations(resolution, context_docs, description)

        # Step 3: LLM quality assessment
        llm_check = self._llm_quality_check(description, resolution, context_docs)

        # Step 4: Combined confidence score
        confidence = self._calculate_confidence(citation_check, hallucination_check, llm_check)
        passed = confidence >= 0.6 and not hallucination_check["critical_issues"]
        suggest_escalation = not passed or hallucination_check["critical_issues"]

        state["quality_check"] = {
            "passed": passed,
            "confidence": round(confidence, 2),
            "reason": llm_check.get("reason", "Quality check completed"),
            "citation_score": round(citation_check["score"], 2),
            "hallucination_warnings": hallucination_check["warnings"],
            "critical_issues": hallucination_check["critical_issues"],
            "suggest_escalation": suggest_escalation
        }

        return state

    def _check_citations(self, resolution: str, context_docs: list) -> dict:
        """Check if key terms from the resolution appear in the context documents."""
        if not context_docs:
            return {"score": 0.0, "unmatched_terms": [], "matched_terms": []}

        # Extract meaningful terms from resolution (nouns, technical terms)
        terms = self._extract_key_terms(resolution)
        if not terms:
            return {"score": 0.5, "matched_terms": [], "unmatched_terms": []}

        # Build combined context text
        context_text = " ".join(doc.get("text", "") for doc in context_docs).lower()

        matched = []
        unmatched = []
        for term in terms:
            if term.lower() in context_text:
                matched.append(term)
            else:
                unmatched.append(term)

        score = len(matched) / len(terms) if terms else 0.5
        return {
            "score": score,
            "matched_terms": matched[:10],
            "unmatched_terms": unmatched[:10]
        }

    def _detect_hallucinations(self, resolution: str, context_docs: list, description: str) -> dict:
        """Detect potential hallucinations by checking unsupported claims."""
        warnings = []
        critical = False

        # Check 1: Does the response introduce specific numbers/amounts not in context?
        amounts = re.findall(r'\$\d+(?:[,.]\d+)?|\d+\s*(?:dollars|USD|eur)', resolution, re.IGNORECASE)
        if amounts and context_docs:
            context_text = " ".join(d.get("text", "") for d in context_docs)
            for amount in amounts:
                if amount not in context_text:
                    warnings.append(f"Specific amount '{amount}' not found in knowledge base")

        # Check 2: Does it reference specific tools/services not mentioned?
        tools = re.findall(r'(?i)(cPanel|Plesk|WordPress|Apache|Nginx|PHP\s*\d+\.?\d*)', resolution)
        if tools and context_docs:
            context_text = " ".join(d.get("text", "") for d in context_docs)
            for tool in tools:
                if tool.lower() not in context_text.lower() and tool.lower() not in description.lower():
                    warnings.append(f"Tool/service '{tool}' mentioned but not in context")

        # Check 3: Length heuristic — suspiciously short/empty?
        word_count = len(resolution.split())
        if word_count < 15:
            warnings.append(f"Response too short ({word_count} words)")
            critical = True
        elif word_count > 1000:
            warnings.append(f"Response unusually long ({word_count} words)")

        return {
            "warnings": warnings,
            "critical_issues": critical,
            "count": len(warnings)
        }

    def _llm_quality_check(self, description: str, resolution: str, context_docs: list) -> dict:
        """Use LLM to assess overall quality."""
        context_summary = ""
        if context_docs:
            context_summary = "\n".join(f"- {d.get('text', '')[:200]}" for d in context_docs[:2])

        prompt = f"""You are a quality assurance agent for a support system.

Ticket: {description[:300]}

Knowledge base context:
{context_summary}

Generated response: {resolution[:800]}

Respond with ONLY a JSON object:
{{
    "reason": "brief explanation of quality assessment",
    "hallucination_risk": "low" | "medium" | "high",
    "actionable": true | false,
    "professional_tone": true | false
}}

Consider:
- Does the response introduce facts NOT supported by the context? (hallucination)
- Is the response actually helpful and specific?
- Does it sound like a human support agent?"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(content)
            self.track_tokens(response)
            return result
        except Exception as e:
            logger.warning("QualityAgent LLM check failed", exc_info=True)
            return {"reason": "LLM check skipped", "hallucination_risk": "unknown", "actionable": True, "professional_tone": True}

    def _calculate_confidence(self, citation: dict, hallucination: dict, llm: dict) -> float:
        """Combine all signals into a single confidence score."""
        score = 0.5  # Start at neutral

        # Citation score contribution (0.0 - 1.0) → weight 30%
        score += (citation["score"] - 0.5) * 0.3

        # Hallucination penalty (each warning reduces score)
        score -= hallucination["count"] * 0.1
        if hallucination["critical_issues"]:
            score -= 0.3

        # LLM assessment (0.0 - 1.0 mapping) → weight 20%
        risk_map = {"low": 1.0, "medium": 0.5, "high": 0.0, "unknown": 0.5}
        llm_score = risk_map.get(llm.get("hallucination_risk", "unknown"), 0.5)
        score += (llm_score - 0.5) * 0.2

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))

    @staticmethod
    def _extract_key_terms(text: str) -> list:
        """Extract important technical terms from text."""
        # Match capitalized multi-word terms, numbers, and technical keywords
        terms = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        # Also extract quoted terms
        quoted = re.findall(r'"([^"]+)"', text)
        terms.extend(quoted)
        # Remove duplicates and short terms
        terms = list(set(t for t in terms if len(t) > 3))
        return terms[:20]  # Limit to 20 terms
