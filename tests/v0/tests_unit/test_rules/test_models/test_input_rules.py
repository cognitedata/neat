from collections.abc import Iterable
from dataclasses import fields, is_dataclass
from types import GenericAlias, UnionType
from typing import Union, get_args, get_origin

import pytest
from _pytest.mark import ParameterSet
from pydantic import BaseModel
from rdflib import URIRef

from cognite.neat.v0.core._data_model.models import SheetList
from cognite.neat.v0.core._data_model.models._base_unverified import UnverifiedDataModel
from tests.v0.utils import DataClassCreator, get_all_subclasses


def input_rules_instances_iterator() -> Iterable[ParameterSet]:
    for cls_ in get_all_subclasses(UnverifiedDataModel, only_concrete=True):
        yield pytest.param(DataClassCreator(cls_).create_instance(), id=cls_.__name__)


def input_rules_cls_iterator() -> Iterable[ParameterSet]:
    for cls_ in get_all_subclasses(UnverifiedDataModel, only_concrete=True):
        yield pytest.param(cls_, id=cls_.__name__)


class TestInputRules:
    @pytest.mark.parametrize("input_rules_cls", input_rules_cls_iterator())
    def test_input_rules_match_verified_cls(self, input_rules_cls: type[UnverifiedDataModel]) -> None:
        """Test that all classes that inherit from InputRules have a matching verified class."""
        verified_cls = input_rules_cls._get_verified_cls()
        input_parameters = dataclass_to_parameters(input_rules_cls)
        verified_parameters = pydantic_to_parameters(verified_cls)

        assert input_parameters == verified_parameters, f"Parameters mismatch for {input_rules_cls.__name__}"

    @pytest.mark.parametrize("input_rules", input_rules_instances_iterator())
    def test_issues_dump_load(self, input_rules: UnverifiedDataModel) -> None:
        """Test that all classes that inherit from InputRules can be dumped and loaded."""
        dumped = input_rules.dump()
        assert isinstance(dumped, dict)
        assert dumped != {}, f"Empty dump for {type(input_rules).__name__}"
        loaded = type(input_rules).load(dumped)
        # In the dump methods, default prefix/space/version are set, so the reloaded object will not match.
        # However, the metadata should match.
        assert input_rules.metadata == loaded.metadata, f"Dump and load mismatch for {type(input_rules).__name__}"


def dataclass_to_parameters(
    input_rules_cls: type[UnverifiedDataModel],
) -> dict[str, set[str]]:
    output: dict[str, set[str]] = {}
    for field_ in fields(input_rules_cls):
        type_ = field_.type
        if isinstance(type_, UnionType) or get_origin(type_) is Union:
            type_ = get_args(type_)[0]

            if type_ is str:
                output[field_.name] = ""
                continue
        if isinstance(type_, str) and type_.startswith(input_rules_cls.__name__):
            type_ = input_rules_cls

        if is_dataclass(type_):
            output[field_.name] = {subfield.name for subfield in fields(type_)}
            continue
        elif isinstance(type_, GenericAlias):
            origin = type_.__origin__
            if origin is list and is_dataclass(type_.__args__[0]):
                output[field_.name] = {subfield.name for subfield in fields(type_.__args__[0])}
                continue
            elif origin is dict:
                output[field_.name] = set()
                continue
        raise TypeError(f"Unsupported type {type_} for {field_.name}")
    return output


def pydantic_to_parameters(verified_cls: type[BaseModel]) -> dict[str, set[str]]:
    output: dict[str, set[str]] = {}
    for name, field_ in verified_cls.model_fields.items():
        if name in ["validators_to_skip", "post_validate"]:
            continue

        type_ = field_.annotation

        if URIRef in get_args(type_):
            output[name] = ""
            continue

        if isinstance(type_, UnionType) or get_origin(type_) is Union:
            type_ = get_args(type_)[0]

        if isinstance(type_, GenericAlias) and type_.__origin__ is dict:
            output[name] = set()
            continue

        if isinstance(type_, GenericAlias) and type_.__origin__ is SheetList:
            type_ = get_args(type_)[0]

        if issubclass(type_, BaseModel):
            output[name] = {k for k in type_.model_fields.keys() if k != "validators_to_skip"}
        else:
            raise TypeError(f"Unsupported type {type_} for {name}")
    return output
