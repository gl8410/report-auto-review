import uuid
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field
from enum import Enum

class ComparisonDocumentStatus(str, Enum):
    """对比文件状态枚举"""
    UPLOADING = "UPLOADING"
    PARSING = "PARSING"
    EMBEDDING = "EMBEDDING"
    DONE = "DONE"
    FAILED = "FAILED"

class ComparisonDocument(SQLModel, table=True):
    """对比文件表 (Module 6)"""
    __tablename__ = "comparison_documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    filename: str
    storage_path: Optional[str] = None
    markdown_path: Optional[str] = None  # Path to extracted .md file
    mineru_batch_id: Optional[str] = None  # MinerU batch ID for tracking
    mineru_zip_url: Optional[str] = None  # MinerU result ZIP URL
    status: str = ComparisonDocumentStatus.UPLOADING.value
    error_message: Optional[str] = None  # Error message if parsing failed
    description: Optional[str] = None
    owner_id: Optional[str] = Field(default=None, index=True)
    upload_time: datetime = Field(default_factory=datetime.utcnow)

class ComparisonResult(SQLModel, table=True):
    """对比结果表"""
    __tablename__ = "comparison_results"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: str = Field(foreign_key="review_tasks.id", index=True)
    comparison_document_id: str = Field(foreign_key="comparison_documents.id", index=True)
    
    # Analysis results
    conflict_score: float = 0.0  # 0-1 score of conflict likelihood
    summary: Optional[str] = None  # Overall summary of comparison
    details: Optional[str] = None  # JSON string containing specific conflict points
    owner_id: Optional[str] = Field(default=None, index=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
