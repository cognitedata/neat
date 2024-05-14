from abc import ABC, abstractmethod
from collections.abc import (
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    Mapping,
    MutableMapping,
    ValuesView,
)
from typing import Any, TypeVar, cast, final

import pandas as pd
import yaml
from cognite.client.data_classes._base import T_CogniteResource
from cognite.client.data_classes.data_modeling import (
    ContainerApply,
    ContainerId,
    DataModelApply,
    DataModelId,
    NodeApply,
    NodeId,
    SpaceApply,
    ViewApply,
    ViewId,
)
from cognite.client.utils._auxiliary import load_yaml_or_json
from cognite.client.utils._pandas_helpers import (
    convert_nullable_int_cols,
)

T_ID = TypeVar("T_ID")


# Inheriting from dict as we are extending it,
# ref https://stackoverflow.com/questions/7148419/subclass-dict-userdict-dict-or-abc
class CogniteResourceDict(dict, MutableMapping[T_ID, T_CogniteResource], ABC):
    """CogniteResource stored in a mapping structure.

    The serialization format of the CognitiveResourceDict is a list of dicts, where each dict
    represents a CognitiveResource.

    This means that the serialization methods .dump() and .load() return a list of dicts and
    expects a list of dicts respectively.

    In addition, the init method is slightly abused compared to a regular dict by allowing the input to be a
    list of CognitiveResources.
    """

    _RESOURCE: type[T_CogniteResource]

    def __init__(
        self,
        items: Iterable[T_CogniteResource]
        | Iterable[tuple[T_ID, T_CogniteResource]]
        | Mapping[T_ID, T_CogniteResource]
        | None = None,
    ) -> None:
        if isinstance(items, Mapping):
            super().__init__(items)
        elif isinstance(items, Iterable):
            super().__init__(item if isinstance(item, tuple) else (self._as_id(item), item) for item in items)  # type: ignore[arg-type]
        else:
            super().__init__()

    @classmethod
    @abstractmethod
    def _as_id(cls, resource: T_CogniteResource) -> T_ID:
        raise NotImplementedError

    def dump(self, camel_case: bool = True) -> list[dict[str, Any]]:
        return [value.dump(camel_case) for value in self.values()]

    def dump_yaml(self) -> str:
        return yaml.dump(self.dump(camel_case=True), sort_keys=False)

    def to_pandas(self, camel_case: bool = False) -> pd.DataFrame:
        df = pd.DataFrame(self.dump(camel_case=camel_case))
        df = convert_nullable_int_cols(df)
        return df

    def _repr_html_(self) -> str:
        # Pretty print the dataframe in Jupyter
        return self.to_pandas()._repr_html_()  # type: ignore[operator]

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
        return cls({cls._as_id(resource): resource for resource in resources})  # type: ignore[abstract]

    # The below methods are included to make better type hints in the IDE
    def __getitem__(self, k: T_ID) -> T_CogniteResource:
        return super().__getitem__(k)

    def __setitem__(self, k: T_ID, v: T_CogniteResource) -> None:
        super().__setitem__(k, v)

    def __delitem__(self, k: T_ID) -> None:
        super().__delitem__(k)

    def __iter__(self) -> Iterator[T_ID]:
        return super().__iter__()

    def keys(self) -> KeysView[T_ID]:  # type: ignore[override]
        return super().keys()

    def values(self) -> ValuesView[T_CogniteResource]:  # type: ignore[override]
        return super().values()

    def items(self) -> ItemsView[T_ID, T_CogniteResource]:  # type: ignore[override]
        return super().items()

    def get(self, __key: T_ID, __default: Any = ...) -> T_CogniteResource:
        return super().get(__key, __default)

    def pop(self, __key: T_ID, __default: Any = ...) -> T_CogniteResource:
        return super().pop(__key, __default)

    def popitem(self) -> tuple[T_ID, T_CogniteResource]:
        return super().popitem()

    def copy(self) -> "CogniteResourceDict[T_ID, T_CogniteResource]":
        return cast(CogniteResourceDict[T_ID, T_CogniteResource], super().copy())


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
