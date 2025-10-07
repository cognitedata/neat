from collections import Counter

from pydantic import Field, ValidationInfo, field_validator

from cognite.neat._data_model.models.entities._constants import PREFIX_PATTERN, SUFFIX_PATTERN, VERSION_PATTERN
from cognite.neat._utils.text import humanize_collection
from cognite.neat.v0.core._data_model.models.entities._single_value import ConceptEntity

from ._base import ResourceMetadata
from ._concept import Concept


class DataModel(ResourceMetadata):
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
    version: str = Field(
        description="Version of the concept.",
        max_length=43,
        pattern=VERSION_PATTERN,
    )

    concepts: list[Concept] = Field(
        description="References to the concepts from where this concept will inherit properties.",
    )

    @field_validator("concepts", mode="after")
    def cannot_have_duplicates(cls, value: list[Concept], info: ValidationInfo) -> list[Concept]:
        concept_ids = [
            ConceptEntity(prefix=concept.space, suffix=concept.external_id, version=concept.version)
            for concept in value
        ]

        counts = Counter(concept_ids)
        duplicates = {concept for concept, count in counts.items() if count > 1}

        if duplicates:
            raise ValueError(f"Duplicate concepts found: {humanize_collection(duplicates)}")

        return value
