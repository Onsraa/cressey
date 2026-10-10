from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # populate_by_name lets tests pass web_dir=…; it also makes plain WEB_DIR readable (harmless).
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore", populate_by_name=True
    )

    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = (
        None  # Bedrock: https://bedrock-runtime.<region>.amazonaws.com/openai/v1
    )
    typesafe_api_key: SecretStr | None = None
    web_dir: Path = Field(Path("web"), validation_alias="CRESSEY_WEB_DIR")
    rewrite_model: str = "gpt-5.4-mini"
    writer_model: str = "gpt-5.5"  # S6: 23/23 verified quotes vs 19/21 for gpt-5.4-mini
    embedding_model: str = "text-embedding-3-small"
    model_mode: Literal["live", "record", "replay", "fallback"] = Field(
        "live", validation_alias="CRESSEY_MODEL_MODE"
    )
    cache_dir: Path = Field(Path("data/cache"), validation_alias="CRESSEY_CACHE_DIR")
    # Under the MCP client's default 300 s read timeout, so the agent gets Cressey's answer.
    hold_timeout: float = Field(240, validation_alias="CRESSEY_HOLD_TIMEOUT")
    demo_dir: Path | None = Field(
        None, validation_alias="CRESSEY_DEMO_DIR"
    )  # temp dir when unset
    relevance_min: float = (
        0.4  # S6 calibration: keeps 51/55 expected passages, 16/185 others
    )

    @field_validator(
        "openai_api_key", "openai_base_url", "typesafe_api_key", mode="before"
    )
    @classmethod
    def _blank_is_missing(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v
