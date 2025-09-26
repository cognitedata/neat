import re
from abc import ABC
from typing import Any

from pydantic import Field, field_validator

from cognite.neat._utils.text import humanize_collection

from ._base import Resource, WriteableResource
from ._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    DM_VERSION_PATTERN,
    FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS,
    SPACE_FORMAT_PATTERN,
)
from ._references import ViewReference

KEY_PATTERN = re.compile(CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN)


class View(Resource, ABC):
    space: str = Field(
        description="Id of the space that the view belongs to.",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )
    external_id: str = Field(
        description="External-id of the view.",
        min_length=1,
        max_length=255,
        pattern=DM_EXTERNAL_ID_PATTERN,
    )
    version: str = Field(
        description="Version of the view.",
        max_length=43,
        pattern=DM_VERSION_PATTERN,
    )
    name: str | None = Field(
        default=None,
        description="name for the view.",
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        description="Description of the view.",
        max_length=1024,
    )
    filter: dict[str, Any] | None = Field(
        default=None,
        description="A filter Domain Specific Language (DSL) used to create advanced filter queries.",
    )
    implements: list[ViewReference] | None = Field(
        default=None,
        description="References to the views from where this view will inherit properties.",
    )

    @field_validator("external_id", mode="after")
    def check_forbidden_external_id_value(cls, val: str) -> str:
        """Check the external_id not present in forbidden set"""
        if val in FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS:
            raise ValueError(
                f"'{val}' is a reserved view External ID. Reserved External IDs are: "
                f"{humanize_collection(FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS)}"
            )
        return val


class ViewRequest(Resource): ...


class ViewResponse(View, WriteableResource[ViewRequest]):
    created_time: int = Field(
        description="When the view was created. The number of milliseconds since 00:00:00 Thursday, 1 January 1970, "
        "Coordinated Universal Time (UTC), minus leap seconds."
    )
    last_updated_time: int = Field(
        description="When the view was last updated. The number of milliseconds since 00:00:00 Thursday, "
        "1 January 1970, Coordinated Universal Time (UTC), minus leap seconds."
    )

    def as_request(self) -> ViewRequest:
        return ViewRequest.model_validate(self.model_dump(by_alias=True))
