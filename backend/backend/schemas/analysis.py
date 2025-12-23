from typing import Optional, List
from pydantic import BaseModel, Field

class ParsedRule(BaseModel):
    """LLM解析出的单条规则"""
    clause_number: str = Field(..., description="条文号，如 3.1.2")
    content: str = Field(..., description="规则具体内容")
    review_type: str = Field(
        default="内容完整性",
        description="审查类型：内容完整性/计算结果准确性/禁止条款/前后逻辑一致性/措施遵从性/计算正确性"
    )
    risk_level: str = Field(
        default="中风险",
        description="风险等级：低风险/中风险/高风险"
    )

class ParsedRulesResponse(BaseModel):
    """LLM解析规则的响应"""
    standard_name: str = Field(..., description="标准/导则名称")
    rules: List[ParsedRule] = Field(default_factory=list, description="解析出的规则列表")

class OpinionUpdate(BaseModel):
    opinion: Optional[str] = None
    risk_level: Optional[str] = None
    review_type: Optional[str] = None
class ConvertToRuleRequest(BaseModel):
    rule_group_id: str