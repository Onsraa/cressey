"""The key a request carries: the agents' ways in and the control plane read it alike."""

from typing import Annotated

from fastapi import Header

AuthorizationHeader = Annotated[str, Header()]


def bearer(authorization: str) -> str:
    """The key in an `Authorization: Bearer <key>` header."""
    return authorization.removeprefix("Bearer ").strip()
