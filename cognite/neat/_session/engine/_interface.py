from collections.abc import Iterable
from typing import Any, ClassVar, Protocol

from rdflib import Literal, URIRef


class Extractor(Protocol):
    def extract(self) -> Iterable[tuple[URIRef, URIRef, Literal | URIRef]]: ...


class SetterAPI(Protocol):
    def file(self, io: Any) -> None: ...

    def type(self, type: str) -> None: ...

    def primary_key(self, key: str) -> None: ...


class NeatEngine(Protocol):
    version: ClassVar[str] = "0.1.0"

    @property
    def set(self) -> SetterAPI: ...

    def create_extractor(self) -> Extractor: ...
