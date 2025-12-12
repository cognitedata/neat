from datetime import datetime, timezone
from typing import Any

from pydantic import Field, field_serializer
from pydantic_core.core_schema import FieldSerializationInfo

from cognite.neat._data_model.deployer.data_classes import BaseDeployObject
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    ContainerRequest,
    DataModelReference,
    DataModelRequest,
    NodeReference,
    SpaceReference,
    SpaceRequest,
    ViewReference,
    ViewRequest,
)


class SchemaSnapshot(BaseDeployObject):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_model: dict[DataModelReference, DataModelRequest] = Field(default_factory=dict)
    views: dict[ViewReference, ViewRequest] = Field(default_factory=dict)
    containers: dict[ContainerReference, ContainerRequest] = Field(default_factory=dict)
    spaces: dict[SpaceReference, SpaceRequest] = Field(default_factory=dict)
    node_types: dict[NodeReference, NodeReference] = Field(default_factory=dict)

    @field_serializer("data_model", "views", "containers", "spaces", "node_types", mode="plain")
    @classmethod
    def make_hashable_keys(cls, value: dict, info: FieldSerializationInfo) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, val in value.items():
            dumped_value = val.model_dump(**vars(info))
            output[str(key)] = dumped_value
        return output
