from typing import Literal

from pydantic import Field

from cognite.neat._utils.useful_types import ReferenceObject

from ._constants import (
    CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    DM_EXTERNAL_ID_PATTERN,
    DM_VERSION_PATTERN,
    INSTANCE_ID_PATTERN,
    SPACE_FORMAT_PATTERN,
)


class SpaceReference(ReferenceObject):
    space: str = Field(
        description="Id of the space.",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )


class ContainerReference(ReferenceObject):
    type: Literal["container"] = Field("container", exclude=True)
    space: str = Field(
        description="Id of the space hosting (containing) the container.",
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

    def __str__(self) -> str:
        return f"{self.space}:{self.external_id}"


class ViewReference(ReferenceObject):
    type: Literal["view"] = Field("view", exclude=True)
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

    def __str__(self) -> str:
        return f"{self.space}:{self.external_id}(version={self.version})"


class DataModelReference(ReferenceObject):
    space: str = Field(
        description="Id of the space that the data model belongs to.",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )
    external_id: str = Field(
        description="External-id of the data model.",
        min_length=1,
        max_length=255,
        pattern=DM_EXTERNAL_ID_PATTERN,
    )
    version: str = Field(
        description="Version of the data model.",
        max_length=43,
        pattern=DM_VERSION_PATTERN,
    )

    def __str__(self) -> str:
        return f"{self.space}:{self.external_id}(version={self.version})"


class NodeReference(ReferenceObject):
    space: str = Field(
        description="Id of the space hosting (containing) the node.",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )
    external_id: str = Field(
        description="External-id of the node.",
        min_length=1,
        max_length=255,
        pattern=INSTANCE_ID_PATTERN,
    )


class ContainerDirectReference(ReferenceObject):
    source: ContainerReference = Field(
        description="Reference to the container from where this relation is inherited.",
    )
    identifier: str = Field(
        description="Identifier of the relation in the source container.",
        min_length=1,
        max_length=255,
        pattern=CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    )


class ViewDirectReference(ReferenceObject):
    source: ViewReference = Field(
        description="Reference to the view from where this relation is inherited.",
    )
    identifier: str = Field(
        description="Identifier of the relation in the source view.",
        min_length=1,
        max_length=255,
        pattern=CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN,
    )


class ContainerIndexReference(ContainerReference):
    identifier: str


class ContainerConstraintReference(ContainerReference):
    identifier: str
