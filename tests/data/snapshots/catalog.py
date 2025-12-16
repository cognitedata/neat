from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Literal, TypeAlias, overload

import yaml

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._data_model import DataModelRequest
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import ContainerReference, DataModelReference, ViewReference
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._utils.useful_types import ModusOperandi

ROOT = Path(__file__).parent
LOCAL_SNAPSHOTS_DIR = ROOT / "local"
CDF_SNAPSHOTS_DIR = ROOT / "cdf"
ENCODING = "utf-8"
LIMITS = SchemaLimits()

now = datetime.now()

LocalScenario: TypeAlias = Literal["ai_readiness", "bi_directional_connections", "requires_constraints", "uncategorized_validators"]
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
