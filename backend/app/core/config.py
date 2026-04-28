from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Shared Azure key.
    azure_openai_api_key: str = Field(min_length=1)

    # Whisper deployment (transcription).
    azure_openai_whisper_endpoint: str = Field(min_length=1)
    azure_openai_whisper_api_version: str = "2024-06-01"
    azure_openai_whisper_deployment: str = Field(min_length=1)

    # GPT deployment (vision + report synthesis).
    azure_openai_gpt_endpoint: str = Field(min_length=1)
    azure_openai_gpt_api_version: str = "2024-12-01-preview"
    azure_openai_gpt_deployment: str = Field(min_length=1)

    log_level: str = "INFO"
    storage_dir: Path = Path("./var")
    templates_dir: Path = Path("../data/4 Report Templates")
    glossary_path: Path | None = None
    max_upload_mb: int = 200
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("azure_openai_whisper_endpoint", "azure_openai_gpt_endpoint")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
