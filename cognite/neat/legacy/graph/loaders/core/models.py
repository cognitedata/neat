from __future__ import annotations

import logging
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, root_validator, validator
from rdflib import Namespace

from cognite.neat.legacy.rules.models.rules import METADATA_VALUE_MAX_LENGTH


class AssetClassMapping(BaseModel):
    external_id: str
    name: str
    parent_external_id: str | None = None
    description: str | None = None
    metadata: dict | None = {}

    @root_validator(pre=True)
    def create_metadata(cls, values: dict):
        fields = values.keys()

        # adding metadata key in case if it is missing
        values["metadata"] = {} if "metadata" not in values else values["metadata"]

        for field in fields:
            if field not in ["external_id", "name", "parent_external_id", "data_set_id", "metadata", "description"]:
                values["metadata"][field] = ""
        return values


class AssetTemplate(BaseModel):
    """This class is used to validate, repair and wrangle rdf asset dictionary according to the
    expected format of cognite sdk Asset dataclass."""

    external_id_prefix: str | None = None  # convenience field to add prefix to external_ids
    external_id: str
    name: str | None = None
    parent_external_id: str | None = None
    metadata: dict | None = {}
    description: str | None = None
    data_set_id: int | None = None

    @root_validator(pre=True)
    def preprocess_fields(cls, values: dict):
        fields = values.keys()

        # Adding metadata key in case if it is missing
        values["metadata"] = {} if "metadata" not in values else values["metadata"]

        for field in fields:
            # Enrich: adding any field that is not in the list of expected fields to metadata
            if field not in [
                "external_id",
                "name",
                "parent_external_id",
                "data_set_id",
                "metadata",
                "description",
                "external_id_prefix",
            ]:
                values["metadata"][field] = values[field]

            # Repair: in case if name/description is list instead of single value list elements are joined
            elif field in ["name", "description"] and isinstance(values[field], list):
                msg = f"{values['type']} instance {values['identifier']} property {field} "
                msg += f"has multiple values {values[field]}, "
                msg += f"these values will be joined in a single string: {', '.join(values[field])}"
                logging.info(msg)
                values[field] = ", ".join(sorted(values[field]))[: METADATA_VALUE_MAX_LENGTH - 1]

            # Repair: in case if external_id or parent_external_id are lists, we take the first value
            elif field in ["external_id", "parent_external_id"] and isinstance(values[field], list):
                msg = f"{values['type']} instance {values['identifier']} property {field} "
                msg += f"has multiple values {values[field]}, "
                msg += f"only the first one will be used: {values[field][0]}"
                logging.info(msg)
                values[field] = values[field][0]

        # Setting asset to be by default active
        values["metadata"]["active"] = "true"

        # Handling case when the external_id is not provided by defaulting to the original identifier
        # The original identifier probably has its namespace removed
        if "external_id" not in fields and "identifier" in fields:
            values["external_id"] = values["identifier"]

        return values

    @validator("metadata")
    def to_list_if_comma(cls, value):
        for key, v in value.items():
            if isinstance(v, list):
                value[key] = ", ".join(sorted(v))[: METADATA_VALUE_MAX_LENGTH - 1]
        return value

    @validator("metadata")
    def to_str(cls, value):
        for key, v in value.items():
            value[key] = str(v)
        return value

    @validator("external_id", always=True)
    def add_prefix_to_external_id(cls, value, values):
        if values["external_id_prefix"]:
            return values["external_id_prefix"] + value
        else:
            return value

    @validator("parent_external_id")
    def add_prefix_to_parent_external_id(cls, value, values):
        if values["external_id_prefix"]:
            return values["external_id_prefix"] + value
        else:
            return value


class RelationshipDefinition(BaseModel):
    source_class: str
    target_class: str
    property_: str
    labels: list[str] | None = None
    target_type: str = "Asset"
    source_type: str = "Asset"
    relationship_external_id_rule: str | None = None


class RelationshipDefinitions(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True, strict=False
    )

    data_set_id: int
    prefix: str
    namespace: Namespace
    relationships: dict[str, RelationshipDefinition]
