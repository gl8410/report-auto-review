from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    upload_time: datetime
    meta_info: Optional[str] = None