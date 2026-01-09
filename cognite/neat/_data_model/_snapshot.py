import sys
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_serializer
from pydantic_core.core_schema import FieldSerializationInfo

from cognite.neat._client import NeatClient
from cognite.neat._data_model.models.dms import (
    ContainerReference,
    ContainerRequest,
    DataModelReference,
    DataModelRequest,
    NodeReference,
    RequestSchema,
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
        """Merge another SchemaSnapshot into this one, prioritizing this snapshot's data."""
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
                container.constraints = {**(cdf_container.constraints or {}), **(container.constraints or {})} or None

        return merged

    @classmethod
    def fetch_cdf_data_model(cls, client: NeatClient, data_model: RequestSchema) -> Self:
        """Fetch the latest data model, views, containers, and spaces from CDF based on the provided RequestSchema."""
        now = datetime.now(timezone.utc)
        space_ids = [space.as_reference() for space in data_model.spaces]
        cdf_spaces = client.spaces.retrieve(space_ids)

        container_refs = [c.as_reference() for c in data_model.containers]
        cdf_containers = client.containers.retrieve(container_refs)

        view_refs = [v.as_reference() for v in data_model.views]
        cdf_views = client.views.retrieve(view_refs)

        dm_ref = data_model.data_model.as_reference()
        cdf_data_models = client.data_models.retrieve([dm_ref])

        nodes = [node_type for view in cdf_views for node_type in view.node_types]
        return cls(
            timestamp=now,
            data_model={dm.as_reference(): dm.as_request() for dm in cdf_data_models},
            views={view.as_reference(): view.as_request() for view in cdf_views},
            containers={container.as_reference(): container.as_request() for container in cdf_containers},
            spaces={space.as_reference(): space.as_request() for space in cdf_spaces},
            node_types={node: node for node in nodes},
        )

    @classmethod
    def fetch_entire_cdf(cls, client: NeatClient) -> Self:
        """Fetch the entire data model, views, containers, and spaces from CDF."""
        now = datetime.now(timezone.utc)
        all_views = client.views.list(
            all_versions=True, include_global=True, include_inherited_properties=False, limit=None
        )
        nodes = [node_type for view in all_views for node_type in view.node_types]
        return cls(
            # TODO: spaces and data_models should be update after updating list methods for unlimited no
            spaces={
                response.as_reference(): response.as_request()
                for response in client.spaces.list(include_global=True, limit=1000)
            },
            data_model={
                response.as_reference(): response.as_request()
                for response in client.data_models.list(all_versions=True, include_global=True, limit=1000)
            },
            views={response.as_reference(): response.as_request() for response in all_views},
            containers={
                response.as_reference(): response.as_request()
                for response in client.containers.list(include_global=True, limit=None)
            },
            node_types={node_type: node_type for node_type in nodes},
            timestamp=now,
        )
