import json
import urllib.parse
from collections.abc import Callable, Iterable, Mapping, Set
from typing import Any

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.instances import Instance
from rdflib import XSD, Literal, Namespace, URIRef

from cognite.neat.core._shared import Triple
from cognite.neat.core._utils.auxiliary import string_to_ideal_type

from ._base import BaseExtractor

DEFAULT_EMPTY_VALUES = frozenset({"nan", "null", "none", "", " ", "nil", "n/a", "na", "unknown", "undefined"})


class DictExtractor(BaseExtractor):
    def __init__(
        self,
        id_: URIRef,
        data: Mapping[str, Any],
        namespace: Namespace,
        uri_ref_keys: set[str] | None = None,
        empty_values: Set[str] = DEFAULT_EMPTY_VALUES,
        str_to_ideal_type: bool = False,
        unpack_json: bool = False,
        source_by_property: dict[str, str] | None = None,
        typed_ids: bool = False,
    ) -> None:
        self.id_ = id_
        self.namespace = namespace
        self.data = data
        self.uri_ref_keys = uri_ref_keys or set()
        self.empty_values = empty_values
        self.str_to_ideal_type = str_to_ideal_type
        self.unpack_json = unpack_json
        self.source_by_property = source_by_property or {}
        self.typed_ids = typed_ids

    def extract(self) -> Iterable[Triple]:
        for key, value in self.data.items():
            for predicate_str, object_ in self._get_predicate_objects_pair(key, value, self.unpack_json):
                yield self.id_, self.namespace[urllib.parse.quote(predicate_str)], object_

    def _typed_suffix(self, property_: str) -> str:
        """Return the suffix for the given property based on its type."""
        return self.source_by_property[property_] if property_ in self.source_by_property and self.typed_ids else ""

    def _get_predicate_objects_pair(
        self, key: str, value: Any, unpack_json: bool
    ) -> Iterable[tuple[str, Literal | URIRef]]:
        # if we have connections they are here ...
        if key in self.uri_ref_keys and not isinstance(value, dict | list):
            object_id = urllib.parse.quote(value)

            if typed_suffix := self._typed_suffix(key):
                object_id += f"?type={typed_suffix}"

            yield key, URIRef(self.namespace[object_id])
        if isinstance(value, str | float | bool | int):
            yield key, Literal(value)
        elif isinstance(value, dict) and unpack_json:
            yield from self._unpack_json(value)
        elif isinstance(value, dict):
            # This object is a json object.
            yield key, Literal(json.dumps(value), datatype=XSD._NS["json"])
        elif isinstance(value, list):
            for item in value:
                yield from self._get_predicate_objects_pair(key, item, False)

    def _unpack_json(self, value: dict, parent: str | None = None) -> Iterable[tuple[str, Literal | URIRef]]:
        for sub_key, sub_value in value.items():
            key = f"{parent}_{sub_key}" if parent else sub_key
            if isinstance(sub_value, str):
                if sub_value.casefold() in self.empty_values:
                    continue
                if self.str_to_ideal_type:
                    yield key, Literal(string_to_ideal_type(sub_value))
                else:
                    yield key, Literal(sub_value)
            elif isinstance(sub_value, int | float | bool):
                yield key, Literal(sub_value)
            elif isinstance(sub_value, dict):
                yield from self._unpack_json(sub_value, key)
            elif isinstance(sub_value, list):
                for no, item in enumerate(sub_value, 1):
                    if isinstance(item, dict):
                        yield from self._unpack_json(item, f"{key}_{no}")
                    else:
                        yield from self._get_predicate_objects_pair(key, item, self.unpack_json)
            else:
                yield key, Literal(str(sub_value))


class DMSPropertyExtractor(DictExtractor):
    def __init__(
        self,
        id_: URIRef,
        data: Mapping[str, Any],
        namespace: Namespace,
        as_uri_ref: Callable[[Instance | dm.DirectRelationReference, str | None], URIRef],
        empty_values: Set[str] = DEFAULT_EMPTY_VALUES,
        str_to_ideal_type: bool = False,
        unpack_json: bool = False,
        source_by_property: dict[str, str] | None = None,
        typed_ids: bool = False,
    ) -> None:
        super().__init__(
            id_=id_,
            data=data,
            namespace=namespace,
            uri_ref_keys=None,
            empty_values=empty_values,
            str_to_ideal_type=str_to_ideal_type,
            unpack_json=unpack_json,
            source_by_property=source_by_property,
            typed_ids=typed_ids,
        )
        self.as_uri_ref = as_uri_ref

    def _get_predicate_objects_pair(
        self, key: str, value: Any, unpack_json: bool
    ) -> Iterable[tuple[str, Literal | URIRef]]:
        # use case: direct relation / object property
        if isinstance(value, dict) and "space" in value and "externalId" in value:
            yield key, self.as_uri_ref(dm.DirectRelationReference.load(value), self._typed_suffix(key))

        # use case: attributes / data type properties
        else:
            yield from super()._get_predicate_objects_pair(key, value, unpack_json)
