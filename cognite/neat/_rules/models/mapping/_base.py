from collections import Counter, defaultdict
from collections.abc import Iterator, MutableSequence, Sequence
from pathlib import Path
from typing import Any, Generic, SupportsIndex, TypeVar, cast, get_args, overload

import pandas as pd
from pydantic import BaseModel, GetCoreSchemaHandler, field_validator
from pydantic_core import core_schema
from pydantic_core.core_schema import ValidationInfo

from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules.models._base_rules import ClassRef, PropertyRef
from cognite.neat._rules.models.entities import ClassEntity, Undefined

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

    @field_validator("properties", "classes", mode="before")
    def as_mapping_list(cls, value: Sequence[Any], info: ValidationInfo) -> Any:
        if isinstance(value, Sequence) and not isinstance(value, MappingList):
            annotation = cast(type, cls.model_fields[info.field_name].annotation)  # type: ignore[index]
            ref_cls = get_args(annotation)[0]
            return annotation([Mapping[ref_cls].model_validate(item) for item in value])  # type: ignore[valid-type, index]
        return value

    @classmethod
    def load_spreadsheet(
        cls, path: str | Path, source_prefix: str | None = None, destination_prefix: str | None = None
    ) -> "RuleMapping":
        """Loads mapping from Excel spreadsheet.

        This method expects four columns in the spreadsheet. The first two columns are the source class and
        property, and the last two columns are the destination class and property. The method will create
        a mapping for each row in the spreadsheet.

        The class mapping will be inferred from the property mappings. If a source class has multiple
        destination classes, the most common destination class will be used.

        Args:
            path: Path to Excel spreadsheet.
            source_prefix: Default prefix for source classes.
            destination_prefix: Default prefix for destination classes.

        Returns:
            Mapping object.

        """
        df = pd.read_excel(path).dropna(axis=1, how="all")
        properties = MappingList[PropertyRef]()
        destination_classes_by_source: dict[ClassEntity, Counter[ClassEntity]] = defaultdict(Counter)
        for _, row in df.iterrows():
            if len(row) < 4:
                raise NeatValueError(f"Row {row} is not valid. Expected 4 columns, got {len(row)}")

            if any(pd.isna(row.iloc[:4])):
                continue
            source_class, source_property, destination_class, destination_property = row.iloc[:4]
            source_entity = ClassEntity.load(source_class, prefix=source_prefix or Undefined)
            destination_entity = ClassEntity.load(destination_class, prefix=destination_prefix or Undefined)
            properties.append(
                Mapping(
                    source=PropertyRef(Class=source_entity, Property=source_property),
                    destination=PropertyRef(Class=destination_entity, Property=destination_property),
                )
            )
            destination_classes_by_source[source_entity][destination_entity] += 1

        classes = MappingList[ClassRef]()
        for source_entity, destination_classes in destination_classes_by_source.items():
            destination_entity = destination_classes.most_common(1)[0][0]
            classes.append(
                Mapping(source=ClassRef(Class=source_entity), destination=ClassRef(Class=destination_entity))
            )

        return cls(properties=properties, classes=classes)
