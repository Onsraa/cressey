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
    # The triangle's decision model: Jev's API by default, with TYPESAFE_API_KEY (S9: Strands
    # Decider 2B separates no subtle case). A URL here, such as the local Strands Decider's
    # http://127.0.0.1:8100, switches to that server. The guides' re-ranker is `reranker`.
    decider_url: str | None = Field(None, validation_alias="CRESSEY_DECIDER_URL")
    typesafe_api_key: SecretStr | None = None
    web_dir: Path = Field(Path("web"), validation_alias="CRESSEY_WEB_DIR")
    # The guides' rewriter, writer and embedder: OpenAI direct, or Amazon Bedrock (GPT through
    # the Responses API, Cohere Embed). The re-ranker is `reranker`.
    models: Literal["openai", "bedrock"] = Field(
        "bedrock", validation_alias="CRESSEY_MODELS"
    )
    # replay-first: the recorded answer when there is one, live only on a miss (the stage).
    model_mode: Literal["live", "record", "replay", "fallback", "replay-first"] = Field(
        "live", validation_alias="CRESSEY_MODEL_MODE"
    )
    cache_dir: Path = Field(Path("data/cache"), validation_alias="CRESSEY_CACHE_DIR")
    # Under the MCP client's default 300 s read timeout, so the agent gets Cressey's answer.
    hold_timeout: float = Field(240, validation_alias="CRESSEY_HOLD_TIMEOUT")
    demo_dir: Path | None = Field(
        None, validation_alias="CRESSEY_DEMO_DIR"
    )  # temp dir when unset
    # The guides' re-ranker: Jev's API, or Cohere Rerank 3.5 on Bedrock. Measured on dev
    # (10-10): Jev 8/8 guides, Rerank 3.5 6/8, Strands Decider 3/8.
    reranker: Literal["jev", "bedrock"] = Field(
        "jev", validation_alias="CRESSEY_RERANKER"
    )
    aws_region: str = Field("us-east-1", validation_alias="AWS_REGION")
    # The event's temporary credentials, read from .env; boto3's own chain when unset.
    aws_access_key_id: SecretStr | None = Field(
        None, validation_alias="AWS_ACCESS_KEY_ID"
    )
    aws_secret_access_key: SecretStr | None = Field(
        None, validation_alias="AWS_SECRET_ACCESS_KEY"
    )
    aws_session_token: SecretStr | None = Field(
        None, validation_alias="AWS_SESSION_TOKEN"
    )
    # Two confirmed legs hold a call. Off measures the safety floor alone (the ablation).
    triangle_holds: bool = Field(True, validation_alias="CRESSEY_TRIANGLE_HOLDS")
    # At fleet scale nobody waits on each hold: `refuse` refuses it at once, with the way out.
    holds: Literal["wait", "refuse"] = Field("wait", validation_alias="CRESSEY_HOLDS")

    @property
    def relevance_min(self) -> float:
        """The re-ranking threshold, calibrated per re-ranker on the dev set (the S6 method)."""
        # Jev, S6: keeps 51/55 expected passages and 16/185 others. Rerank 3.5, 10-10:
        # 47/57 and 63/191; no out-of-scope question keeps a passage (their best is < 0.15).
        return {"bedrock": 0.2, "jev": 0.4}[self.reranker]

    @property
    def rerank_model(self) -> str:
        return {"bedrock": "cohere.rerank-v3-5:0", "jev": "jev-1.13.0"}[self.reranker]

    @property
    def rewrite_model(self) -> str:
        # gpt-5.4-mini isn't on Bedrock. Dev, two runs (10-10): GPT-5.6 Sol re-ranked hit@3
        # 61/62, GPT-5.4 60/62 but 0.27 s faster a call; Luna 30/31 in one run, the slowest.
        return {"bedrock": "us.openai.gpt-5.6-sol", "openai": "gpt-5.4-mini"}[
            self.models
        ]

    @property
    def writer_model(self) -> str:
        # S6: 23/23 verified quotes vs 19/21 for gpt-5.4-mini. Bedrock wants an inference
        # profile; the us. ones need a US region.
        return {"bedrock": "us.openai.gpt-5.5", "openai": "gpt-5.5"}[self.models]

    @property
    def embedding_model(self) -> str:
        return {
            "bedrock": "cohere.embed-multilingual-v3",
            "openai": "text-embedding-3-small",
        }[self.models]

    @property
    def decision_model(self) -> str:
        """One switch: the local decider's model when its URL is set, otherwise Jev's."""
        return (
            "strands-decider-2B-qwen3.5-v1-2610" if self.decider_url else "jev-1.13.0"
        )

    @field_validator(
        "openai_api_key",
        "typesafe_api_key",
        "decider_url",
        mode="before",
    )
    @classmethod
    def _blank_is_missing(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v
