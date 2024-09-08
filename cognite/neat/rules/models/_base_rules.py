"""This module contains the definition of `TransformationRules` pydantic model and all
its sub-models and validators.
"""

from __future__ import annotations

import sys
import types
from abc import ABC, abstractmethod
from collections.abc import Callable, Hashable, Iterator, MutableSequence, Sequence
from typing import Annotated, Any, ClassVar, Literal, SupportsIndex, TypeVar, get_args, get_origin, overload

import pandas as pd
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    PlainSerializer,
    field_validator,
    model_serializer,
)
from pydantic.main import IncEx
from pydantic_core import core_schema

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import Self
else:
    from backports.strenum import StrEnum
    from typing_extensions import Self


METADATA_VALUE_MAX_LENGTH = 5120


def _get_required_fields(model: type[BaseModel], use_alias: bool = False) -> set[str]:
    """Get required fields from a pydantic model.

    Parameters
    ----------
    model : type[BaseModel]
        Pydantic data model
    use_alias : bool, optional
        Whether to return field alias name, by default False

    Returns
    -------
    list[str]
        List of required fields
    """
    required_fields = set()
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue

        alias = getattr(field, "alias", None)
        if use_alias and alias:
            required_fields.add(alias)
        else:
            required_fields.add(name)
    return required_fields


class SchemaCompleteness(StrEnum):
    complete = "complete"
    partial = "partial"
    extended = "extended"


class ExtensionCategory(StrEnum):
    addition = "addition"
    reshape = "reshape"
    rebuild = "rebuild"


class DataModelType(StrEnum):
    solution = "solution"
    enterprise = "enterprise"


class RoleTypes(StrEnum):
    domain_expert = "domain expert"
    information = "information architect"
    asset = "asset architect"
    dms = "DMS Architect"


class MatchType(StrEnum):
    exact = "exact"
    partial = "partial"


class NeatModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
        strict=False,
        extra="ignore",
        use_enum_values=True,
    )
    validators_to_skip: set[str] = Field(default_factory=set, exclude=True)

    @classmethod
    def mandatory_fields(cls, use_alias=False) -> set[str]:
        """Returns a set of mandatory fields for the model."""
        return _get_required_fields(cls, use_alias)


class BaseMetadata(NeatModel):
    """
    Metadata model for data model
    """

    role: ClassVar[RoleTypes]

    def to_pandas(self) -> pd.Series:
        """Converts Metadata to pandas Series."""
        return pd.Series(self.model_dump())

    def _repr_html_(self) -> str:
        """Returns HTML representation of Metadata."""
        return self.to_pandas().to_frame("value")._repr_html_()  # type: ignore[operator]

    @classmethod
    def mandatory_fields(cls, use_alias=False) -> set[str]:
        """Returns a set of mandatory fields for the model."""
        return _get_required_fields(cls, use_alias)

    @model_serializer(mode="wrap")
    def include_role(self, serializer: Callable) -> dict:
        return {"role": self.role.value, **serializer(self)}

    @abstractmethod
    def as_identifier(self) -> str:
        """Returns a unique identifier for the metadata."""
        raise NotImplementedError()

    @abstractmethod
    def get_prefix(self) -> str:
        """Returns the prefix for the metadata."""
        raise NotImplementedError()


