import uuid
from typing import Optional
from sqlmodel import SQLModel, Field

class Profile(SQLModel, table=True):
    """用户配置文件 (对应 Supabase public.profiles)"""
    __tablename__ = "profiles"

    id: uuid.UUID = Field(primary_key=True)
    email: Optional[str] = None
    credits: int = Field(default=10)