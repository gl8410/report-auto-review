"""
SQLModel database models for ADS system.
Defines RuleGroup, Rule, Document, ReviewTask, and ReviewResultItem tables.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


# ============== Enums ==============

class ReviewType(str, Enum):
    """审查类型枚举"""
    CONTENT_COMPLETENESS = "内容完整性"
    CALCULATION_ACCURACY = "计算结果准确性"
    PROHIBITION_CLAUSE = "禁止条款"
    LOGIC_CONSISTENCY = "前后逻辑一致性"
    MEASURE_COMPLIANCE = "措施遵从性"
    CALCULATION_CORRECTNESS = "计算正确性"


class Importance(str, Enum):
    """重要性枚举"""
    LOW = "一般"
    MEDIUM = "中等"
    HIGH = "重要"


class DocumentStatus(str, Enum):
    """文档状态枚举"""
    UPLOADED = "UPLOADED"
    PARSING = "PARSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ResultCode(str, Enum):
    """审查结果枚举"""
    PASS = "PASS"
    REJECT = "REJECT"
    MANUAL_CHECK = "MANUAL_CHECK"


# ============== Database Models ==============

class RuleGroup(SQLModel, table=True):
    """规则组表"""
    __tablename__ = "rule_groups"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    rules: List["Rule"] = Relationship(back_populates="group")


class Rule(SQLModel, table=True):
    """原子规则表"""
    __tablename__ = "rules"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    group_id: str = Field(foreign_key="rule_groups.id", index=True)
    standard_name: Optional[str] = None  # 来源标准名称
    clause_number: str  # 条文号 (如 3.1.2)
    content: str  # 规则具体内容
    review_type: Optional[str] = None  # 审查类型 (内容完整性/计算结果准确性/禁止条款/前后逻辑一致性/措施遵从性/计算正确性)
    importance: str = "中等"  # 重要性: 一般/中等/重要
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    group: Optional[RuleGroup] = Relationship(back_populates="rules")


class Document(SQLModel, table=True):
    """文档表"""
    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    filename: str
    storage_path: Optional[str] = None
    status: str = DocumentStatus.UPLOADED.value
    meta_info: Optional[str] = None  # JSON string
    upload_time: datetime = Field(default_factory=datetime.utcnow)


class ReviewTask(SQLModel, table=True):
    """审查任务表"""
    __tablename__ = "review_tasks"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    document_id: str = Field(foreign_key="documents.id", index=True)
    rule_group_id: str = Field(foreign_key="rule_groups.id", index=True)
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