from pydantic import Field

from cognite.neat._data_model.models.entities import ConceptEntity
from cognite.neat._data_model.models.entities._constants import PREFIX_PATTERN, SUFFIX_PATTERN, VERSION_PATTERN

from ._base import ResourceMetadata
from ._property import Property


class Concept(ResourceMetadata):
    space: str = Field(
        description="Id of the space that the concept belongs to.",
        min_length=1,
        max_length=43,
        pattern=PREFIX_PATTERN,
        alias="prefix",
    )
    external_id: str = Field(
        description="External-id of the concept.",
        min_length=1,
        max_length=255,
        pattern=SUFFIX_PATTERN,
        alias="suffix",
    )
    version: str | None = Field(
        default=None,
        description="Version of the concept.",
        max_length=43,
        pattern=VERSION_PATTERN,
    )

    implements: list[ConceptEntity] | None = Field(
        default=None,
        description="References to the concepts from where this concept will inherit properties.",
    )

    properties: dict[str, Property] | None = Field(default=None, description="Properties associated with the concept.")
