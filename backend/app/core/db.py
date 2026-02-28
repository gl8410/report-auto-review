from sqlmodel import SQLModel, create_engine, Session
from typing import Generator
from app.core.config import settings

# Create engine with connection pool settings
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,  # Never echo SQL; controlled via logging level instead
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

def init_db() -> None:
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    with Session(engine) as session:
        yield session