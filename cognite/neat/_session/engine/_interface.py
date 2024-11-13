from collections.abc import Iterable
from typing import Any, Protocol

from rdflib import Literal, URIRef


class Extractor(Protocol):
    def extract(self) -> Iterable[tuple[URIRef, URIRef, Literal | URIRef]]: ...


class ConfigAPI(Protocol):
    source: str | None
    file: Any | None
    type: str | None
    primary_key: str | None


class NeatEngine(Protocol):
    version: str = "1.0.0"

    @property
    def set(self) -> ConfigAPI: ...

    def create_extractor(self) -> Extractor: ...
