from __future__ import annotations

from functools import lru_cache
from typing import Literal, cast

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_ENV: Literal["development", "test", "production"] = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    ENABLE_API_DOCS: bool = True
    ALLOWED_HOSTS: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "proxy", "testserver"]
    )
    CORS_ALLOWED_ORIGINS: list[HttpUrl] = Field(
        default_factory=lambda: [
            cast(HttpUrl, "http://localhost:3000"),
            cast(HttpUrl, "http://127.0.0.1:3000"),
            cast(HttpUrl, "http://localhost:8080"),
            cast(HttpUrl, "http://127.0.0.1:8080"),
        ]
    )
    MAX_REQUEST_BYTES: int = 1_048_576
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinelflow"
    LANGGRAPH_CHECKPOINT_URL: str = "postgresql://postgres:postgres@localhost:5432/sentinelflow"
    QUEUE_REDIS_URL: str = "redis://localhost:6379/0"

    OPENAI_API_KEY: str | None = None
    MODEL_PROVIDER: Literal["openai_compatible"] = "openai_compatible"
    MODEL_NAME: str = "gpt-4.1-mini"
    MODEL_DEPLOYMENT_ID: str = "sentinelflow-default"
    MODEL_BASE_URL: str | None = None
    MODEL_TIMEOUT_SECONDS: int = 30
    MODEL_MAX_RETRIES: int = 2
    MODEL_RETRY_BACKOFF_SECONDS: float = 0.5

    OTEL_SERVICE_NAME: str = "sentinelflow-agent-engine"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    OTEL_EXPORTER_OTLP_HEADERS: str | None = None

    AUDIT_ARTIFACT_KEY_ID: str = "v1"
    AUDIT_ARTIFACT_ENCRYPTION_KEY: str | None = None

    AUTH_ISSUER: str = "sentinelflow-dev"
    AUTH_AUDIENCE: str = "sentinelflow-api"
    AUTH_JWT_SECRET: str | None = None
    AUTH_ALGORITHM: str = "HS256"
    AUTH_ALLOWED_ALGORITHMS: list[str] = Field(
        default_factory=lambda: ["RS256", "ES256", "PS256", "HS256"]
    )
    AUTH_OIDC_ISSUER: str | None = None
    AUTH_OIDC_DISCOVERY_URL: str | None = None
    AUTH_JWKS_URL: str | None = None
    AUTH_RESOURCE_CLIENT_ID: str | None = None
    AUTH_ROLE_MAP: dict[str, str] = Field(default_factory=dict)
    AUTH_ALLOW_DEV_TOKENS: bool = True

    INVESTIGATION_MAX_ITERATIONS: int = 5
    INVESTIGATION_MAX_TOOL_CALLS: int = 8
    INVESTIGATION_MAX_ANALYZER_CALLS: int = 4
    INVESTIGATION_MAX_TOKENS: int = 24000
    INVESTIGATION_MAX_SECONDS: int = 45

    DEFAULT_REVIEW_THRESHOLD: float = 0.8

    @model_validator(mode="after")
    def validate_runtime_requirements(self) -> Settings:
        if self.APP_ENV == "production":
            missing: list[str] = []
            if not self.OPENAI_API_KEY:
                missing.append("OPENAI_API_KEY")
            has_shared_secret = bool(self.AUTH_JWT_SECRET)
            has_oidc_config = bool(
                self.AUTH_OIDC_ISSUER
                or self.AUTH_OIDC_DISCOVERY_URL
                or self.AUTH_JWKS_URL
            )
            if not has_shared_secret and not has_oidc_config:
                missing.append(
                    "AUTH_JWT_SECRET or AUTH_OIDC_ISSUER/AUTH_OIDC_DISCOVERY_URL/AUTH_JWKS_URL"
                )
            if not self.OTEL_EXPORTER_OTLP_ENDPOINT:
                missing.append("OTEL_EXPORTER_OTLP_ENDPOINT")
            if not self.LANGGRAPH_CHECKPOINT_URL:
                missing.append("LANGGRAPH_CHECKPOINT_URL")
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing)}")
            if self.AUTH_ALLOW_DEV_TOKENS:
                raise ValueError("AUTH_ALLOW_DEV_TOKENS must be false in production.")
        if self.MODEL_PROVIDER != "openai_compatible":
            raise ValueError("Unsupported MODEL_PROVIDER. Expected 'openai_compatible'.")
        if self.MODEL_MAX_RETRIES < 0:
            raise ValueError("MODEL_MAX_RETRIES must be >= 0.")
        if self.MODEL_TIMEOUT_SECONDS <= 0:
            raise ValueError("MODEL_TIMEOUT_SECONDS must be > 0.")
        if self.MODEL_RETRY_BACKOFF_SECONDS < 0:
            raise ValueError("MODEL_RETRY_BACKOFF_SECONDS must be >= 0.")
        if not self.AUTH_ALLOWED_ALGORITHMS:
            raise ValueError("AUTH_ALLOWED_ALGORITHMS must include at least one value.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
