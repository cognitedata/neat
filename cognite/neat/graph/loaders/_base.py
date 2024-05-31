from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Generic, Literal, TypeVar, overload

from cognite.client import CogniteClient

from cognite.neat.rules.issues import NeatValidationError

T_Output = TypeVar("T_Output")


class BaseLoader(ABC, Generic[T_Output]):
    _new_line = "\n"
    _encoding = "utf-8"

    @abstractmethod
    def write_to_file(self, filepath: Path) -> None:
        raise NotImplementedError

    @overload
    def load(self, stop_on_exception: Literal[True]) -> Iterable[T_Output]: ...

    @overload
    def load(self, stop_on_exception: Literal[False] = False) -> Iterable[T_Output | NeatValidationError]: ...

    def load(self, stop_on_exception: bool = False) -> Iterable[T_Output | NeatValidationError]:
        """Load the graph with data."""
        return self._load(stop_on_exception)

    # Private to avoid creating overload in all subclasses
    @abstractmethod
    def _load(self, stop_on_exception: bool = False) -> Iterable[T_Output | NeatValidationError]:
        """Load the graph with data."""
        pass


class CDFLoader(BaseLoader[T_Output]):
    @abstractmethod
    def load_into_cdf_iterable(self, client: CogniteClient, dry_run: bool = False) -> Iterable:
        raise NotImplementedError

    def load_into_cdf(self, client: CogniteClient, dry_run: bool = False) -> list:
        return list(self.load_into_cdf_iterable(client, dry_run))
