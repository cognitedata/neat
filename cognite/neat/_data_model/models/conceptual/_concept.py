from collections import Counter

from pydantic import Field, ValidationInfo, field_validator
from pyparsing import cast

from cognite.neat._data_model.models.entities import ConceptEntity
from cognite.neat._data_model.models.entities._constants import PREFIX_PATTERN, SUFFIX_PATTERN, VERSION_PATTERN
from cognite.neat._utils.text import humanize_collection

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

    @field_validator("implements", mode="after")
    def cannot_implement_itself(cls, value: list[ConceptEntity], info: ValidationInfo) -> list[ConceptEntity]:
        if not value:
            return value

        this_concept = ConceptEntity(
            prefix=info.data["space"],
            suffix=info.data["external_id"],
            version=cast(str, info.data.get("version")),
        )

        if this_concept in value:
            raise ValueError("A concept cannot implement itself.")

        return value

    @field_validator("implements", mode="after")
    def cannot_have_duplicates(cls, value: list[ConceptEntity], info: ValidationInfo) -> list[ConceptEntity]:
        counts = Counter(value)
        duplicates = {concept for concept, count in counts.items() if count > 1}

        if duplicates:
            raise ValueError(f"Duplicate concepts found: {humanize_collection(duplicates)}")

        return value
