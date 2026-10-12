from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend's data: the policy, the corpus, the sessions, the recorded model answers.
DATA = Path(__file__).parents[2] / "data"
DEMO_PROFILE = DATA / "profiles" / "demo.yaml"  # the demo's own tools


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
    # What this Cressey fronts: its MCP servers, what their tools do, the key broker and the
    # trap keys (domain/policy.py, Profile). The demo's own tools by default.
    profile: Path = Field(DEMO_PROFILE, validation_alias="CRESSEY_PROFILE")
    # Trap keys planted outside the demo workspace, name: value as JSON, added to the
    # profile's. A real token an agent can find goes here, never in a profile.
    decoys: dict[str, str] = Field(
        default_factory=dict, validation_alias="CRESSEY_DECOYS"
    )
    # Two confirmed legs hold a call. Off measures the safety floor alone (the ablation).
    triangle_holds: bool = Field(True, validation_alias="CRESSEY_TRIANGLE_HOLDS")
    # On, an excuse in a thought (R or C1 going toward the crossing) with pressure or
    # opportunity confirmed stops the agent at its next call, whatever it is, and confirms
    # rationalization there. Off, the words show on the triangle and never hold.
    thought_holds: bool = Field(False, validation_alias="CRESSEY_THOUGHT_HOLDS")
    # At fleet scale nobody waits on each hold: `refuse` refuses it at once, with the way out.
    holds: Literal["wait", "refuse"] = Field("wait", validation_alias="CRESSEY_HOLDS")
    # The control plane's key (Authorization: Bearer): deciding holds, unlocking, the policy
    # and every read of runs and incidents. The agent only ever holds its run key. Unset, each
    # start draws a random key no client knows, so the control plane stays locked.
    admin_token: SecretStr | None = Field(None, validation_alias="CRESSEY_ADMIN_TOKEN")
    # Where the event log, its anchor and the runs' keys are kept, so a restart keeps them.
    # Unset, they live in memory (tests, replays, the evaluation's throwaway Cresseys).
    state_dir: Path | None = Field(None, validation_alias="CRESSEY_STATE_DIR")
    # Where Cressey itself answers, its API and its dashboard: the safety floor holds a call
    # an agent aims at either.
    base_url: str = Field("http://localhost:8000", validation_alias="CRESSEY_URL")
    dashboard_url: str = Field(
        "http://localhost:5173", validation_alias="CRESSEY_DASHBOARD_URL"
    )

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
        "admin_token",
        "state_dir",
        mode="before",
    )
    @classmethod
    def _blank_is_missing(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v

    def on_demo(self, folder: Path) -> "Settings":
        """These settings on the demo's own tools, seeded fresh in `folder`, keeping nothing:
        what plays the demo's scripted sessions (the evals, the stage, « Rejouer ×5 », the
        tests) must never reach the servers a profile names."""
        update = {"demo_dir": folder, "state_dir": None, "profile": DEMO_PROFILE}
        return self.model_copy(update=update)
