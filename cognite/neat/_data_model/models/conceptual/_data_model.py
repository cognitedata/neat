from pydantic import Field, ValidationInfo, field_validator

from cognite.neat._data_model.models.entities._constants import PREFIX_PATTERN, SUFFIX_PATTERN, VERSION_PATTERN

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
        concept_ids = [(concept.space, concept.external_id, concept.version) for concept in value]

        concept_tuples = set()
        duplicates = set()

        for concept in concept_ids:
            if concept in concept_tuples:
                duplicates.add(concept)
            else:
                concept_tuples.add(concept)
        if duplicates:
            duplicate_strs = [
                f"{space}:{external_id}{f'(version={version})' if version else ''}"
                for space, external_id, version in duplicates
            ]
            raise ValueError(f"Duplicate concepts found: {', '.join(duplicate_strs)}")

        return value
