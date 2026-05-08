"""Resolver Agent - Generates ticket resolution using LLM and context."""
from app.agents.base import BaseAgent
from langchain.schema import HumanMessage
import os

class ResolverAgent(BaseAgent):
    """Generates a resolution response based on ticket details and context."""

    def __init__(self):
        super().__init__(
            model=os.getenv("POWER_MODEL", "anthropic/claude-sonnet-4-20250514"),
            temperature=0.7
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
        
        prompt = f"""You are a support agent for a hosting company. 
Ticket category: {category}
Ticket description: {description}{context_text}

Provide a helpful, professional resolution. Include specific steps the user can take.
If the issue requires human intervention, clearly state that it needs escalation.
Keep the response friendly but professional."""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            state["resolution"] = response.content.strip()
            self.track_tokens(response)
            
        except Exception as e:
            print(f"[ResolverAgent] Error: {e}")
            state["resolution"] = f"Error: Unable to generate resolution - {str(e)}"
        
        return state
