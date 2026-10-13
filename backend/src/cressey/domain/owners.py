"""The triangle's legs, and who owns the fix for each: an incident's guides and fixes and the
task's assessment before the run name the same owners."""

from typing import Literal

LegName = Literal["pressure", "opportunity", "rationalization"]
OwnerRole = Literal["key_owner", "task_author", "platform_owner", "soc"]
LEGS: tuple[LegName, ...] = ("pressure", "opportunity", "rationalization")
OWNERS: dict[LegName, OwnerRole] = {
    "pressure": "task_author",
    "opportunity": "key_owner",
    "rationalization": "platform_owner",
}
OWNER_NAMES: dict[OwnerRole, str] = {
    "task_author": "task author",
    "key_owner": "key owner",
    "platform_owner": "platform owner",
}
