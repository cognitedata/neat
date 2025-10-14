from collections.abc import Hashable
from datetime import date, datetime, time, timedelta
from typing import TypeAlias, TypeVar

JsonVal: TypeAlias = None | str | int | float | bool | dict[str, "JsonVal"] | list["JsonVal"]


T_ID = TypeVar("T_ID", bound=Hashable)

# These are the types that openpyxl supports in cells
CellValueType: TypeAlias = str | int | float | bool | datetime | date | time | timedelta | None

# The format expected for excel sheets representing a data model
DataModelTableType: TypeAlias = dict[str, list[dict[str, CellValueType]]]
