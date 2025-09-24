import dataclasses
import datetime
from abc import ABC
from collections.abc import Sequence
from dataclasses import fields
from pathlib import Path
from types import GenericAlias, UnionType
from typing import Any, Literal, TypeVar, Union, get_args, get_origin

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import ContainerId, DataModelId, ViewId
from cognite.client.data_classes.data_modeling.instances import Instance, Properties
from rdflib import Namespace

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._data_model._shared import (
    ConceptualDataModel,
    PhysicalDataModel,
    VerifiedDataModel,
)
from cognite.neat.v0.core._data_model.models.data_types import DataType, String
from cognite.neat.v0.core._data_model.models.entities import ConceptEntity


class DataClassCreator:
    def __init__(self, data_cls: type) -> None:
        self.data_cls = data_cls

    def create_instance(self) -> object:
        """Create an instance of the dataclass."""
        kwargs = {field.name: self._create_value(field.type) for field in fields(self.data_cls)}
        return self.data_cls(**kwargs)

    def _create_value(self, type_: type) -> Any:
        if isinstance(type_, str) and type_.startswith(self.data_cls.__name__):
            return None
        elif type_ is str or isinstance(type_, str):
            return "string"
        elif type_ is Any:
            return "any"
        elif type_ is int:
            return 1
        elif type_ is float:
            return 1.0
        elif type_ is bool:
            return True
        elif type_ is Path:
            return Path("path")
        elif type_ is Namespace:
            return Namespace("http://purl.org/cognite/neat/issue#")
        elif type_ == list[tuple[str, str]]:
            return [("Class", "Property")]
        elif isinstance(type_, GenericAlias):
            return self._create_values(type_)
        elif isinstance(type_, UnionType) or get_origin(type_) is Union:
            args = get_args(type_)
            return self._create_value(args[0])
        elif type(type_) is TypeVar or any(type(arg) is TypeVar for arg in get_args(type_)):
            return "typevar"
        elif type_ is ViewId:
            return ViewId("namespace", "class", "version")
        elif type_ is DataModelId:
            return DataModelId("space", "externalId", "version")
        elif type_ is ContainerId:
            return ContainerId("namespace", "class")
        elif get_origin(type_) is Literal:
            args = get_args(type_)
            return args[0]
        elif dataclasses.is_dataclass(type_):
            return DataClassCreator(type_).create_instance()
        elif type_ is datetime.datetime:
            return datetime.datetime.now()
        elif type_ is datetime.date:
            return datetime.date.today()
        elif type_ is ConceptEntity:
            return ConceptEntity(prefix="namespace", suffix="class", version="version")
        elif type_ is DataType:
            return String()
        else:
            raise NotImplementedError(f"Type {type_} not implemented.")

    def _create_values(self, field_type: GenericAlias) -> Any:
        origin = field_type.__origin__
        if origin is list:
            return [self._create_value(field_type.__args__[0])]
        elif origin is dict:
            return {self._create_value(field_type.__args__[0]): self._create_value(field_type.__args__[1])}
        elif origin is tuple:
            return (self._create_value(field_type.__args__[0]),)
        elif origin is set:
            return {self._create_value(field_type.__args__[0])}
        elif origin is frozenset:
            return frozenset({self._create_value(field_type.__args__[0])})
        elif origin is type and issubclass(field_type.__args__[0], Warning):
            return UserWarning
        else:
            raise NotImplementedError(f"Field type {field_type} not implemented.")


T_Type = TypeVar("T_Type", bound=type)


def get_all_subclasses(cls: T_Type, only_concrete: bool = False) -> list[T_Type]:
    """Get all subclasses of a class."""
    return [s for s in cls.__subclasses__() if only_concrete is False or ABC not in s.__bases__] + [
        g for s in cls.__subclasses__() for g in get_all_subclasses(s, only_concrete)
    ]


def normalize_neat_id_in_rules(rules: VerifiedDataModel) -> VerifiedDataModel:
    if isinstance(rules, ConceptualDataModel):
        for i, class_ in enumerate(rules.concepts):
            class_.neatId = DEFAULT_NAMESPACE[f"Class_{i}"]
        for i, property_ in enumerate(rules.properties):
            property_.neatId = DEFAULT_NAMESPACE[f"Property_{i}"]

    elif isinstance(rules, PhysicalDataModel):
        for i, view in enumerate(rules.views):
            view.neatId = DEFAULT_NAMESPACE[f"View_{i}"]
        for i, property_ in enumerate(rules.properties):
            property_.neatId = DEFAULT_NAMESPACE[f"Property_{i}"]

        if rules.containers:
            for i, container in enumerate(rules.containers):
                container.neatId = DEFAULT_NAMESPACE[f"Container_{i}"]

        if rules.enum:
            for i, enum in enumerate(rules.enum):
                enum.neatId = DEFAULT_NAMESPACE[f"Enum_{i}"]
        if rules.nodes:
            for i, node in enumerate(rules.nodes):
                node.neatId = DEFAULT_NAMESPACE[f"NodeType_{i}"]


def as_read_instance(instance: dm.NodeApply | dm.EdgeApply) -> Instance:
    args = dict(
        space=instance.space,
        external_id=instance.external_id,
        type=instance.type,
        last_updated_time=0,
        created_time=0,
        version=instance.existing_version,
        deleted_time=None,
        properties=Properties(
            {source.source: source.properties for source in instance.sources or []},
        ),
    )
    if isinstance(instance, dm.NodeApply):
        return dm.Node(**args)
    else:
        return dm.Edge(
            start_node=instance.start_node,
            end_node=instance.end_node,
            **args,
        )


def as_read_containers(containers: Sequence[dm.ContainerApply]) -> dm.ContainerList:
    return dm.ContainerList(
        [
            dm.Container(
                space=c.space,
                external_id=c.external_id,
                properties=c.properties,
                is_global=c.space.startswith("cdf"),
                last_updated_time=0,
                created_time=0,
                description=c.description,
                name=c.name,
                used_for=c.used_for or "all",
                constraints=c.constraints,
                indexes=c.indexes,
            )
            for c in containers
        ]
    )


def as_read_space(space: dm.SpaceApply) -> dm.Space:
    return dm.Space(
        space=space.space,
        last_updated_time=0,
        created_time=0,
        description=space.description,
        name=space.name,
        is_global=space.space.startswith("cdf"),
    )
