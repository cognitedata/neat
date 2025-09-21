import re
from typing import Literal

from pydantic import Field, field_validator

from cognite.neat.core._utils.text import humanize_collection

from ._base import WriteableResource
from ._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS,
    SPACE_FORMAT_PATTERN,
)

KEY_PATTERN = re.compile(CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN)


class Container(WriteableResource):
    space: str = Field(
        description="The workspace for the container, a unique identifier for the space.",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )
    external_id: str = Field(
        description="External-id of the container.",
        min_length=1,
        max_length=255,
        pattern=DM_EXTERNAL_ID_PATTERN,
    )
    name: str | None = Field(
        default=None,
        description="name for the container.",
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Description of the container.",
        max_length=1024,
    )
    used_for: Literal["node", "edge", "all"] | None = Field(
        default=None,
        description="Should this operation apply to nodes, edges or both.",
    )

    @field_validator("external_id")
    def check_forbidden_external_id_value(cls, val: str) -> str:
        """Check the external_id not present in forbidden set"""
        if val in FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS:
            raise ValueError(
                f"{val!r} is a reserved container External ID. Reserved External IDs are:"
                f"{humanize_collection(FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS)}"
            )
        return val

    def as_request(self) -> "ContainerRequest":
        return ContainerRequest.model_validate(
            self.model_dump(by_alias=True, exclude={"created_time", "last_updated_time", "is_global"})
        )


class ContainerResponse(Container):
    created_time: int = Field(
        description="When the container was created. The number of milliseconds since 00:00:00 "
        "Thursday, 1 January 1970, "
        "Coordinated Universal Time (UTC), minus leap seconds."
    )
    last_updated_time: int = Field(
        description="When the container was last updated. The number of milliseconds since 00:00:00 Thursday, "
        "1 January 1970, Coordinated Universal Time (UTC), minus leap seconds."
    )
    is_global: bool = Field(description="Whether the container is a global container.")


class ContainerRequest(Container): ...
