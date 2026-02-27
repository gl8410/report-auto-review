from uuid import uuid4
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field

class AnalysisStatus(str, Enum):
    """历史报告智能分析任务状态"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class OpinionStatus(str, Enum):
    """推断意见状态"""
    PENDING = "PENDING"
    ADDED = "ADDED"
    IGNORED = "IGNORED"
    DELETED = "DELETED"

class HistoryAnalysisTask(SQLModel, table=True):
    """历史报告智能分析任务"""
    __tablename__ = "history_analysis_tasks"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    status: str = AnalysisStatus.PENDING.value
    draft_filenames: str = Field(default="[]")  # JSON list of filenames
    approved_filenames: str = Field(default="[]")  # JSON list of filenames
    draft_file_paths: str = Field(default="[]")  # JSON list of storage paths
    approved_file_paths: str = Field(default="[]")  # JSON list of storage paths
    created_at: datetime = Field(default_factory=datetime.utcnow)

class InferredOpinion(SQLModel, table=True):
    """AI推断的审查意见"""
    __tablename__ = "inferred_opinions"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    task_id: str = Field(foreign_key="history_analysis_tasks.id", index=True)
    opinion: str  # 推断出的意见内容
    evidence: Optional[str] = None  # 差异证据/上下文
    clause: Optional[str] = None  # 关联条文号(如有)
    risk_level: str = "中风险"
    review_type: Optional[str] = None  # 审查类型
    draft_file_location: Optional[str] = None  # JSON: {filename, page, bbox}
    approved_file_location: Optional[str] = None  # JSON: {filename, page, bbox}
    status: str = OpinionStatus.PENDING.value
    created_at: datetime = Field(default_factory=datetime.utcnow)