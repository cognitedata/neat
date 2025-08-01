from collections.abc import Hashable, ItemsView, Iterator, KeysView, Mapping, ValuesView
from typing import TypeVar

from cognite.neat.core._utils.spreadsheet import SpreadsheetRead

T_Key = TypeVar("T_Key", bound=Hashable)
T_Value = TypeVar("T_Value")


class ImportContext(dict, Mapping[T_Key, T_Value]):
    # The below methods are included to make better type hints in the IDE
    def __getitem__(self, k: T_Key) -> T_Value:
        return super().__getitem__(k)

    def __setitem__(self, k: T_Key, v: T_Value) -> None:
        super().__setitem__(k, v)

    def __delitem__(self, k: T_Key) -> None:
        super().__delitem__(k)

    def __iter__(self) -> Iterator[T_Key]:
        return super().__iter__()

    def keys(self) -> KeysView[T_Key]:  # type: ignore[override]
        return super().keys()

    def values(self) -> ValuesView[T_Value]:  # type: ignore[override]
        return super().values()

    def items(self) -> ItemsView[T_Key, T_Value]:  # type: ignore[override]
        return super().items()

    def get(self, __key: T_Key, __default: T_Value = ...) -> T_Value:  # type: ignore[override, assignment]
        return super().get(__key, __default)

    def pop(self, __key: T_Key, __default: T_Value = ...) -> T_Value:  # type: ignore[override, assignment]
        return super().pop(__key, __default)

    def popitem(self) -> tuple[T_Key, T_Value]:
        return super().popitem()


class SpreadsheetContext(ImportContext[str, SpreadsheetRead]):
    def __init__(self, data: dict[str, SpreadsheetRead] | None = None) -> None:
        """Initialize the SpreadsheetContext with a dictionary of SpreadsheetRead objects.

        Args:
            data (dict[str, SpreadsheetRead]): A dictionary where keys are sheet names and values are
                SpreadsheetRead objects containing the read data.
        """
        super().__init__(data or {})
        for k, v in self.items():
            if not isinstance(k, str):
                raise TypeError(f"Expected string key, got {type(k).__name__}")
            if not isinstance(v, SpreadsheetRead):
                raise TypeError(f"Expected SpreadsheetRead for key '{k}', got {type(v).__name__}")
