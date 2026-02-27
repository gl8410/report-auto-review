import os
from typing import Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = Field(
        default="Report Inspection System",
        validation_alias=AliasChoices("PROJECT_NAME", "APP_NAME")
    )
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    # Server Ports
    BACKEND_PORT: int = 6802
    FRONTEND_PORT: int = 7802

    # Database
    DATABASE_URL: str = "postgresql://ads_user:ads_password@localhost:5433/ads_db"
    DEBUG: bool = False

    # LLM
    API_KEY: Optional[str] = None
    LLM_URL: str = "https://api.siliconflow.cn/v1/chat/completions"
    LLM_MODEL: str = "deepseek-ai/DeepSeek-V3.2"

    # Rerank
    RERANK_URL: str = "https://api.siliconflow.cn/v1/rerank"
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # Embedding
    EMBEDDING_URL: str = "https://api.siliconflow.cn/v1/embeddings"
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-8B"
    EMBEDDING_DIMENSION: int = 1024

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001

    # MinerU API
    MINERU_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("MINERU_KEY", "Mineru_KEY")
    )

    # Supabase
    SUPABASE_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_URL", "VITE_SUPABASE_URL")
    )
    SUPABASE_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_KEY", "VITE_SUPABASE_ANON_KEY")
    )
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "VITE_SUPABASE_SERVICE_ROLE_KEY")
    )

    # Credit System Configuration
    APP_ID: str = "report_review_lite"
    FEATURE_REVIEW_TASK: str = "review_task"
    FEATURE_REVIEW_REFUND: str = "review_task_refund"
    ENABLE_CREDIT_SYSTEM: bool = True

    # Storage
    UPLOADS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")

    model_config = SettingsConfigDict(
        env_file=(
            os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env'),
            os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        ),
        env_ignore_empty=True,
        extra="ignore",
        populate_by_name=True,
    )

settings = Settings()