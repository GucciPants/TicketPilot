"""Test configuration and fixtures."""
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force SQLite for tests BEFORE importing app modules
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["QDRANT_URL"] = "http://localhost:6333"

from app.database import Base, get_db
from app.main import app

class MockLLMResponse:
    """Mock response for LLM calls to avoid real API calls."""
    def __init__(self, content: str):
        self.content = content
        self.usage_metadata = {"input_tokens": 10, "output_tokens": 20}


# SQLite in-memory test database
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_redis():
    """Mock Redis to prevent real connection attempts."""
    mock_client = MagicMock()
    with patch("app.api.routes.redis.from_url", return_value=mock_client):
        with patch("app.api.routes.redis_client", mock_client):
            yield mock_client


@pytest.fixture
def client(mock_redis):
    """FastAPI test client with overridden dependencies."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_ticket_data():
    return {"description": "I cannot log in to my account"}


@pytest.fixture
def agent_state():
    """Base state dictionary for agent pipeline tests."""
    return {
        "ticket_id": 1,
        "description": "I cannot log in to my account",
        "category": None,
        "priority": None,
        "context_docs": [],
        "resolution": None,
        "status": "open",
        "errors": []
    }


@pytest.fixture
def mock_llm():
    """Patches BaseAgent.llm to return controlled responses during the test."""
    patcher = patch("app.agents.base.BaseAgent.llm", new_callable=PropertyMock)
    mock_prop = patcher.start()
    mock_instance = MagicMock()
    mock_instance.invoke.return_value = MockLLMResponse("default response")
    mock_prop.return_value = mock_instance
    yield lambda text: mock_instance.__dict__.update({'invoke': MagicMock(return_value=MockLLMResponse(text))}) or mock_instance
    patcher.stop()


@pytest.fixture
def mock_qdrant():
    """Mock VectorStore.search and QdrantClient to avoid real connections."""
    with patch("app.rag.vector_store.VectorStore.search") as mock_search:
        with patch("app.rag.vector_store.QdrantClient"):
            mock_search.return_value = [
                {"doc_id": f"doc_{i}", "text": f"Sample document about login #{i}", "score": 0.9 - i * 0.1}
                for i in range(3)
            ]
            yield mock_search
