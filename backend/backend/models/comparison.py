import uuid
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field
from enum import Enum

class ComparisonDocumentStatus(str, Enum):
    """对比文件状态枚举"""
    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"

class ComparisonDocument(SQLModel, table=True):
    """对比文件表 (Module 6)"""
    __tablename__ = "comparison_documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    filename: str
    storage_path: Optional[str] = None
    status: str = ComparisonDocumentStatus.UPLOADED.value
    description: Optional[str] = None
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
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
