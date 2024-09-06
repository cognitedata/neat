"""This module contains the definition of `TransformationRules` pydantic model and all
its sub-models and validators.
"""

from __future__ import annotations

import sys
import types
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from typing import Annotated, Any, ClassVar, Generic, Literal, TypeVar

import pandas as pd
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.main import IncEx

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum


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


class RuleModel(BaseModel):
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

    @classmethod
    def sheets(cls, by_alias: bool = False) -> list[str]:
        """Returns a list of sheet names for the model."""
        return [
            (field.alias or field_name) if by_alias else field_name
            for field_name, field in cls.model_fields.items()
            if field_name != "validators_to_skip"
        ]

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
                if isinstance(annotation, type) and issubclass(annotation, SheetList):
                    # We know that this is a SheetList, so we can safely access the annotation
                    # which is the concrete type of the SheetEntity.
                    model_fields = annotation.model_fields["data"].annotation.__args__[0].model_fields  # type: ignore[union-attr]
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
                if field_name != "validators_to_skip"
            ]
        return headers_by_sheet


class BaseMetadata(RuleModel):
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


class BaseRules(RuleModel, ABC):
    """
    Rules is a core concept in `neat`. This represents fusion of data model
    definitions and (optionally) the transformation rules used to transform the data/graph
    from the source representation to the target representation defined by the data model.
    The rules are defined in a Excel sheet and then parsed into a `Rules` object. The
    `Rules` object is then used to generate data model and the`RDF` graph made of data
    model instances.

    Args:
        metadata: Data model metadata
        validators_to_skip: List of validators to skip. Defaults to []
    """

    metadata: BaseMetadata

    def dump(
        self,
        mode: Literal["python", "json"] = "python",
        by_alias: bool = False,
        exclude: IncEx = None,
        exclude_none: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        as_reference: bool = False,
    ) -> dict[str, Any]:
        """Dump the model to a dictionary.

        This is used in the Exporters to dump rules in the required format.
        """
        return self.model_dump(
            mode=mode,
            by_alias=by_alias,
            exclude=exclude,
            exclude_none=exclude_none,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
        )


# An sheet entity is either a class or a property.
class SheetEntity(RuleModel):
    @field_validator("*", mode="before")
    def strip_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


T_Entity = TypeVar("T_Entity", bound=SheetEntity)


class SheetList(BaseModel, Generic[T_Entity]):
    data: list[T_Entity] = Field(default_factory=list)

    @model_validator(mode="before")
    def from_list_format(cls, values: Any) -> Any:
        if isinstance(values, list):
            return {"data": values}
        return values

    def __contains__(self, item: str) -> bool:
        return item in self.data

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[T_Entity]:  # type: ignore[override]
        return iter(self.data)

    def append(self, value: T_Entity) -> None:
        self.data.append(value)

    def extend(self, values: list[T_Entity]) -> None:
        self.data.extend(values)

    def to_pandas(self, drop_na_columns: bool = True, include: list[str] | None = None) -> pd.DataFrame:
        """Converts ResourceDict to pandas DataFrame."""
        df = pd.DataFrame([entity.model_dump() for entity in self.data])
        if drop_na_columns:
            df = df.dropna(axis=1, how="all")
        if include is not None:
            df = df[include]
        return df

    def _repr_html_(self) -> str:
        """Returns HTML representation of ResourceDict."""
        return self.to_pandas(drop_na_columns=True)._repr_html_()  # type: ignore[operator]

    @classmethod
    def mandatory_fields(cls, use_alias=False) -> set[str]:
        """Returns a set of mandatory fields for the model."""
        return _get_required_fields(cls, use_alias)


ExtensionCategoryType = Annotated[
    ExtensionCategory,
    PlainSerializer(
        lambda v: v.value if isinstance(v, ExtensionCategory) else v,
        return_type=str,
        when_used="unless-none",
    ),
    BeforeValidator(lambda v: ExtensionCategory(v) if isinstance(v, str) else v),
]
