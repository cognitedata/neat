from collections.abc import Hashable
from typing import TypeAlias, TypeVar

JsonVal: TypeAlias = None | str | int | float | bool | dict[str, "JsonVal"] | list["JsonVal"]


T_ID = TypeVar("T_ID", bound=Hashable)
