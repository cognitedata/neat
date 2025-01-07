import json
import re
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence, Set
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar

from cognite.client import CogniteClient
from cognite.client.data_classes._base import WriteableCogniteResource
from pydantic import AnyHttpUrl, ValidationError
from rdflib import RDF, XSD, Literal, Namespace, URIRef

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph.extractors._base import BaseExtractor
from cognite.neat._shared import Triple
from cognite.neat._utils.auxiliary import string_to_ideal_type

T_CogniteResource = TypeVar("T_CogniteResource", bound=WriteableCogniteResource)

DEFAULT_SKIP_METADATA_VALUES = frozenset({"nan", "null", "none", ""})

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum


class InstanceIdPrefix(StrEnum):
    asset = "Asset_"
    label = "Label_"
    relationship = "Relationship_"
    sequence = "Sequence_"
    file = "File_"
    time_series = "TimeSeries_"
    event = "Event_"
    data_set = "DataSet_"

    @classmethod
    def from_str(cls, raw: str) -> "InstanceIdPrefix":
        raw = raw.title() + "_"
        if raw == "Timeseries_":
            return cls.time_series
        else:
            return cls(raw)


class ClassicCDFBaseExtractor(BaseExtractor, ABC, Generic[T_CogniteResource]):
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
        camel_case (bool, optional): Whether to use camelCase instead of snake_case for property names.
            Defaults to True.
        as_write (bool, optional): Whether to use the write/request format of the items. Defaults to False.
    """

    _default_rdf_type: str
    _instance_id_prefix: str
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
        camel_case: bool = True,
        as_write: bool = False,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.items = items
        self.to_type = to_type
        self.total = total
        self.limit = min(limit, total) if limit and total else limit
        self.unpack_metadata = unpack_metadata
        self.skip_metadata_values = skip_metadata_values
        self.camel_case = camel_case
        self.as_write = as_write

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

    def _item2triples(self, item: T_CogniteResource) -> list[Triple]:
        id_value: str | None
        if hasattr(item, "id"):
            id_value = str(item.id)
        else:
            id_value = self._fallback_id(item)
        if id_value is None:
            return []

        id_ = self.namespace[f"{self._instance_id_prefix}{id_value}"]

        type_ = self._get_rdf_type(item)

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]
        if self.as_write:
            item = item.as_write()
        dumped = item.dump(self.camel_case)
        dumped.pop("id", None)
        # We have parentId so we don't need parentExternalId
        dumped.pop("parentExternalId", None)
        if "metadata" in dumped:
            triples.extend(self._metadata_to_triples(id_, dumped.pop("metadata")))

        triples.extend(self._item2triples_special_cases(id_, dumped))

        for key, value in dumped.items():
            if value is None or value == []:
                continue
            values = value if isinstance(value, Sequence) and not isinstance(value, str) else [value]
            for raw in values:
                triples.append((id_, self.namespace[key], self._as_object(raw, key)))
        return triples

    def _item2triples_special_cases(self, id_: URIRef, dumped: dict[str, Any]) -> list[Triple]:
        """This can be overridden to handle special cases for the item."""
        return []

    def _fallback_id(self, item: T_CogniteResource) -> str | None:
        raise AttributeError(
            f"Item of type {type(item)} does not have an id attribute. "
            f"Please implement the _fallback_id method in the extractor."
        )

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

    def _as_object(self, raw: Any, key: str) -> Literal | URIRef:
        if key in {"data_set_id", "dataSetId"}:
            return self.namespace[f"{InstanceIdPrefix.data_set}{raw}"]
        elif key in {"assetId", "asset_id", "assetIds", "asset_ids", "parentId", "rootId", "parent_id", "root_id"}:
            return self.namespace[f"{InstanceIdPrefix.asset}{raw}"]
        elif key in {
            "startTime",
            "endTime",
            "createdTime",
            "lastUpdatedTime",
            "start_time",
            "end_time",
            "created_time",
            "last_updated_time",
        } and isinstance(raw, int):
            return Literal(datetime.fromtimestamp(raw / 1000, timezone.utc), datatype=XSD.dateTime)
        elif key == "labels":
            from ._labels import LabelsExtractor

            return self.namespace[f"{InstanceIdPrefix.label}{LabelsExtractor._label_id(raw)}"]
        elif key in {"sourceType", "targetType", "source_type", "target_type"} and isinstance(raw, str):
            # Relationship types. Titled so they can be looked up.
            return self.namespace[raw.title()]
        elif key in {"unit_external_id", "unitExternalId"}:
            try:
                return URIRef(str(AnyHttpUrl(raw)))
            except ValidationError:
                ...
        return Literal(raw)

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[T_CogniteResource], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
    ):
        total, items = cls._from_dataset(client, data_set_external_id)
        return cls(items, namespace, to_type, total, limit, unpack_metadata, skip_metadata_values, camel_case, as_write)

    @classmethod
    @abstractmethod
    def _from_dataset(
        cls, client: CogniteClient, data_set_external_id: str
    ) -> tuple[int | None, Iterable[T_CogniteResource]]:
        raise NotImplementedError

    @classmethod
    def from_hierarchy(
        cls,
        client: CogniteClient,
        root_asset_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[T_CogniteResource], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
    ):
        total, items = cls._from_hierarchy(client, root_asset_external_id)
        return cls(items, namespace, to_type, total, limit, unpack_metadata, skip_metadata_values, camel_case, as_write)

    @classmethod
    @abstractmethod
    def _from_hierarchy(
        cls, client: CogniteClient, root_asset_external_id: str
    ) -> tuple[int | None, Iterable[T_CogniteResource]]:
        raise NotImplementedError

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        namespace: Namespace | None = None,
        to_type: Callable[[T_CogniteResource], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
    ):
        total, items = cls._from_file(file_path)
        return cls(items, namespace, to_type, total, limit, unpack_metadata, skip_metadata_values, camel_case, as_write)

    @classmethod
    @abstractmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[T_CogniteResource]]:
        raise NotImplementedError
