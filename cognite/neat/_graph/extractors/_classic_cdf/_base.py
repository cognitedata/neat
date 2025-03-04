import json
import re
import sys
import typing
import urllib.parse
import warnings
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence, Set
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar, cast

from cognite.client import CogniteClient
from cognite.client.data_classes._base import WriteableCogniteResource
from cognite.client.exceptions import CogniteAPIError
from pydantic import AnyHttpUrl, ValidationError
from rdflib import RDF, XSD, Literal, Namespace, URIRef

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph.extractors._base import BaseExtractor
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import CDFAuthWarning, NeatValueWarning
from cognite.neat._shared import Triple
from cognite.neat._utils.auxiliary import string_to_ideal_type
from cognite.neat._utils.collection_ import iterate_progress_bar_if_above_config_threshold

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
        prefix (str, optional): A prefix to add to the rdf type. Defaults to None.
        identifier (Literal["id", "externalId"], optional): The identifier to use. Defaults to "id".
    """

    _default_rdf_type: str
    _instance_id_prefix: str
    _SPACE_PATTERN = re.compile(r"\s+")

    def __init__(
        self,
        items: Iterable[T_CogniteResource],
        namespace: Namespace | None = None,
        total: int | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.items = items
        self.total = total
        self.limit = min(limit, total) if limit and total else limit
        self.unpack_metadata = unpack_metadata
        self.skip_metadata_values = skip_metadata_values
        self.camel_case = camel_case
        self.as_write = as_write
        self.prefix = prefix
        self.identifier = identifier
        # If identifier=externalId, we need to keep track of the external ids
        # and use them in linking of Files, Sequences, TimeSeries, and Events.
        self.asset_external_ids_by_id: dict[int, str] = {}
        self.lookup_dataset_external_id: Callable[[int], str] | None = None
        # Used by the ClassicGraphExtractor to log URIRefs
        self._log_urirefs = False
        self._uriref_by_external_id: dict[str, URIRef] = {}
        self.asset_parent_uri_by_id: dict[int, URIRef] = {}
        self.asset_parent_uri_by_external_id: dict[str, URIRef] = {}

    def extract(self) -> Iterable[Triple]:
        """Extracts an asset with the given asset_id."""
        from ._assets import AssetsExtractor

        if self.total is not None and self.total > 0:
            to_iterate = iterate_progress_bar_if_above_config_threshold(
                self.items, self.total, f"Extracting {type(self).__name__.removesuffix('Extractor')}"
            )
        else:
            to_iterate = self.items
        if self.identifier == "externalId" and isinstance(self, AssetsExtractor):
            to_iterate = self._store_asset_external_ids(to_iterate)  # type: ignore[attr-defined]

        for no, asset in enumerate(to_iterate):
            yield from self._item2triples(asset)
            if self.limit and no >= self.limit:
                break

    def _store_asset_external_ids(self, items: Iterable[T_CogniteResource]) -> Iterable[T_CogniteResource]:
        for item in items:
            if hasattr(item, "id") and hasattr(item, "external_id"):
                self.asset_external_ids_by_id[item.id] = item.external_id
            yield item

    def _item2triples(self, item: T_CogniteResource) -> list[Triple]:
        if self.identifier == "id":
            id_value: str | None
            if hasattr(item, "id"):
                id_value = str(item.id)
            else:
                id_value = self._fallback_id(item)
            if id_value is None:
                return []
            id_suffix = id_value
        elif self.identifier == "externalId":
            if not hasattr(item, "external_id"):
                return []
            id_suffix = self._external_id_as_uri_suffix(item.external_id)
        else:
            raise NeatValueError(f"Unknown identifier {self.identifier}")

        id_ = self.namespace[f"{self._instance_id_prefix}{id_suffix}"]
        if self._log_urirefs and hasattr(item, "external_id"):
            self._uriref_by_external_id[item.external_id] = id_

        type_ = self._get_rdf_type()

        # Set rdf type
        triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]
        if self.as_write:
            item = item.as_write()
        dumped = item.dump(self.camel_case)
        dumped.pop("id", None)

        if "metadata" in dumped:
            triples.extend(self._metadata_to_triples(id_, dumped.pop("metadata")))

        triples.extend(self._item2triples_special_cases(id_, dumped))

        parent_renaming = {"parent_external_id": "parent_id", "parentExternalId": "parentId"}
        parent_key = set(parent_renaming.keys()) | set(parent_renaming.values())

        for key, value in dumped.items():
            if value is None or value == []:
                continue
            values = value if isinstance(value, Sequence) and not isinstance(value, str) else [value]
            for raw in values:
                object_ = self._as_object(raw, key)
                if object_ is None:
                    continue
                if key in parent_key:
                    parent_id = cast(URIRef, object_)
                    if isinstance(raw, str):
                        self.asset_parent_uri_by_external_id[raw] = parent_id
                    elif isinstance(raw, int):
                        self.asset_parent_uri_by_id[raw] = parent_id
                    # We add a triple to include the parent. This is such that for example the parent
                    # externalID will remove the prefix when loading.
                    triples.append((parent_id, RDF.type, self.namespace[self._get_rdf_type()]))
                    # Parent external ID must be renamed to parent id to match the data model.
                    key = parent_renaming.get(key, key)

                triples.append((id_, self.namespace[key], object_))
        return triples

    def _item2triples_special_cases(self, id_: URIRef, dumped: dict[str, Any]) -> list[Triple]:
        """This can be overridden to handle special cases for the item."""
        return []

    @classmethod
    def _external_id_as_uri_suffix(cls, external_id: str | None) -> str:
        if external_id == "" or (isinstance(external_id, str) and external_id.strip() == ""):
            warnings.warn(NeatValueWarning(f"Empty external id in {cls._default_rdf_type}"), stacklevel=2)
            return "empty"
        elif external_id == "\x00":
            warnings.warn(NeatValueWarning(f"Null external id in {cls._default_rdf_type}"), stacklevel=2)
            return "null"
        elif external_id is None:
            warnings.warn(NeatValueWarning(f"None external id in {cls._default_rdf_type}"), stacklevel=2)
            return "None"
        # The external ID needs to pass the ^[^\\x00]{1,256}$ regex for the DMS API.
        # In addition, neat internals requires the external ID to be a valid URI.
        return urllib.parse.quote(external_id)

    def _fallback_id(self, item: T_CogniteResource) -> str | None:
        raise AttributeError(
            f"Item of type {type(item)} does not have an id attribute. "
            "Please implement the _fallback_id method in the extractor."
        )

    def _metadata_to_triples(self, id_: URIRef, metadata: dict[str, str]) -> Iterable[Triple]:
        if self.unpack_metadata:
            for key, value in metadata.items():
                if value and (self.skip_metadata_values is None or value.casefold() not in self.skip_metadata_values):
                    yield (
                        id_,
                        self.namespace[urllib.parse.quote(key)],
                        Literal(string_to_ideal_type(value)),
                    )
        else:
            yield id_, self.namespace.metadata, Literal(json.dumps(metadata), datatype=XSD._NS["json"])

    def _get_rdf_type(self) -> str:
        type_ = self._default_rdf_type
        if self.prefix:
            type_ = f"{self.prefix}{type_}"
        return self._SPACE_PATTERN.sub("_", type_)

    def _as_object(self, raw: Any, key: str) -> Literal | URIRef | None:
        """Return properly formatted object part of s-p-o triple"""
        if key in {"data_set_id", "dataSetId"}:
            if self.identifier == "externalId" and self.lookup_dataset_external_id:
                try:
                    data_set_external_id = self.lookup_dataset_external_id(raw)
                except KeyError:
                    return Literal("Unknown data set")
                else:
                    return self.namespace[
                        f"{InstanceIdPrefix.data_set}{self._external_id_as_uri_suffix(data_set_external_id)}"
                    ]
            else:
                return self.namespace[f"{InstanceIdPrefix.data_set}{raw}"]
        elif key in {"parentId", "parent_id", "parentExternalId", "parent_external_id"}:
            if self.identifier == "id" and key in {"parent_id", "parentId"}:
                return self.namespace[f"{InstanceIdPrefix.asset}{raw}"]
            elif (
                self.identifier == "externalId"
                and key in {"parent_external_id", "parentExternalId"}
                and isinstance(raw, str)
            ):
                return self.namespace[f"{InstanceIdPrefix.asset}{self._external_id_as_uri_suffix(raw)}"]
            else:
                # Skip it
                return None
        elif key in {"assetId", "asset_id", "assetIds", "asset_ids", "rootId", "root_id"}:
            if self.identifier == "id":
                return self.namespace[f"{InstanceIdPrefix.asset}{raw}"]
            else:
                try:
                    asset_external_id = self._external_id_as_uri_suffix(self.asset_external_ids_by_id[raw])
                except KeyError:
                    warnings.warn(NeatValueWarning(f"Unknown asset id {raw}"), stacklevel=2)
                    return Literal("Unknown asset", datatype=XSD.string)
                else:
                    return self.namespace[f"{InstanceIdPrefix.asset}{asset_external_id}"]
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
            try:
                return Literal(datetime.fromtimestamp(raw / 1000, timezone.utc), datatype=XSD.dateTime)
            except (OSError, ValueError) as e:
                warnings.warn(NeatValueWarning(f"Failed to convert timestamp {raw} to datetime: {e!s}"), stacklevel=2)
                return Literal(raw)
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
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
    ):
        total, items = cls._handle_no_access(lambda: cls._from_dataset(client, data_set_external_id))
        return cls(
            items,
            namespace,
            total,
            limit,
            unpack_metadata,
            skip_metadata_values,
            camel_case,
            as_write,
            prefix,
            identifier,
        )

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
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
    ):
        total, items = cls._handle_no_access(lambda: cls._from_hierarchy(client, root_asset_external_id))
        return cls(
            items,
            namespace,
            total,
            limit,
            unpack_metadata,
            skip_metadata_values,
            camel_case,
            as_write,
            prefix,
            identifier,
        )

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
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
        camel_case: bool = True,
        as_write: bool = False,
        prefix: str | None = None,
        identifier: typing.Literal["id", "externalId"] = "id",
    ):
        total, items = cls._from_file(file_path)
        return cls(
            items,
            namespace,
            total,
            limit,
            unpack_metadata,
            skip_metadata_values,
            camel_case,
            as_write,
            prefix,
            identifier,
        )

    @classmethod
    @abstractmethod
    def _from_file(cls, file_path: str | Path) -> tuple[int | None, Iterable[T_CogniteResource]]:
        raise NotImplementedError

    @classmethod
    def _handle_no_access(
        cls, action: Callable[[], tuple[int | None, Iterable[T_CogniteResource]]]
    ) -> tuple[int | None, Iterable[T_CogniteResource]]:
        try:
            return action()
        except CogniteAPIError as e:
            if e.code == 403:
                warnings.warn(
                    CDFAuthWarning(f"extract {cls.__name__.removesuffix('Extractor').casefold()}", str(e)), stacklevel=2
                )
                return 0, []
            else:
                raise e
