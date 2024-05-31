from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Generic, Literal, TypeVar, overload

from cognite.client import CogniteClient

from cognite.neat.rules.issues import NeatValidationError
from cognite.neat.graph.models import Triple
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

    def _iterate_class_triples(self, classes: Iterable[str]) -> Iterable[tuple[str, Iterable[Triple]]]:
        """Iterate over all classes and their triples."""
        for class_name in classes:
            try:
                sparql_construct_query = build_construct_query(
                    self.graph_store.graph, class_name, self.rules, properties_optional=True
                )
            except Exception as e:
                # Todo add proper logging/return the error as an object
                # logging.error(f"Failed to build construct query for class {class_name}: {e}")
                continue

            yield class_name, self.graph_store.query_delayed(sparql_construct_query)


class CDFLoader(BaseLoader[T_Output]):
    @abstractmethod
    def load_into_cdf_iterable(self, client: CogniteClient, dry_run: bool = False) -> Iterable:
        raise NotImplementedError

    def load_into_cdf(self, client: CogniteClient, dry_run: bool = False) -> list:
        return list(self.load_into_cdf_iterable(client, dry_run))
