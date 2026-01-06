from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any, Literal, TypeAlias, overload

import respx
import yaml

from cognite.neat._client.config import NeatClientConfig
from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._container import ContainerRequest, ContainerResponse
from cognite.neat._data_model.models.dms._data_model import DataModelRequest, DataModelResponse
from cognite.neat._data_model.models.dms._data_types import TextProperty
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import ContainerReference, DataModelReference, ViewReference
from cognite.neat._data_model.models.dms._schema import RequestSchema
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
from cognite.neat._data_model.models.dms._views import ViewRequest, ViewResponse
from cognite.neat._utils.useful_types import ModusOperandi

ROOT = Path(__file__).parent
LOCAL_SNAPSHOTS_DIR = ROOT / "local"
CDF_SNAPSHOTS_DIR = ROOT / "cdf"
ENCODING = "utf-8"
LIMITS = SchemaLimits()

now = datetime.now()

LocalScenario: TypeAlias = Literal["ai_readiness", "bi_directional_connections", "uncategorized_validators"]
CDFScenario: TypeAlias = Literal["cdm", "for_validators"]


class Catalog:
    @overload
    def load_scenario(
        self,
        local_scenario_name: LocalScenario,
        cdf_scenario_name: CDFScenario | None = None,
        modus_operandi: ModusOperandi = "additive",
        include_cdm: bool = False,
        format: Literal["validation-resource"] = "validation-resource",
    ) -> ValidationResources: ...

    @overload
    def load_scenario(
        self,
        local_scenario_name: LocalScenario,
        cdf_scenario_name: CDFScenario | None = None,
        modus_operandi: ModusOperandi = "additive",
        include_cdm: bool = False,
        format: Literal["snapshots"] = "snapshots",
    ) -> tuple[SchemaSnapshot, SchemaSnapshot]: ...

    def load_scenario(
        self,
        local_scenario_name: LocalScenario,
        cdf_scenario_name: CDFScenario | None = None,
        modus_operandi: ModusOperandi = "additive",
        include_cdm: bool = False,
        format: Literal["validation-resource", "snapshots"] = "validation-resource",
    ) -> ValidationResources | tuple[SchemaSnapshot, SchemaSnapshot]:
        cdf_scenario_name = cdf_scenario_name or local_scenario_name

        local = self.load_schema_snapshot(LOCAL_SNAPSHOTS_DIR / local_scenario_name)
        cdf = self.load_schema_snapshot(CDF_SNAPSHOTS_DIR / cdf_scenario_name)

        return self.return_desired_format(local, cdf, modus_operandi, include_cdm, format)

    def return_desired_format(
        self,
        local: SchemaSnapshot,
        cdf: SchemaSnapshot,
        modus_operandi: ModusOperandi,
        include_cdm: bool,
        format: Literal["validation-resource", "snapshots"],
    ) -> ValidationResources | tuple[SchemaSnapshot, SchemaSnapshot]:
        if include_cdm:
            cdf.data_model.update(self.cdm_snapshot.data_model)
            cdf.views.update(self.cdm_snapshot.views)
            cdf.containers.update(self.cdm_snapshot.containers)

        if format == "validation-resource":
            return ValidationResources(
                local=local,
                cdf=cdf,
                limits=LIMITS,
                modus_operandi=modus_operandi,
            )
        else:
            return local, cdf

    def load_schema_snapshot(self, path: Path) -> SchemaSnapshot:
        schema = SchemaSnapshot(
            timestamp=now,
            data_model=self.load_data_model(path / "data_model.yaml"),
            views=self.load_views(path / "views.yaml"),
            containers=self.load_containers(path / "containers.yaml"),
            node_types={},
            spaces={},
        )

        return schema

    @cached_property
    def cdm_snapshot(self) -> SchemaSnapshot:
        return self.load_schema_snapshot(CDF_SNAPSHOTS_DIR / "cdm")

    def load_containers(self, path: Path) -> dict[ContainerReference, ContainerRequest]:
        content = yaml.safe_load(path.read_text(encoding=ENCODING)) or []
        return {(container := ContainerRequest.model_validate(item)).as_reference(): container for item in content}

    def load_views(self, path: Path) -> dict[ViewReference, ViewRequest]:
        content = yaml.safe_load(path.read_text(encoding=ENCODING)) or []
        return {(view := ViewRequest.model_validate(item)).as_reference(): view for item in content}

    def load_data_model(self, path: Path) -> dict[DataModelReference, DataModelRequest]:
        return (
            {(dm := DataModelRequest.model_validate(content)).as_reference(): dm}
            if (content := yaml.safe_load(path.read_text(encoding=ENCODING)))
            else {}
        )

    @classmethod
    def snapshot_to_request_schema(cls, snapshot: SchemaSnapshot) -> RequestSchema:
        """This is a helper method for tests that converts a SchemaSnapshot to a RequestSchema"""
        if not snapshot.data_model:
            raise ValueError("Cannot create RequestSchema from a snapshot with no data model.")

        data_model = next(iter(snapshot.data_model.values()))

        return RequestSchema(
            dataModel=data_model,
            views=list(snapshot.views.values()),
            containers=list(snapshot.containers.values()),
            spaces=list(snapshot.spaces.values()),
            node_types=list(snapshot.node_types.values()),
        )

    @classmethod
    def snapshot_to_response_schema(cls, snapshot: SchemaSnapshot) -> dict[str, Any]:
        """This is a helper method for tests that converts a SchemaSnapshot
        to a dict representing the response schema"""

        timestamp = int(snapshot.timestamp.timestamp())

        datamodels = [
            DataModelResponse(
                **dm.model_dump(by_alias=True, exclude_unset=True),
                createdTime=timestamp,
                lastUpdatedTime=timestamp,
                isGlobal=True,
            ).model_dump(by_alias=True, exclude_unset=True)
            for dm in snapshot.data_model.values()
        ]
        containers = [
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
        spaces = [
            SpaceResponse(
                **space.model_dump(by_alias=True, exclude_unset=True),
                createdTime=timestamp,
                lastUpdatedTime=timestamp,
                isGlobal=True,
            ).model_dump(by_alias=True, exclude_unset=True)
            for space in snapshot.spaces.values()
        ]
        views = []

        for view in snapshot.views.values():
            if not view.properties:
                continue

            model_dump = view.model_dump(by_alias=True, exclude_unset=True)
            model_dump["createdTime"] = model_dump["lastUpdatedTime"] = timestamp
            model_dump["isGlobal"] = model_dump["writable"] = model_dump["queryable"] = True
            model_dump["usedFor"] = "all"
            model_dump["mappedContainers"] = view.used_containers

            properties: dict[str, Any] = {}
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
                        type=TextProperty(),
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

        return {"datamodels": datamodels, "containers": containers, "spaces": spaces, "views": views}

    @classmethod
    def snapshot_to_mock_router(
        cls, snapshot: SchemaSnapshot, client: NeatClientConfig, respx_mock: respx.MockRouter
    ) -> respx.MockRouter:
        responses = cls.snapshot_to_response_schema(snapshot)

        for endpoint, resource in [
            ("/models/containers?includeGlobal=true&limit=1000", "containers"),
            (
                "/models/views?allVersions=true&includeInheritedProperties=false&includeGlobal=true&limit=1000",
                "views",
            ),
            ("/models/datamodels?allVersions=true&includeGlobal=true&limit=1000", "datamodels"),
            ("/models/spaces?includeGlobal=true&limit=1000", "spaces"),
        ]:
            respx_mock.get(
                client.create_api_url(endpoint),
            ).respond(
                status_code=200,
                json={
                    "items": responses[resource],
                    "nextCursor": None,
                },
            )

        respx_mock.get(
            client.create_api_url("/models/statistics"),
        ).respond(
            status_code=200,
            json={
                "spaces": {"count": 5, "limit": 100},
                "containers": {"count": 42, "limit": 1000},
                "views": {"count": 123, "limit": 2000},
                "dataModels": {"count": 8, "limit": 500},
                "containerProperties": {"count": 1234, "limit": 100},
                "instances": {
                    "edges": 5000,
                    "softDeletedEdges": 100,
                    "nodes": 10000,
                    "softDeletedNodes": 200,
                    "instances": 15000,
                    "instancesLimit": 5000000,
                    "softDeletedInstances": 300,
                    "softDeletedInstancesLimit": 10000000,
                },
                "concurrentReadLimit": 10,
                "concurrentWriteLimit": 5,
                "concurrentDeleteLimit": 3,
            },
        )

        return respx_mock
