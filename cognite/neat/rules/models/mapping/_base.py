from collections.abc import Iterator, MutableSequence, Sequence
from pathlib import Path
from typing import Any, Generic, SupportsIndex, TypeVar, get_args, overload

import pandas as pd
from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import core_schema

from cognite.neat.rules.models._base_rules import ClassRef, PropertyRef

T_Mapping = TypeVar("T_Mapping", bound=ClassRef | PropertyRef)


class Mapping(BaseModel, Generic[T_Mapping]):
    source: T_Mapping
    destination: T_Mapping


class MappingList(list, MutableSequence[Mapping[T_Mapping]]):
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        if args := get_args(source):
            item_type = args[0]
        else:
            # Someone use SheetList without specifying the type
            raise TypeError("SheetList must be used with a type argument, e.g., SheetList[InformationProperty]")

        instance_schema = core_schema.is_instance_schema(cls)
        sequence_row_schema = handler.generate_schema(Sequence[item_type])  # type: ignore[valid-type]

        non_instance_schema = core_schema.no_info_after_validator_function(MappingList, sequence_row_schema)
        return core_schema.union_schema([instance_schema, non_instance_schema])

    def as_destination_by_source(self) -> dict[T_Mapping, T_Mapping]:
        return {mapping.source: mapping.destination for mapping in self}

    def to_pandas(self, drop_na_columns: bool = True, include: list[str] | None = None) -> pd.DataFrame:
        """Converts ResourceDict to pandas DataFrame."""
        df = pd.DataFrame([entity.model_dump() for entity in self])
        if drop_na_columns:
            df = df.dropna(axis=1, how="all")
        if include is not None:
            df = df[include]
        return df

    def _repr_html_(self) -> str:
        """Returns HTML representation of ResourceDict."""
        return self.to_pandas(drop_na_columns=True)._repr_html_()  # type: ignore[operator]

    # Implemented to get correct type hints
    def __iter__(self) -> Iterator[Mapping[T_Mapping]]:
        return super().__iter__()

    @overload
    def __getitem__(self, index: SupportsIndex) -> Mapping[T_Mapping]: ...

    @overload
    def __getitem__(self, index: slice) -> "MappingList[T_Mapping]": ...

    def __getitem__(self, index: SupportsIndex | slice, /) -> "Mapping[T_Mapping] | MappingList[T_Mapping]":
        if isinstance(index, slice):
            return MappingList[T_Mapping](super().__getitem__(index))
        return super().__getitem__(index)


class RuleMapping(BaseModel):
    properties: MappingList[PropertyRef]
    classes: MappingList[ClassRef]

    @classmethod
    def load(cls, data: dict[str, Any]) -> "RuleMapping":
        return cls(
            properties=MappingList[PropertyRef](data["properties"]),
            classes=MappingList[ClassRef](data["classes"]),
        )

    @classmethod
    def load_spreadsheet(cls, path: str | Path) -> "RuleMapping":
        raise NotImplementedError()
