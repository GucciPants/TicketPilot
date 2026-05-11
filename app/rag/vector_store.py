from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import os
import hashlib
import logging
from app.rag.embedding import get_embedding

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        self.qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        self.collection_name = "ticketpilot_knowledge"
        self.client = QdrantClient(url=self.qdrant_url)
        self._init_collection()
    
    def _init_collection(self):
        """Initialize Qdrant collection if it doesn't exist."""
        try:
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
                logger.info("Created collection: %s", self.collection_name)
        except Exception as e:
            logger.error("Failed to initialize collection: %s", str(e))
    
    def add_document(self, doc_id: str, text: str, metadata: dict = None):
        """Add a document to the vector store."""
        try:
            embedding = get_embedding(text)
            point = PointStruct(
                id=abs(hashlib.md5(doc_id.encode()) % (2**31)),
                vector=embedding,
                payload={
                    "doc_id": doc_id,
                    "text": text[:1000],  # Store first 1000 chars in payload
                    **(metadata or {})
                }
            )
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            return True
        except Exception as e:
            logger.error("Failed to add document %s: %s", doc_id, str(e))
            return False
    
    def search(self, query: str, limit: int = 3):
        """Search for relevant documents."""
        try:
            query_embedding = get_embedding(query)
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit
            )
            return [
                {
                    "doc_id": r.payload.get("doc_id"),
                    "text": r.payload.get("text"),
                    "score": r.score
                }
                for r in results
            ]
        except Exception as e:
            logger.error("Vector search failed: %s", str(e))
            return []
