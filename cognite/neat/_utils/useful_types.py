from collections.abc import Hashable
from datetime import date, datetime, time, timedelta
from typing import Literal, TypeAlias, TypeVar

from pydantic import BaseModel
from pydantic.alias_generators import to_camel

JsonVal: TypeAlias = None | str | int | float | bool | dict[str, "JsonVal"] | list["JsonVal"]
PrimaryTypes: TypeAlias = str | int | float | bool

T_ID = TypeVar("T_ID", bound=Hashable)
# These are the types that openpyxl supports in cells
CellValueType: TypeAlias = str | int | float | bool | datetime | date | time | timedelta | None

# The format expected for excel sheets representing a data model
DataModelTableType: TypeAlias = dict[str, list[dict[str, CellValueType]]]
PrimitiveType: TypeAlias = str | int | float | bool


class BaseModelObject(BaseModel, alias_generator=to_camel, extra="ignore"):
    """Base class for all object. This includes resources and nested objects."""

    ...


T_Item = TypeVar("T_Item", bound=BaseModelObject)


class ReferenceObject(BaseModelObject, frozen=True, populate_by_name=True):
    """Base class for all reference objects - these are identifiers."""

    ...


T_Reference = TypeVar("T_Reference", bound=ReferenceObject, covariant=True)

ModusOperandi: TypeAlias = Literal["rebuild", "additive"]
