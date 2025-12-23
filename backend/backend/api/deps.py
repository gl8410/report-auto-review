from typing import Generator
from sqlmodel import Session
from backend.core.db import engine

def get_session() -> Generator[Session, None, None]:
    """Get database session."""
    with Session(engine) as session:
        yield session