from typing import Optional
from backend.models.comparison import ComparisonResult

class ComparisonResultRead(ComparisonResult):
    document_name: Optional[str] = None