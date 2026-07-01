"""Resolver Agent - Generates ticket resolution using LLM and context."""
import logging

logger = logging.getLogger(__name__)
from app.agents.base import BaseAgent
import os

class ResolverAgent(BaseAgent):
    """Generates a resolution response based on ticket details and context."""

    def __init__(self):
        super().__init__(
            model=os.getenv("POWER_MODEL", "anthropic/claude-sonnet-4-20250514"),
            temperature=0.2
        )

    def run(self, state: dict) -> dict:
        """Generate resolution using LLM with context."""
        description = state["description"]
        category = state.get("category", "general")
        
        # Build context from RAG results
        context_text = ""
        if state.get("context_docs"):
            context_text = "\n\nRelevant knowledge base articles:\n"
            for doc in state["context_docs"]:
                context_text += f"- {doc['text'][:300]}...\n"
        
        category_lower = category.lower() if category else "general"

        # Few-shot examples based on category
        examples = {
            "access": """Example for 'cannot log in': Try resetting your password via the 'Forgot Password' link on the login page. Make sure caps lock is off when typing your password. If the reset email doesn't arrive, check your spam folder and add us to your safe senders list.""",
            "billing": """Example for 'wrong charge on bill': Please check your invoice history in the billing portal to verify the charge. If the amount is incorrect, I can process a refund for the difference. Refunds are typically processed within 3-5 business days.""",
            "technical": """Example for 'website down 503 error': Check our status page for any ongoing incidents. If none, restart your server from the control panel and review the error logs in your server logs section.""",
        }
        example = examples.get(category_lower, "")
        example_section = f"Example format:\n{example}\n\n" if example else ""

        prompt = f"""You are a support agent for a SaaS platform. Respond in 2-3 short, direct sentences. Be specific and actionable.

Ticket category: {category}
Ticket description: {description}{context_text}

{example_section}IMPORTANT rules:
1. Use the EXACT keywords from the knowledge base articles (e.g., use "reset password" not "create new password").
2. Start each step with an action verb.
3. Maximum 3 short sentences.
4. If escalation is needed, end with: "This needs to be escalated to our team."
5. Do NOT add greetings, pleasantries, or meta-commentary. Just give the solution."""

        try:
            state["resolution"] = self.invoke_with_retry(prompt)
            
        except Exception as e:
            logger.error("Resolution generation failed", exc_info=True)
            state["resolution"] = f"Error: Unable to generate resolution - {str(e)}"
        
        return state
