"""Context Agent - Retrieves relevant documents from the knowledge base."""
from app.rag.vector_store import VectorStore
import logging

logger = logging.getLogger(__name__)


class ContextAgent:
    """Retrieves relevant documents from the RAG knowledge base."""

    def __init__(self, vector_store: VectorStore = None):
        self.vector_store = vector_store or VectorStore()

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
