from abc import abstractmethod
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

import pandas as pd

T_ID = TypeVar("T_ID", bound=Hashable)


@dataclass
class NeatObject:
    """A neat object can be dumped to a dictionary."""

    @abstractmethod
    def dump(self, aggregate: bool = True) -> dict[str, Any]:
        """Return a dictionary representation of the object."""
        raise NotImplementedError()

    def _repr_html_(self) -> str:
        return pd.Series(self.dump(aggregate=True)).to_frame(name="value")._repr_html_()


@dataclass(frozen=True)
class FrozenNeatObject:
    """A frozen neat object can be dumped to a dictionary."""

    @abstractmethod
    def dump(self, aggregate: bool = True) -> dict[str, Any]:
        """Return a dictionary representation of the object."""
        raise NotImplementedError()

    def _repr_html_(self) -> str:
        return pd.Series(self.dump(aggregate=True)).to_frame(name="value")._repr_html_()


T_NeatObject = TypeVar("T_NeatObject", bound=NeatObject | FrozenNeatObject)


class NeatList(list, Sequence[T_NeatObject]):
    """A list of neat objects."""

    def dump(self) -> list[dict[str, Any]]:
        """Return a list of dictionary representations of the objects."""
        return [obj.dump() for obj in self]

    def to_pandas(self) -> pd.DataFrame:
        return pd.DataFrame(self.dump())

    def _repr_html_(self) -> str:
        return self.to_pandas()._repr_html_()  # type: ignore[operator]
