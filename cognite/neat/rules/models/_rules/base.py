"""This module contains the definition of `TransformationRules` pydantic model and all
its sub-models and validators.
"""

from __future__ import annotations

import math
import sys
from collections.abc import Iterator
from functools import wraps
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, constr, model_validator
from pydantic.fields import FieldInfo

from cognite.neat.rules.models._rules._types import ClassType

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum


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


# An sheet entity is either a class or a property.
class SheetEntity(RuleModel):
    class_: ClassType = Field(alias="Class")
    name: str | None = Field(alias="Name", default=None)
    description: str | None = Field(alias="Description", default=None)


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
