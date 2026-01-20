import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from enum import Enum

class DocumentStatus(str, Enum):
    """文档状态枚举"""
    UPLOADING = "UPLOADING"
    PARSING = "PARSING"
    EMBEDDING = "EMBEDDING"
    DONE = "DONE"
    FAILED = "FAILED"

class Document(SQLModel, table=True):
    """文档表"""
    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    filename: str
    storage_path: Optional[str] = None
    markdown_path: Optional[str] = None  # Path to extracted .md file
    mineru_batch_id: Optional[str] = None  # MinerU batch ID for tracking
    mineru_zip_url: Optional[str] = None  # MinerU result ZIP URL
    status: str = DocumentStatus.UPLOADING.value
    error_message: Optional[str] = None  # Error message if parsing failed
    meta_info: Optional[str] = None  # JSON string
    owner_id: Optional[str] = Field(default=None, index=True)
    upload_time: datetime = Field(default_factory=datetime.utcnow)