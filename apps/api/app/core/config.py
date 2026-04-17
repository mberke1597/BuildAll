from functools import lru_cache
from pydantic import BaseModel
import os


class Settings(BaseModel):
    app_name: str = "BuildAll API"
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    algorithm: str = "HS256"

    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/buildall"
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "buildall")
    minio_secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    openai_chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "25"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()
