from typing import Optional
from app.models.comparison import ComparisonResult

class ComparisonResultRead(ComparisonResult):
    document_name: Optional[str] = None