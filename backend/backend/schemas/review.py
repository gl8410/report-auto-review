from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class ReviewStartRequest(BaseModel):
    document_id: str
    rule_group_ids: List[str]

class ReviewResultResponse(BaseModel):
    id: str
    task_id: str
    rule_id: str
    clause_number: str
    rule_content: str
    result_code: str
    reasoning: Optional[str]
    evidence: Optional[str]
    suggestion: Optional[str]

class ResultUpdateRequest(BaseModel):
    result_code: Optional[str] = None
    reasoning: Optional[str] = None
    evidence: Optional[str] = None
    suggestion: Optional[str] = None

class ReviewTaskResponse(BaseModel):
    id: str
    document_id: str
    document_name: str
    rule_group_id: Optional[str]
    rule_group_name: Optional[str]
    rule_group_names: Optional[str]
    status: str
    progress: int
    start_time: Optional[str]
    end_time: Optional[str]
    created_at: str
    results_count: Optional[int] = None
    stats: Optional[Dict[str, int]] = None