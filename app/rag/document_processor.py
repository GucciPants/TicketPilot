import os
from app.rag.vector_store import VectorStore
from app.rag.embedding import get_embedding

class DocumentProcessor:
    def __init__(self):
        self.vector_store = VectorStore()
        self.chunk_size = 1000
        self.chunk_overlap = 200
    
    def process_text(self, text: str, doc_id: str, metadata: dict = None):
        """Process text by chunking and adding to vector store."""
        chunks = self._chunk_text(text)
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            chunk_metadata = {
                "doc_id": doc_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
                **(metadata or {})
            }
            self.vector_store.add_document(chunk_id, chunk, chunk_metadata)
        
        return len(chunks)
    
    def _chunk_text(self, text: str):
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap
        
        return chunks
    
    def ingest_file(self, file_path: str):
        """Ingest a file (txt, md, etc.)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        doc_id = os.path.basename(file_path)
        return self.process_text(text, doc_id, {"source": file_path})
    
    def ingest_sample_knowledge_base(self):
        """Ingest sample support knowledge base documents."""
        sample_docs = [
            {
                "id": "kb_login_issue",
                "text": "Login issues: If a user cannot log in, first check if they have the correct password. Reset password if needed. Check if account is locked. Verify email verification status.",
                "metadata": {"category": "authentication", "type": "troubleshooting"}
            },
            {
                "id": "kb_billing",
                "text": "Billing inquiries: For billing questions, verify subscription status. Check payment history. If payment failed, suggest updating payment method. Provide refund policy details when requested.",
                "metadata": {"category": "billing", "type": "policy"}
            },
            {
                "id": "kb_performance",
                "text": "Performance issues: Slow loading times may be due to high traffic, server maintenance, or local network issues. Clear cache and cookies. Try different browser. Check service status page.",
                "metadata": {"category": "technical", "type": "troubleshooting"}
            }
        ]
        
        for doc in sample_docs:
            self.process_text(doc["text"], doc["id"], doc["metadata"])
        
        return len(sample_docs)
