"""The model clients' plumbing: OpenAI direct or through Bedrock, the AWS clients, and the
decision model's credentials. Every client fails fast, and a call that gets no answer
raises ModelUnavailable: the record-and-replay cache (llm/cache.py) answers then."""

from typing import Any

import boto3
import openai
from botocore.client import BaseClient
from botocore.config import Config
from openai.providers import bedrock
from pydantic import BaseModel, ValidationError

from cressey.settings import Settings


class ModelUnavailable(Exception):
    """A model call failed (SDK error, timeout, 429 after retries, missing key, cache miss in replay)."""


class Adapter:
    def __init__(self, client: Any, model: str = "") -> None:
        self.client, self.model = client, model

    def _c(self) -> Any:
        if self.client is None:
            raise ModelUnavailable("missing key")
        return self.client

    def _parse[T: BaseModel](self, system: str, user: str, fmt: type[T]) -> T:
        try:
            r = self._c().responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                text_format=fmt,
                store=False,  # incident text must not be kept by the provider (30 days by default)
            )
        except (
            openai.OpenAIError,
            ValidationError,
        ) as e:  # ValidationError: truncated output
            raise ModelUnavailable(str(e)) from e
        if r.output_parsed is None:
            raise ModelUnavailable("no parsed output (refusal)")
        return r.output_parsed


def openai_client(settings: Settings) -> openai.OpenAI | None:
    key = settings.openai_api_key
    # Fail fast: in `fallback` mode the cache answers only after the live call gives up.
    return (
        openai.OpenAI(
            api_key=key.get_secret_value(),
            timeout=openai.Timeout(20, connect=5),
            max_retries=1,
        )
        if key
        else None
    )


def responses_client(s: Settings) -> openai.OpenAI | None:
    """The rewriter's and the writer's client. On Bedrock, the SDK's provider signs each request
    with the AWS credentials (SigV4): no Bedrock API key to mint, none to expire."""
    if s.models == "openai":
        return openai_client(s)
    creds = aws_credentials(s)
    provider = bedrock(
        endpoint="runtime",
        region=s.aws_region,
        access_key_id=creds.get("aws_access_key_id"),
        secret_access_key=creds.get("aws_secret_access_key"),
        session_token=creds.get("aws_session_token"),
    )
    return openai.OpenAI(
        provider=provider, timeout=openai.Timeout(20, connect=5), max_retries=1
    )


LOCAL_KEY = "local"  # the local decider ignores the key, but the SDK wants one


def decision_auth(s: Settings) -> tuple[str, str | None] | None:
    """(API key, base URL) for the decision model: the local Strands Decider when its URL
    is set, otherwise Jev's API. None when neither is configured."""
    if s.decider_url:
        return LOCAL_KEY, s.decider_url
    key = s.typesafe_api_key
    return (key.get_secret_value(), None) if key else None


def aws_credentials(s: Settings) -> dict[str, str]:
    """The credentials set in .env; when none are, boto3 uses its own chain."""
    keys = {
        "aws_access_key_id": s.aws_access_key_id,
        "aws_secret_access_key": s.aws_secret_access_key,
        "aws_session_token": s.aws_session_token,
    }
    return {name: v.get_secret_value() for name, v in keys.items() if v}


def aws_client(service: str, s: Settings) -> BaseClient:
    return boto3.client(
        service,
        region_name=s.aws_region,
        # Fail fast, like openai_client: the cache answers only after the live call gives up.
        config=Config(
            connect_timeout=5,
            read_timeout=20,
            retries={"total_max_attempts": 2, "mode": "standard"},
        ),
        **aws_credentials(s),
    )
