"""Application configuration from environment variables."""

from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.config.database_url import build_database_url, project_ref_from_supabase_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_embed_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBED_MODEL"
    )
    openai_chat_model: str = Field(default="gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    max_llm_concurrent: int = Field(default=5, alias="MAX_LLM_CONCURRENT")

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")

    database_url: str = Field(default="", alias="DATABASE_URL")

    # Optional: build DATABASE_URL when unset (see .env.example)
    supabase_project_ref: str = Field(default="", alias="SUPABASE_PROJECT_REF")
    supabase_db_password: str = Field(default="", alias="SUPABASE_DB_PASSWORD")
    supabase_region: str = Field(default="us-east-1", alias="SUPABASE_REGION")
    database_connection: str = Field(
        default="pooler-session", alias="DATABASE_CONNECTION"
    )

    cors_origins: str = Field(
        default="http://localhost:3000", alias="CORS_ORIGINS"
    )

    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket_hts_releases: str = Field(default="", alias="S3_BUCKET_HTS_RELEASES")

    @model_validator(mode="after")
    def _fill_project_ref(self) -> "Settings":
        if not self.supabase_project_ref and self.supabase_url:
            self.supabase_project_ref = project_ref_from_supabase_url(self.supabase_url)
        return self

    @property
    def resolved_database_url(self) -> str:
        explicit = self.database_url.strip()
        if explicit:
            return explicit
        if self.supabase_db_password and self.supabase_project_ref:
            return build_database_url(
                project_ref=self.supabase_project_ref,
                password=self.supabase_db_password,
                region=self.supabase_region,
                mode=self.database_connection,
            )
        return ""

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def require_database(self) -> None:
        if not self.resolved_database_url:
            raise RuntimeError(
                "DATABASE_URL is not set (or set SUPABASE_DB_PASSWORD + DATABASE_CONNECTION)"
            )

    def require_openai(self) -> None:
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")


@lru_cache
def get_settings() -> Settings:
    return Settings()
