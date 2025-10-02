import json
import urllib.parse
from collections.abc import Callable, Iterable, Mapping, Set
from typing import Any

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.instances import Instance
from rdflib import XSD, Literal, Namespace, URIRef

from cognite.neat.v0.core._shared import Triple
from cognite.neat.v0.core._utils.auxiliary import string_to_ideal_type

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
    ) -> None:
        self.id_ = id_
        self.namespace = namespace
        self.data = data
        self.uri_ref_keys = uri_ref_keys or set()
        self.empty_values = empty_values
        self.str_to_ideal_type = str_to_ideal_type
        self.unpack_json = unpack_json

    def extract(self) -> Iterable[Triple]:
        for key, value in self.data.items():
            for predicate_str, object_ in self._get_predicate_objects_pair(key, value, self.unpack_json):
                yield self.id_, self.namespace[urllib.parse.quote(predicate_str)], object_

    def _get_predicate_objects_pair(
        self, key: str, value: Any, unpack_json: bool
    ) -> Iterable[tuple[str, Literal | URIRef]]:
        if key in self.uri_ref_keys and not isinstance(value, dict | list):
            # exist if key is meant to form a URIRef
            yield key, URIRef(self.namespace[urllib.parse.quote(value)])
        elif isinstance(value, float | bool | int):
            yield key, Literal(value)
        elif isinstance(value, str):
            yield key, Literal(string_to_ideal_type(value)) if self.str_to_ideal_type else Literal(value)
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
        as_uri_ref: Callable[[Instance | dm.DirectRelationReference], URIRef],
        empty_values: Set[str] = DEFAULT_EMPTY_VALUES,
        str_to_ideal_type: bool = False,
        unpack_json: bool = False,
    ) -> None:
        super().__init__(id_, data, namespace, None, empty_values, str_to_ideal_type, unpack_json)
        self.as_uri_ref = as_uri_ref

    def _get_predicate_objects_pair(
        self, key: str, value: Any, unpack_json: bool
    ) -> Iterable[tuple[str, Literal | URIRef]]:
        if isinstance(value, dict) and "space" in value and "externalId" in value:
            yield key, self.as_uri_ref(dm.DirectRelationReference.load(value))
        else:
            yield from super()._get_predicate_objects_pair(key, value, unpack_json)
