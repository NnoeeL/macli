"""Configuration loading and validation for macli."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator


class ConfigError(Exception):
    """Raised when macli configuration is missing or invalid."""


class Settings(BaseModel):
    """Validated LLM and runtime settings loaded from environment variables."""

    api_key: str = Field(..., min_length=1, description="LLM API key")
    base_url: str = Field(
        default="https://api.openai.com/v1",
        min_length=1,
        description="OpenAI-compatible API base URL",
    )
    model: str = Field(
        default="gpt-4o-mini",
        min_length=1,
        description="Model identifier",
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    timeout: float = Field(default=120.0, gt=0.0)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in {
            "your-api-key-here",
            "your_api_key_here",
            "changeme",
            "replace-me",
        }:
            raise ValueError(
                "LLM_API_KEY is missing or still set to a placeholder value."
            )
        return cleaned

    @field_validator("base_url", "model")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be empty.")
        return cleaned


def load_settings(env_path: Path | None = None) -> Settings:
    """Load settings from a .env file and environment variables.

    Args:
        env_path: Optional explicit path to a .env file. Defaults to `.env` in CWD.

    Returns:
        A validated Settings instance.

    Raises:
        ConfigError: If required environment variables are missing or invalid.
    """
    target_env = env_path or (Path.cwd() / ".env")
    if target_env.exists():
        load_dotenv(dotenv_path=target_env, override=False)

    raw_api_key = os.getenv("LLM_API_KEY", "")
    raw_base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    raw_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    raw_temperature = os.getenv("LLM_TEMPERATURE", "0.2")
    raw_timeout = os.getenv("LLM_TIMEOUT", "120.0")

    if not raw_api_key.strip():
        hint = (
            "Run `macli init` to generate a `.env` template, then set `LLM_API_KEY`, "
            "`LLM_BASE_URL`, and `LLM_MODEL`."
        )
        if not target_env.exists():
            raise ConfigError(f"No `.env` file found and `LLM_API_KEY` is not set.\n{hint}")
        raise ConfigError(f"`LLM_API_KEY` is not set in `{target_env}`.\n{hint}")

    try:
        return Settings(
            api_key=raw_api_key,
            base_url=raw_base_url,
            model=raw_model,
            temperature=float(raw_temperature),
            timeout=float(raw_timeout),
        )
    except (ValidationError, ValueError) as exc:
        raise ConfigError(
            f"Invalid configuration: {exc}\n"
            "Please check your `.env` file or run `macli init` to create a fresh template."
        ) from exc