class BaseRules(NeatModel, ABC):
    """
    Rules is a core concept in `neat`. This represents fusion of data model
    definitions and (optionally) the transformation rules used to transform the data/graph
    from the source representation to the target representation defined by the data model.
    The rules are defined in an Excel sheet and then parsed into a `Rules` object. The
    `Rules` object is then used to generate data model and the `RDF` graph made of data
    model instances.

    Args:
        metadata: Data model metadata
        validators_to_skip: List of validators to skip. Defaults to []
    """

    metadata: BaseMetadata
    reference: Self | None = Field(None, alias="Reference")

    @classmethod
    def headers_by_sheet(cls, by_alias: bool = False) -> dict[str, list[str]]:
        """Returns a list of headers for the model."""
        headers_by_sheet: dict[str, list[str]] = {}
        for field_name, field in cls.model_fields.items():
            if field_name == "validators_to_skip":
                continue
            sheet_name = (field.alias or field_name) if by_alias else field_name
            annotation = field.annotation

            if isinstance(annotation, types.UnionType):
                annotation = annotation.__args__[0]

            try:
                if isinstance(annotation, types.GenericAlias) and get_origin(annotation) is SheetList:
                    # We know that this is a SheetList, so we can safely access the annotation
                    # which is the concrete type of the SheetEntity.
                    model_fields = get_args(annotation)[0].model_fields  # type: ignore[union-attr]
                elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
                    model_fields = annotation.model_fields
                else:
                    model_fields = {}
            except TypeError:
                # Python 3.10 raises TypeError: issubclass() arg 1 must be a class
                # when calling issubclass(annotation, SheetList) with the dict annotation
                model_fields = {}
            headers_by_sheet[sheet_name] = [
                (field.alias or field_name) if by_alias else field_name
                for field_name, field in model_fields.items()
                if field_name != "validators_to_skip" and not field.exclude
            ]
        return headers_by_sheet

    def dump(
        self,
        mode: Literal["python", "json"] = "python",
        by_alias: bool = False,
        exclude: IncEx = None,
        exclude_none: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        as_reference: bool = False,
        entities_exclude_defaults: bool = True,
    ) -> dict[str, Any]:
        """Dump the model to a dictionary.

        This is used in the Exporters to dump rules in the required format.
        """
        for field_name in self.model_fields.keys():
            value = getattr(self, field_name)
            # Ensure deterministic order of properties
            if isinstance(value, SheetList):
                value.sort(key=lambda x: x._identifier())

        context: dict[str, Any] = {"as_reference": as_reference}
        if entities_exclude_defaults:
            context["metadata"] = self.metadata

        if self.reference is not None:
            exclude_input: IncEx
            if isinstance(exclude, dict):
                exclude_input = exclude.copy()
                exclude_input["reference"] = {"__all__"}  # type: ignore[index]
            elif isinstance(exclude, set):
                exclude_input = exclude.copy()
                exclude_input.add("reference")  # type: ignore[arg-type]
            else:
                exclude_input = {"reference"}
        else:
            exclude_input = exclude

        output = self.model_dump(
            mode=mode,
            by_alias=by_alias,
            exclude=exclude_input,
            exclude_none=exclude_none,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            context=context,
        )
        if self.reference is not None and not (isinstance(exclude, dict | set) and "reference" in exclude):
            output["Reference" if by_alias else "reference"] = self.reference.dump(
                mode=mode,
                by_alias=by_alias,
                exclude=exclude,
                exclude_none=exclude_none,
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                entities_exclude_defaults=entities_exclude_defaults,
                as_reference=True,
            )
        return output


class SheetRow(NeatModel):
    @field_validator("*", mode="before")
    def strip_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @abstractmethod
    def _identifier(self) -> tuple[Hashable, ...]:
        raise NotImplementedError()


T_SheetRow = TypeVar("T_SheetRow", bound=SheetRow)


class SheetList(list, MutableSequence[T_SheetRow]):
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        if args := get_args(source):
            item_type = args[0]
        else:
            # Someone use SheetList without specifying the type
            raise TypeError("SheetList must be used with a type argument, e.g., SheetList[InformationProperty]")

        instance_schema = core_schema.is_instance_schema(cls)
        sequence_row_schema = handler.generate_schema(Sequence[item_type])  # type: ignore[valid-type]

        non_instance_schema = core_schema.no_info_after_validator_function(SheetList, sequence_row_schema)
        return core_schema.union_schema([instance_schema, non_instance_schema])

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
    def __iter__(self) -> Iterator[T_SheetRow]:
        return super().__iter__()

    @overload
    def __getitem__(self, index: SupportsIndex) -> T_SheetRow: ...

    @overload
    def __getitem__(self, index: slice) -> SheetList[T_SheetRow]: ...

    def __getitem__(self, index: SupportsIndex | slice, /) -> T_SheetRow | SheetList[T_SheetRow]:
        if isinstance(index, slice):
            return SheetList[T_SheetRow](super().__getitem__(index))
        return super().__getitem__(index)


ExtensionCategoryType = Annotated[
    ExtensionCategory,
    PlainSerializer(
        lambda v: v.value if isinstance(v, ExtensionCategory) else v,
        return_type=str,
        when_used="unless-none",
    ),
    BeforeValidator(lambda v: ExtensionCategory(v) if isinstance(v, str) else v),
]
