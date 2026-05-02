"""MCP process configuration (gRPC target + LlamaCloud for CV parse tool)."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_grpc_host: str = Field(default="127.0.0.1", description="API gRPC host.")
    api_grpc_port: int = Field(default=50051, description="API gRPC port (same as api_server GRPC_PORT).")
    api_grpc_target: str | None = Field(
        default=None,
        description="Optional full host:port; if unset, built from api_grpc_host:api_grpc_port.",
    )

    llama_cloud_api_key: str = ""
    llama_cloud_base_url: str = Field(
        default="https://api.cloud.llamaindex.ai",
        description="LlamaCloud parsing API base URL (no trailing slash).",
    )
    llama_cloud_organization_id: str | None = None
    llama_cloud_project_id: str | None = None
    llama_cloud_parse_timeout_seconds: float = Field(default=900.0, ge=30.0)
    llama_cloud_parse_poll_interval: float = Field(default=2.0, ge=0.5)
    llama_cloud_parse_max_poll_interval: float = Field(default=5.0, ge=1.0)

    @model_validator(mode="after")
    def compose_api_grpc_target(self) -> Settings:
        raw = (self.api_grpc_target or "").strip()
        if raw:
            self.api_grpc_target = raw
        else:
            self.api_grpc_target = f"{self.api_grpc_host}:{self.api_grpc_port}"
        return self

    @field_validator("llama_cloud_organization_id", "llama_cloud_project_id", mode="before")
    @classmethod
    def _empty_llama_ids_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v


settings = Settings()
