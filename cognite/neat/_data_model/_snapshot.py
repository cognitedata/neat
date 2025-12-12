import sys
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_serializer
from pydantic_core.core_schema import FieldSerializationInfo

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

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class SchemaSnapshot(BaseModel, extra="ignore"):
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

    def merge(self, cdf: Self) -> Self:
        """Merge local and CDF snapshots, prioritizing local definitions."""
        merged = self.model_copy(deep=True)

        for model_ref, local_model in merged.data_model.items():
            if model_ref not in cdf.data_model:
                continue
            cdf_model = cdf.data_model[model_ref]
            if new_views := (set(cdf_model.views or []) - set(local_model.views or [])):
                for view_ref in new_views:
                    if cdf_view := cdf.views.get(view_ref):
                        merged.views[view_ref] = cdf_view
            # We append the local views at the end of the CDF views.
            local_model.views = list(dict.fromkeys((cdf_model.views or []) + (local_model.views or [])).keys())

        # Update local views with additional properties and implements from CDF views
        for view_ref, view in merged.views.items():
            if cdf_view := cdf.views.get(view_ref):
                if cdf_only_containers := cdf_view.used_containers - set(view.used_containers):
                    for cdf_only_container_ref in cdf_only_containers:
                        if (
                            cdf_container := cdf.containers.get(cdf_only_container_ref)
                        ) and cdf_only_container_ref not in merged.containers:
                            merged.containers[cdf_only_container_ref] = cdf_container

                view.properties = {**cdf_view.properties, **view.properties}

                # update implements
                if cdf_view.implements:
                    view.implements = list(dict.fromkeys(cdf_view.implements + (view.implements or [])).keys())

        for container_ref, container in merged.containers.items():
            if cdf_container := cdf.containers.get(container_ref):
                container.properties = {**cdf_container.properties, **container.properties}

        return merged
