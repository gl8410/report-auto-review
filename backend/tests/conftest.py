"""
Pytest configuration and fixtures for ADS System tests.
Uses an in-memory SQLite database for isolated testing.
"""
import pytest
import uuid
from typing import Generator
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

import sys
import os
# Add backend directory to sys.path so we can import backend package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.api.deps import get_session, get_current_user
from backend.models import * # Import all models to register with SQLModel
from backend.models.user import Profile

# Create in-memory SQLite engine for testing
TEST_DATABASE_URL = "sqlite://"

@pytest.fixture(name="engine")
def engine_fixture():
    """Create a test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(engine) -> Generator[TestClient, None, None]:
    """Create a test client with overridden database dependency."""
    
    def get_session_override():
        with Session(engine) as session:
            yield session
            
    def get_current_user_override() -> Profile:
        return Profile(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            subscription_credits=1000,
            topup_credits=0
        )
    
    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_current_user] = get_current_user_override
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()
