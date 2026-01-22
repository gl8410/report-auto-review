import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ADS System API"
    BACKEND_CORS_ORIGINS: list[str] = ["*"]
    
    # Database
    DATABASE_URL: str = "postgresql://ads_user:ads_password@localhost:5432/ads_db"
    DEBUG: bool = False
    
    # LLM
    API_KEY: Optional[str] = None
    LLM_URL: str = "https://api.siliconflow.cn/v1/chat/completions"
    LLM_MODEL: str = "deepseek-ai/DeepSeek-V3.2"
    
    # Embedding
    EMBEDDING_URL: str = "https://api.siliconflow.cn/v1/embeddings"
    EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-8B"
    
    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001

    # MinerU API
    MINERU_KEY: Optional[str] = None
    # Supabase
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
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
        extra="ignore"
    )

settings = Settings()