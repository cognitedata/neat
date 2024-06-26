from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

import pandas as pd


@dataclass
class NeatObject:
    """A neat object can be dumped to a dictionary."""

    @abstractmethod
    def dump(self) -> dict[str, Any]:
        """Return a dictionary representation of the object."""
        raise NotImplementedError()


T_NeatObject = TypeVar("T_NeatObject", bound=NeatObject)


class NeatList(list, Sequence[T_NeatObject]):
    """A list of neat objects."""

    def dump(self) -> list[dict[str, Any]]:
        """Return a list of dictionary representations of the objects."""
        return [obj.dump() for obj in self]

    def to_pandas(self) -> pd.DataFrame:
        return pd.DataFrame(self.dump())

    def _repr_html_(self) -> str:
        return self.to_pandas()._repr_html_()  # type: ignore[operator]
