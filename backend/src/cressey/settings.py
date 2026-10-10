from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # populate_by_name lets tests pass web_dir=…; it also makes plain WEB_DIR readable (harmless).
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore", populate_by_name=True
    )

    openai_api_key: SecretStr | None = None
    typesafe_api_key: SecretStr | None = None
    web_dir: Path = Field(Path("web"), validation_alias="CRESSEY_WEB_DIR")
