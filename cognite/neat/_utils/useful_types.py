from collections.abc import Hashable
from datetime import date, datetime, time, timedelta
from typing import TypeAlias, TypeVar

JsonVal: TypeAlias = None | str | int | float | bool | dict[str, "JsonVal"] | list["JsonVal"]
# These are the types that openpyxl supports in cells
CellValue: TypeAlias = str | int | float | bool | datetime | date | time | timedelta | None

T_ID = TypeVar("T_ID", bound=Hashable)
