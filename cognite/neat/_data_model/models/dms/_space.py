from abc import ABC

from pydantic import Field, field_validator

from cognite.neat.v0.core._utils.text import humanize_collection

from ._base import WriteableResource
from ._constants import FORBIDDEN_SPACES, SPACE_FORMAT_PATTERN


class Space(WriteableResource["SpaceRequest"], ABC):
    space: str = Field(
        description="The Space identifier (id).",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )
    name: str | None = Field(None, description="Name of the space.", max_length=1024)
    description: str | None = Field(None, description="The description of the space.", max_length=255)

    @field_validator("space")
    def check_forbidden_space_value(cls, val: str) -> str:
        """Check the space name not present in forbidden set"""
        if val in FORBIDDEN_SPACES:
            raise ValueError(f"{val!r} is a reserved space. Reserved Spaces: {humanize_collection(FORBIDDEN_SPACES)}")
        return val

    def as_request(self) -> "SpaceRequest":
        return SpaceRequest.model_validate(self.model_dump(by_alias=True))


class SpaceResponse(Space):
    created_time: int = Field(
        description="When the space was created. The number of milliseconds since 00:00:00 Thursday, 1 January 1970, "
        "Coordinated Universal Time (UTC), minus leap seconds."
    )
    last_updated_time: int = Field(
        description="When the space was last updated. The number of milliseconds since 00:00:00 Thursday, "
        "1 January 1970, Coordinated Universal Time (UTC), minus leap seconds."
    )
    is_global: bool = Field(description="Whether the space is a global space.")


class SpaceRequest(Space): ...
