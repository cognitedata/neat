from abc import ABC, abstractmethod
from collections.abc import Iterable, MutableMapping
from typing import Any, TypeVar, cast, final

import pandas as pd
import yaml
from cognite.client.data_classes._base import T_CogniteResource
from cognite.client.data_classes.data_modeling import (
    ContainerApply,
    ContainerId,
    DataModelApply,
    DataModelId,
    DataModelingId,
    NodeApply,
    NodeId,
    SpaceApply,
    VersionedDataModelingId,
    ViewApply,
    ViewId,
)
from cognite.client.data_classes.data_modeling.ids import InstanceId
from cognite.client.utils._auxiliary import load_yaml_or_json
from cognite.client.utils._pandas_helpers import (
    convert_nullable_int_cols,
)

T_ID = TypeVar("T_ID", bound=str | VersionedDataModelingId | DataModelingId | InstanceId)


class CogniteResourceDict(dict, MutableMapping[T_ID, T_CogniteResource], ABC):
    _RESOURCE: type[T_CogniteResource]

    @classmethod
    @abstractmethod
    def _as_id(cls, resource: T_CogniteResource) -> T_ID:
        raise NotImplementedError

    def dump(self, camel_case: bool = True) -> dict:
        return {key: value.dump(camel_case) for key, value in self.items()}

    def dump_yaml(self) -> str:
        return yaml.dump(self.dump(camel_case=True), sort_keys=False)

    def to_pandas(self, camel_case: bool = False) -> pd.DataFrame:
        df = pd.DataFrame(self.dump(camel_case=camel_case).values())
        df = convert_nullable_int_cols(df)
        return df

    @classmethod
    @final
    def load(cls: "type[T_CogniteResourceDict]", resource: Iterable[dict[str, Any]] | str) -> "T_CogniteResourceDict":
        """Load a resource from a YAML/JSON string or iterable of dict."""
        if isinstance(resource, str):
            resource = load_yaml_or_json(resource)

        if isinstance(resource, Iterable):
            return cls._load(cast(Iterable, resource))

        raise TypeError(f"Resource must be json or yaml str, or iterable of dicts, not {type(resource)}")

    @classmethod
    def _load(
        cls: "type[T_CogniteResourceDict]",
        resource_list: Iterable[dict[str, Any]],
    ) -> "T_CogniteResourceDict":
        resources = (cls._RESOURCE._load(resource) for resource in resource_list)
        return cls({cls._as_id(resource): resource for resource in resources})


T_CogniteResourceDict = TypeVar("T_CogniteResourceDict", bound=CogniteResourceDict)


class ViewApplyDict(CogniteResourceDict[ViewId, ViewApply]):
    _RESOURCE = ViewApply

    @classmethod
    def _as_id(cls, resource: ViewApply) -> ViewId:
        return resource.as_id()


class SpaceApplyDict(CogniteResourceDict[str, SpaceApply]):
    _RESOURCE = SpaceApply

    @classmethod
    def _as_id(cls, resource: SpaceApply) -> str:
        return resource.space


class ContainerApplyDict(CogniteResourceDict[ContainerId, ContainerApply]):
    _RESOURCE = ContainerApply

    @classmethod
    def _as_id(cls, resource: ContainerApply) -> ContainerId:
        return resource.as_id()


class DataModelApplyDict(CogniteResourceDict[DataModelId, DataModelApply]):
    _RESOURCE = DataModelApply

    @classmethod
    def _as_id(cls, resource: DataModelApply) -> DataModelId:
        return resource.as_id()


class NodeApplyDict(CogniteResourceDict[NodeId, NodeApply]):
    _RESOURCE = NodeApply

    @classmethod
    def _as_id(cls, resource: NodeApply) -> NodeId:
        return resource.as_id()
