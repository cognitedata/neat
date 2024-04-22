"""This module contains the definition of `TransformationRules` pydantic model and all
its sub-models and validators.
"""

from __future__ import annotations

import math
import sys
import types
from abc import abstractmethod
from collections.abc import Callable, Iterator
from functools import wraps
from typing import Annotated, Any, ClassVar, Generic, TypeAlias, TypeVar

import pandas as pd
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    PlainSerializer,
    constr,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo

from cognite.neat.rules.models.rules._types import ClassType

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import Self
else:
    from backports.strenum import StrEnum
    from typing_extensions import Self


METADATA_VALUE_MAX_LENGTH = 5120


def replace_nan_floats_with_default(values: dict, model_fields: dict[str, FieldInfo]) -> dict:
    output = {}
    for field_name, value in values.items():
        is_nan_float = isinstance(value, float) and math.isnan(value)
        if not is_nan_float:
            output[field_name] = value
            continue
        if field_name in model_fields:
            output[field_name] = model_fields[field_name].default
        else:
            # field_name may be an alias
            source_name = next((name for name, field in model_fields.items() if field.alias == field_name), None)
            if source_name:
                output[field_name] = model_fields[source_name].default
            else:
                # Just pass it through if it is not an alias.
                output[field_name] = value
    return output


def skip_field_validator(validators_field):
    def decorator(func):
        @wraps(func)
        def wrapper(cls, value, values):
            if isinstance(values, dict):
                to_skip = values.get(validators_field, set())
            else:
                try:
                    to_skip = values.data.get(validators_field, set())
                except Exception:
                    to_skip = set()

            if "all" in to_skip or func.__name__ in to_skip:
                return value
            return func(cls, value, values)

        return wrapper

    return decorator


def skip_model_validator(validators_field):
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            to_skip = getattr(self, validators_field, set())
            if "all" in to_skip or func.__name__ in to_skip:
                return self

            return func(self)

        return wrapper

    return decorator


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


Space: TypeAlias = str
Description: TypeAlias = constr(min_length=1, max_length=1024)  # type: ignore[valid-type]


class SchemaCompleteness(StrEnum):
    complete = "complete"
    partial = "partial"
    extended = "extended"


class ExtensionCategory(StrEnum):
    addition = "addition"
    reshape = "reshape"
    rebuild = "rebuild"


class RoleTypes(StrEnum):
    domain_expert = "domain expert"
    information_architect = "information architect"
    dms_architect = "DMS Architect"


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


class URL(BaseModel):
    url: HttpUrl


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


class BaseRules(RuleModel):
    """
    Rules is a core concept in `neat`. This represents fusion of data model
    definitions and (optionally) the transformation rules used to transform the data/graph
    from the source representation to the target representation defined by the data model.
    The rules are defined in a Excel sheet and then parsed into a `Rules` object. The
    `Rules` object is then used to generate data model and the`RDF` graph made of data
    model instances.

    Args:
        metadata: Data model metadata
        classes: Classes defined in the data model
        properties: Class properties defined in the data model with accompanying transformation rules
                    to transform data from source to target representation
        prefixes: Prefixes used in the data model. Defaults to PREFIXES
        instances: Instances defined in the data model. Defaults to None
        validators_to_skip: List of validators to skip. Defaults to []
    """

    metadata: BaseMetadata

    @abstractmethod
    def reference_self(self) -> Self:
        """
        Returns a copy of the rules with reference fields set to itself

        For example, if the rules have a property with a reference field, then
        the reference field will be set to the property itself. This is used when
        exporting a reference model.
        """
        raise NotImplementedError


# An sheet entity is either a class or a property.
class SheetEntity(RuleModel):
    class_: ClassType = Field(alias="Class")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)

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
