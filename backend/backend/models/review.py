import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from enum import Enum

class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class ResultCode(str, Enum):
    """审查结果枚举"""
    PASS = "PASS"
    REJECT = "REJECT"
    MANUAL_CHECK = "MANUAL_CHECK"

class ReviewTask(SQLModel, table=True):
    """审查任务表"""
    __tablename__ = "review_tasks"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    rule_group_id: Optional[str] = Field(default=None, foreign_key="rule_groups.id", index=True)
    rule_group_names: Optional[str] = None # Comma separated names of selected groups
    status: str = TaskStatus.PENDING.value
    progress: int = 0  # 0-100
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ReviewResultItem(SQLModel, table=True):
    """审查结果明细表"""
    __tablename__ = "review_result_items"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: str = Field(foreign_key="review_tasks.id", index=True)
    rule_id: str = Field(foreign_key="rules.id", index=True)
    result_code: str = ResultCode.MANUAL_CHECK.value
    reasoning: Optional[str] = None  # LLM生成的判断理由
    evidence: Optional[str] = None  # 引用原文片段
    suggestion: Optional[str] = None  # 修改建议
    created_at: datetime = Field(default_factory=datetime.utcnow)