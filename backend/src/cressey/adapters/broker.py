"""The key broker: Cressey, not the agent, picks the credential a tool receives. The agent's
own key is ignored, so a key it found, or a call the floor misread, can't exceed the grant."""

from collections.abc import Mapping

from pydantic import JsonValue

from cressey.domain.policy import Credential
from cressey.domain.runs import Mandate


def scoped(
    args: Mapping[str, JsonValue],
    credential: Credential | None,
    mandate: Mandate,
    approved: bool,
) -> Mapping[str, JsonValue]:
    """The arguments the tool receives: the write credential when the mandate grants changes
    or a human approved this call, the read credential otherwise."""
    if credential is None:
        return args
    granted = approved or bool(mandate.may_destroy)
    return {**args, credential.arg: credential.write if granted else credential.read}
