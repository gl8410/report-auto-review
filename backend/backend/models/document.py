import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from enum import Enum

class DocumentStatus(str, Enum):
    """文档状态枚举"""
    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    MANUAL_CHECK = "MANUAL_CHECK"

class Document(SQLModel, table=True):
    """文档表"""
    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    filename: str
    storage_path: Optional[str] = None
    status: str = DocumentStatus.UPLOADED.value
    meta_info: Optional[str] = None  # JSON string
    upload_time: datetime = Field(default_factory=datetime.utcnow)