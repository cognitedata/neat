import dataclasses
import datetime
from abc import ABC
from dataclasses import fields
from pathlib import Path
from types import GenericAlias, UnionType
from typing import Any, Literal, TypeVar, Union, get_args, get_origin

from cognite.client.data_classes.data_modeling import ContainerId, ViewId
from rdflib import Namespace


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
