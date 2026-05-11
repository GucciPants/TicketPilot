"""Context Agent - Retrieves relevant documents from the knowledge base."""
from app.agents.base import BaseAgent
from app.rag.vector_store import VectorStore
import logging

logger = logging.getLogger(__name__)

class ContextAgent(BaseAgent):
    """Retrieves relevant documents from the RAG knowledge base."""

    def __init__(self):
        super().__init__()
        self.vector_store = VectorStore()

    def run(self, state: dict) -> dict:
        """Search for relevant documents and add them to state."""
        description = state["description"]
        
        try:
            results = self.vector_store.search(description, limit=3)
            state["context_docs"] = [
                {
                    "doc_id": r["doc_id"],
                    "text": r["text"],
                    "score": r["score"]
                }
                for r in results
            ]
            logger.info(f"RAG: {len(state['context_docs'])} documents retrieved")
            
        except Exception as e:
            logger.error("RAG search failed", exc_info=True)
            state["context_docs"] = []
        
        return state
