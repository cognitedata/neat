from typing import Any

import respx

from cognite.neat._client.config import NeatClientConfig
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._container import ContainerResponse
from cognite.neat._data_model.models.dms._data_model import DataModelResponse
from cognite.neat._data_model.models.dms._data_types import TextProperty
from cognite.neat._data_model.models.dms._space import SpaceResponse
from cognite.neat._data_model.models.dms._view_property import (
    ConstraintOrIndexState,
    MultiEdgeProperty,
    MultiReverseDirectRelationPropertyRequest,
    MultiReverseDirectRelationPropertyResponse,
    SingleEdgeProperty,
    SingleReverseDirectRelationPropertyRequest,
    SingleReverseDirectRelationPropertyResponse,
    ViewCorePropertyRequest,
    ViewCorePropertyResponse,
)
from cognite.neat._data_model.models.dms._views import ViewResponse


def snapshot_to_response_schema(snapshot: SchemaSnapshot) -> dict[str, Any]:
    """This is a helper method for tests that converts a SchemaSnapshot
    to a dict representing the response schema"""

    timestamp = int(snapshot.timestamp.timestamp())

    datamodels = (
        [
            DataModelResponse(
                **dm.model_dump(by_alias=True, exclude_unset=True),
                createdTime=timestamp,
                lastUpdatedTime=timestamp,
                isGlobal=True,
            ).model_dump(by_alias=True, exclude_unset=True)
            for dm in snapshot.data_model.values()
        ]
        if snapshot.data_model
        else []
    )
    containers = (
        [
            ContainerResponse(
                **container.model_dump(by_alias=True, exclude_unset=True),
                createdTime=timestamp,
                lastUpdatedTime=timestamp,
                isGlobal=True,
                writable=True,
                queryable=True,
            ).model_dump(by_alias=True, exclude_unset=True)
            for container in snapshot.containers.values()
        ]
        if snapshot.containers
        else []
    )
    spaces = (
        [
            SpaceResponse(
                **space.model_dump(by_alias=True, exclude_unset=True),
                createdTime=timestamp,
                lastUpdatedTime=timestamp,
                isGlobal=True,
            ).model_dump(by_alias=True, exclude_unset=True)
            for space in snapshot.spaces.values()
        ]
        if snapshot.spaces
        else []
    )

    views = snapshot_to_view_response(snapshot)

    return {"datamodels": datamodels, "containers": containers, "spaces": spaces, "views": views}


def snapshot_to_view_response(snapshot: SchemaSnapshot) -> list[dict[str, Any]]:
    """Convert views in snapshot to list of view response dicts.
    This is a helper method for tests.
    Args:
        snapshot (SchemaSnapshot): The schema snapshot containing the views.
    """

    timestamp = int(snapshot.timestamp.timestamp())
    views: list[dict[str, Any]] = []

    if not snapshot.views:
        return views

    for view in snapshot.views.values():
        if not view.properties:
            continue

        model_dump = view.model_dump(by_alias=True, exclude_unset=True)
        model_dump["createdTime"] = model_dump["lastUpdatedTime"] = timestamp
        model_dump["isGlobal"] = model_dump["writable"] = model_dump["queryable"] = True
        model_dump["usedFor"] = "all"
        model_dump["mappedContainers"] = view.used_containers

        properties: dict[
            str,
            ViewCorePropertyResponse
            | SingleReverseDirectRelationPropertyResponse
            | MultiReverseDirectRelationPropertyResponse
            | SingleEdgeProperty
            | MultiEdgeProperty,
        ] = {}
        for id, prop in view.properties.items():
            response: (
                ViewCorePropertyResponse
                | SingleReverseDirectRelationPropertyResponse
                | MultiReverseDirectRelationPropertyResponse
                | SingleEdgeProperty
                | MultiEdgeProperty
            )
            if isinstance(prop, ViewCorePropertyRequest):
                response = ViewCorePropertyResponse(
                    **prop.model_dump(by_alias=True, exclude_unset=True),
                    constraintState=ConstraintOrIndexState(),
                    type=TextProperty(),  # Default type for testing purposes, can be updated to consider containers
                )
            elif isinstance(prop, SingleReverseDirectRelationPropertyRequest):
                response = SingleReverseDirectRelationPropertyResponse(
                    **prop.model_dump(by_alias=True, exclude_unset=True), targetsList=True
                )
            elif isinstance(prop, MultiReverseDirectRelationPropertyRequest):
                response = MultiReverseDirectRelationPropertyResponse(
                    **prop.model_dump(by_alias=True, exclude_unset=True), targetsList=True
                )
            else:
                response = prop
            properties[id] = response

        model_dump["properties"] = properties

        views.append(ViewResponse(**model_dump).model_dump(by_alias=True))

    return views


def update_mock_router(snapshot: SchemaSnapshot, client: NeatClientConfig, respx_mock: respx.MockRouter) -> None:
    """Update the respx mock router with responses based on the provided snapshot.

    Args:
        snapshot (SchemaSnapshot): The schema snapshot to base the responses on.
        client (NeatClientConfig): The Neat client configuration.
        respx_mock (respx.MockRouter): The respx mock router to update.

    """

    responses = snapshot_to_response_schema(snapshot)

    calls = ["/models/containers", "/models/views", "/models/datamodels", "/models/spaces"]

    for call in calls:
        resource = call.split("/")[-1].split("?")[0]
        items = responses.get(resource, [])

        respx_mock.get(
            client.create_api_url(call),
        ).respond(
            status_code=200,
            json={
                "items": items,
                "nextCursor": None,
            },
        )

    return None
