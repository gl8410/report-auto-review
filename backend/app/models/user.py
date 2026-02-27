import uuid
from typing import Optional
from sqlmodel import SQLModel, Field
from pydantic import computed_field

class Profile(SQLModel, table=True):
    """用户配置文件 (对应 Supabase public.profiles)"""
    __tablename__ = "profiles"

    id: uuid.UUID = Field(primary_key=True)
    email: Optional[str] = None
    subscription_credits: int = Field(default=0)
    topup_credits: int = Field(default=0)

    @computed_field
    def credits(self) -> int:
        return self.subscription_credits + self.topup_credits