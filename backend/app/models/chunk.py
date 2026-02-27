import uuid
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

class DocumentChunk(SQLModel, table=True):
    """Document chunk table"""
    __tablename__ = "document_chunks"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    document_id: str = Field(index=True)
    chunk_index: int
    content: str
    word_count: int
    sentence_count: int
