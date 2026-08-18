"""Tests for RAG document processing and knowledge base ingestion (F3)."""
from unittest.mock import patch

from app.rag.document_processor import DocumentProcessor

FAKE_EMBEDDING = [0.1] * 384


class TestGoldStandardIngestion:
    def test_ingests_all_gold_resolutions(self, mock_qdrant):
        with patch("app.rag.vector_store.get_embedding", return_value=FAKE_EMBEDDING):
            processor = DocumentProcessor()
            count = processor.ingest_gold_standard_knowledge_base()
        assert count == 25  # evaluation/gold_dataset.jsonl contains 25 entries

    def test_each_gold_doc_is_upserted(self, mock_qdrant):
        with patch("app.rag.vector_store.get_embedding", return_value=FAKE_EMBEDDING):
            processor = DocumentProcessor()
            processor.ingest_gold_standard_knowledge_base()
        assert len(processor.vector_store.client.upsert.call_args_list) == 25

    def test_missing_dataset_returns_zero(self, mock_qdrant):
        with patch("app.rag.vector_store.get_embedding", return_value=FAKE_EMBEDDING):
            with patch("app.rag.document_processor.os.path.exists", return_value=False):
                processor = DocumentProcessor()
                count = processor.ingest_gold_standard_knowledge_base()
        assert count == 0