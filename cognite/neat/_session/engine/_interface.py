from collections.abc import Iterable
from typing import Any, Protocol

from rdflib import Literal, URIRef


class Extractor(Protocol):
    def extract(self) -> Iterable[tuple[URIRef, URIRef, Literal | URIRef]]: ...


class ConfigAPI(Protocol):
    format: str | None = None
    file: Any | None
    type: str | None
    primary_key: str | None
    mapping: Any | None = None


class NeatEngine(Protocol):
    version: str = "2.0.0"

    @property
    def set(self) -> ConfigAPI: ...

    def create_extractor(self) -> Extractor: ...
