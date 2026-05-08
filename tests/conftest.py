"""Test configuration and fixtures."""
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# SQLite in-memory test database
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override the get_db dependency for testing."""
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
def client(mock_redis):  # pylint: disable=redefined-outer-name,unused-argument
    """FastAPI test client with overridden dependencies."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_ticket_data():
    """Sample ticket payload for tests."""
    return {"description": "I cannot log in to my account"}


@pytest.fixture
def long_ticket_data():
    """Long ticket description for edge case testing."""
    return {"description": "Help " * 500}
