import uuid
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

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

class RuleGroup(SQLModel, table=True):
    """规则组表"""
    __tablename__ = "rule_groups"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    parent_id: Optional[str] = Field(default=None, foreign_key="rule_groups.id", index=True)
    owner_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    rules: List["Rule"] = Relationship(back_populates="group")
    parent: Optional["RuleGroup"] = Relationship(back_populates="children", sa_relationship_kwargs={"remote_side": "RuleGroup.id"})
    children: List["RuleGroup"] = Relationship(back_populates="parent")

class Rule(SQLModel, table=True):
    """原子规则表"""
    __tablename__ = "rules"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    group_id: str = Field(foreign_key="rule_groups.id", index=True)
    standard_name: Optional[str] = None  # 来源标准名称
    clause_number: str  # 条文号 (如 3.1.2)
    content: str  # 规则具体内容
    review_type: Optional[str] = None  # 审查类型
    risk_level: str = "中风险"  # 风险等级: 低风险/中风险/高风险
    owner_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    group: Optional[RuleGroup] = Relationship(back_populates="rules")