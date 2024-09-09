import json
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Set
from typing import Generic, TypeVar

from cognite.client.data_classes._base import CogniteResource
from rdflib import XSD, Literal, Namespace, URIRef

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.auxiliary import string_to_ideal_type

T_CogniteResource = TypeVar("T_CogniteResource", bound=CogniteResource)

DEFAULT_SKIP_METADATA_VALUES = frozenset({"nan", "null", "none", ""})


class ClassicCDFExtractor(BaseExtractor, ABC, Generic[T_CogniteResource]):
    """This is the Base Extractor for all classic CDF resources.

    A classic resource is recognized in that it has a metadata attribute of type dict[str, str].

    Args:
        items (Iterable[T_CogniteResource]): An iterable of classic resource.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        to_type (Callable[[T_CogniteResource], str | None], optional): A function to convert an item to a type.
            Defaults to None. If None or if the function returns None, the asset will be set to the default type.
        total (int, optional): The total number of items to load. If passed, you will get a progress bar if rich
            is installed. Defaults to None.
        limit (int, optional): The maximal number of items to load. Defaults to None. This is typically used for
            testing setup of the extractor. For example, if you are extracting 100 000 assets, you might want to
            limit the extraction to 1000 assets to test the setup.
        unpack_metadata (bool, optional): Whether to unpack metadata. Defaults to False, which yields the metadata as
            a JSON string.
        skip_metadata_values (set[str] | frozenset[str] | None, optional): If you are unpacking metadata, then
           values in this set will be skipped.
    """

    _default_rdf_type: str
    _SPACE_PATTERN = re.compile(r"\s+")

    def __init__(
        self,
        items: Iterable[T_CogniteResource],
        namespace: Namespace | None = None,
        to_type: Callable[[T_CogniteResource], str | None] | None = None,
        total: int | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.items = items
        self.to_type = to_type
        self.total = total
        self.limit = min(limit, total) if limit and total else limit
        self.unpack_metadata = unpack_metadata
        self.skip_metadata_values = skip_metadata_values

    def extract(self) -> Iterable[Triple]:
        """Extracts an asset with the given asset_id."""
        if self.total:
            try:
                from rich.progress import track
            except ModuleNotFoundError:
                to_iterate = self.items
            else:
                to_iterate = track(
                    self.items,
                    total=self.limit or self.total,
                    description=f"Extracting {type(self).__name__.removesuffix('Extractor')}",
                )
        else:
            to_iterate = self.items
        for no, asset in enumerate(to_iterate):
            yield from self._item2triples(asset)
            if self.limit and no >= self.limit:
                break

    @abstractmethod
    def _item2triples(self, item: T_CogniteResource) -> list[Triple]:
        raise NotImplementedError()

    def _metadata_to_triples(self, id_: URIRef, metadata: dict[str, str]) -> Iterable[Triple]:
        if self.unpack_metadata:
            for key, value in metadata.items():
                if value and (self.skip_metadata_values is None or value.casefold() not in self.skip_metadata_values):
                    yield (
                        id_,
                        self.namespace[key],
                        Literal(string_to_ideal_type(value)),
                    )
        else:
            yield id_, self.namespace.metadata, Literal(json.dumps(metadata), datatype=XSD._NS["json"])

    def _get_rdf_type(self, item: T_CogniteResource) -> str:
        type_ = self._default_rdf_type
        if self.to_type:
            type_ = self.to_type(item) or type_
        return self._SPACE_PATTERN.sub("_", type_)
