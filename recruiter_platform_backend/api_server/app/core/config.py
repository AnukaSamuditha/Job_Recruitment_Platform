from functools import lru_cache

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All service URLs, hosts, and ports are loaded from environment (see `.env.example`).
    Defaults below apply only when a variable is unset (local development).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_url: str = Field(
        default="postgresql+asyncpg://recruit:recruit@127.0.0.1:5433/recruitment",
        description="Async SQLAlchemy URL (see DB_URL in .env.example).",
    )
    port: int = Field(default=8000, description="HTTP (Uvicorn) port.")
    grpc_port: int = Field(default=50051, description="RecruitmentData gRPC listen port.")
    grpc_bind_host: str = Field(
        default="0.0.0.0",
        description="Host interface for the gRPC server (e.g. 0.0.0.0 or 127.0.0.1).",
    )

    cors_allow_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated browser origins allowed by CORS.",
    )
    cors_allow_origin_regex: str | None = Field(
        default=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
        description=(
            "Optional regex for allowed origins (e.g. any port on localhost). "
            "Set to empty string in .env to disable and rely on CORS_ALLOW_ORIGINS only."
        ),
    )

    minio_endpoint: str = Field(
        default="http://127.0.0.1:9000",
        description="MinIO / S3 endpoint URL.",
    )
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "cvs"
    minio_use_ssl: bool = False

    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        description="Ollama HTTP API base URL.",
    )
    ollama_chat_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"
    embedding_dim: int = 768

    # LlamaCloud — required for CV PDF parsing (https://cloud.llamaindex.ai)
    llama_cloud_api_key: str = ""
    llama_cloud_base_url: str = Field(
        default="https://api.cloud.llamaindex.ai",
        description="LlamaCloud parsing API base URL (no trailing slash).",
    )
    llama_cloud_organization_id: str | None = Field(
        default=None,
        description="Optional LlamaCloud organization_id query param for parsing.",
    )
    llama_cloud_project_id: str | None = Field(
        default=None,
        description="Optional LlamaCloud project_id query param for parsing.",
    )
    llama_cloud_parse_timeout_seconds: float = Field(
        default=900.0,
        ge=30.0,
        description="Max seconds to wait for a parse job (upload + poll + result).",
    )
    llama_cloud_parse_poll_interval: float = Field(
        default=2.0,
        ge=0.5,
        description="Initial seconds between job status polls.",
    )
    llama_cloud_parse_max_poll_interval: float = Field(
        default=5.0,
        ge=1.0,
        description="Cap for backoff between job status polls (seconds).",
    )

    cv_preview_max_pages: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Max PDF pages rasterized for the candidate CV preview API.",
    )
    cv_preview_max_width_px: int = Field(
        default=1100,
        ge=480,
        le=2400,
        description="Max raster width in CSS pixels for CV preview images.",
    )

    mcp_cv_tools_url: str = Field(
        default="http://127.0.0.1:8765/mcp",
        description=(
            "Streamable-HTTP MCP URL for CV extraction (FastMCP: ``--transport streamable-http``). "
            "The cv_parser agent always calls MCP tool ``parse_candidate_cv_structured``; "
            "LlamaCloud / LlamaIndex parsing runs inside that MCP tool."
        ),
    )
    mcp_cv_auto_start: bool = Field(
        default=True,
        description=(
            "When true and MCP_CV_TOOLS_URL uses loopback, start ``mcp_server`` FastMCP on that port "
            "after gRPC starts (requires ``uv`` on PATH and mcp_server/.env with LLAMA_CLOUD_API_KEY). "
            "Set false if you start MCP manually."
        ),
    )

    trace_log_to_files: bool = Field(
        default=True,
        description="When true, append agent trace JSON lines to files under TRACE_LOG_DIR.",
    )
    trace_log_dir: str = Field(
        default="logs",
        description="Directory for agent trace logs (relative to api_server root unless absolute).",
    )

    @field_validator("cors_allow_origin_regex", mode="before")
    @classmethod
    def _empty_cors_regex_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @field_validator("llama_cloud_organization_id", "llama_cloud_project_id", mode="before")
    @classmethod
    def _empty_llama_ids_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v

    @field_validator("mcp_cv_tools_url", mode="before")
    @classmethod
    def _mcp_cv_tools_url_default(cls, v: object) -> object:
        if v == "" or v is None:
            return "http://127.0.0.1:8765/mcp"
        return v

    @computed_field
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
