"""Application configuration loaded from environment variables via pydantic-settings."""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(str, Enum):
    """Supported ServiceNow authentication modes."""

    BASIC = "basic"
    OAUTH = "oauth"


class MCPTransport(str, Enum):
    """Supported MCP server transports."""

    STDIO = "stdio"
    SSE = "sse"


class Settings(BaseSettings):
    """All application settings sourced from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # ── ServiceNow instance ───────────────────────────────────────────────────
    servicenow_instance_url: HttpUrl = Field(
        ...,
        description="Base URL of the ServiceNow instance, e.g. https://dev12345.service-now.com",
    )
    servicenow_auth_mode: AuthMode = Field(
        default=AuthMode.BASIC,
        description="Authentication mode: 'basic' or 'oauth'",
    )

    # ── Basic auth ────────────────────────────────────────────────────────────
    servicenow_username: str = Field(
        default="",
        description="ServiceNow username (required when auth_mode=basic)",
    )
    servicenow_password: SecretStr = Field(
        default=SecretStr(""),
        description="ServiceNow password (required when auth_mode=basic)",
    )

    # ── OAuth ─────────────────────────────────────────────────────────────────
    servicenow_client_id: str = Field(
        default="",
        description="OAuth client ID (required when auth_mode=oauth)",
    )
    servicenow_client_secret: SecretStr = Field(
        default=SecretStr(""),
        description="OAuth client secret (required when auth_mode=oauth)",
    )

    # ── HTTP tuning ───────────────────────────────────────────────────────────
    servicenow_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="HTTP request timeout in seconds",
    )
    servicenow_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retry attempts for transient failures",
    )
    servicenow_retry_backoff: float = Field(
        default=1.0,
        gt=0,
        description="Initial backoff in seconds between retries (exponential)",
    )

    # ── MCP transport ─────────────────────────────────────────────────────────
    mcp_transport: MCPTransport = Field(
        default=MCPTransport.STDIO,
        description="MCP server transport: 'stdio' or 'sse'",
    )
    mcp_sse_host: str = Field(
        default="0.0.0.0",
        description="Host to bind when using SSE transport",
    )
    mcp_sse_port: int = Field(
        default=8000,
        gt=0,
        lt=65536,
        description="Port to listen on when using SSE transport",
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        description="Python logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    @field_validator("servicenow_instance_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """Ensure instance URL never ends with a slash."""
        return str(v).rstrip("/")

    @property
    def instance_url(self) -> str:
        """Normalised instance URL as a plain string."""
        return str(self.servicenow_instance_url).rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()  # type: ignore[call-arg]


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with a structured format."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
