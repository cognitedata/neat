import json
import warnings
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import cast, overload

import yaml
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from pydantic import HttpUrl, TypeAdapter, ValidationError
from rdflib.term import URIRef

from cognite.neat.graph.stores import NeatGraphStoreBase
from cognite.neat.rules.issues import NeatValidationError
from cognite.neat.rules.models import DMSRules

from ._base import CDFLoader


class DMSLoader(CDFLoader[dm.InstanceApply]):
    def __init__(
        self, graph_store: NeatGraphStoreBase, data_model: dm.DataModel[dm.View], add_class_prefix: bool = False
    ):
        super().__init__(graph_store)
        self.data_model = data_model
        self.add_class_prefix = add_class_prefix

    @classmethod
    def from_data_model_id(
        cls,
        client: CogniteClient,
        data_model_id: dm.DataModelId,
        graph_store: NeatGraphStoreBase,
        add_class_prefix: bool = False,
    ) -> "DMSLoader":
        # Todo add error handling
        data_model = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True).latest_version()
        return cls(graph_store, data_model, add_class_prefix)

    @classmethod
    def from_rules(
        cls, rules: DMSRules, graph_store: NeatGraphStoreBase, add_class_prefix: bool = False
    ) -> "DMSLoader":
        schema = rules.as_schema()
        # Todo add error handling
        return cls(graph_store, schema.as_read_model(), add_class_prefix)

    def _load(self, stop_on_exception: bool = False) -> Iterable[dm.InstanceApply | NeatValidationError]:
        classes = (view.external_id for view in self.data_model.views)
        for class_name in classes:
            # Some tracking and creation of a structure to do validation
            validation_structure = self._create_validation_structure(class_name)
            triples = self.graph_store.queries.list_instances_of_type(class_name)
            for instance_dict in _triples2dictionary(triples).values():
                try:
                    yield self._create_instance(class_name, instance_dict, validation_structure)
                except NeatValidationError as e:
                    yield e

    def load_into_cdf_iterable(self, client: CogniteClient, dry_run: bool = False) -> Iterable:
        raise NotImplementedError()

    def write_to_file(self, filepath: Path) -> None:
        if filepath.suffix not in [".json", ".yaml", ".yml"]:
            raise ValueError(f"File format {filepath.suffix} is not supported")
        dumped: dict[str, list] = {"nodes": [], "edges": [], "errors": []}
        for item in self.load(stop_on_exception=False):
            key = {
                dm.NodeApply: "nodes",
                dm.EdgeApply: "edges",
                NeatValidationError: "errors",
            }.get(type(item))
            if key is None:
                # Todo use appropriate warning
                warnings.warn(f"Item {item} is not supported", UserWarning, stacklevel=2)
                continue
            dumped[key].append(item.dump())
        with filepath.open("w", encoding=self._encoding, newline=self._new_line) as f:
            if filepath.suffix == ".json":
                json.dump(dumped, f, indent=2)
            else:
                yaml.safe_dump(dumped, f, sort_keys=False)

    def _create_validation_structure(self, class_name: str) -> dict:
        return {}

    def _create_instance(self, class_name: str, instance_dict: dict, validation_structure: dict) -> dm.InstanceApply:
        raise NotImplementedError()


def _triples2dictionary(
    triples: Iterable[tuple[URIRef, URIRef, str | URIRef]],
) -> dict[URIRef, dict[URIRef | str, list[str | URIRef]]]:
    """Converts list of triples to dictionary"""
    dictionary: dict[URIRef, dict[URIRef | str, list[str | URIRef]]] = {}
    for triple in triples:
        id_, property_, value = _remove_namespace(*triple)  # type: ignore[misc]
        if id_ not in dictionary:
            dictionary[id_] = defaultdict(list)
            dictionary[id_]["external_id"].append(id_)

        dictionary[id_][property_].append(value)
    return dictionary


@overload
def _remove_namespace(*URI: URIRef | str, special_separator: str = "#_") -> str: ...


@overload
def _remove_namespace(*URI: tuple[URIRef | str, ...], special_separator: str = "#_") -> tuple[str, ...]: ...


def _remove_namespace(
    *URI: URIRef | str | tuple[URIRef | str, ...], special_separator: str = "#_"
) -> tuple[str, ...] | str:
    """Removes namespace from URI

    Args
        URI: URIRef | str
            URI of an entity
        special_separator : str
            Special separator to use instead of # or / if present in URI
            Set by default to "#_" which covers special client use case

    Returns
        Entities id without namespace

    Examples:

        >>> _remove_namespace("http://www.example.org/index.html#section2")
        'section2'
        >>> _remove_namespace("http://www.example.org/index.html#section2", "http://www.example.org/index.html#section3")
        ('section2', 'section3')
    """
    if isinstance(URI, str | URIRef):
        uris = (URI,)
    elif isinstance(URI, tuple):
        # Assume that all elements in the tuple are of the same type following type hint
        uris = cast(tuple[URIRef | str, ...], URI)
    else:
        raise TypeError(f"URI must be of type URIRef or str, got {type(URI)}")

    output = []
    for u in uris:
        try:
            _ = TypeAdapter(HttpUrl).validate_python(u)
            output.append(u.split(special_separator if special_separator in u else "#" if "#" in u else "/")[-1])
        except ValidationError:
            output.append(str(u))

    return tuple(output) if len(output) > 1 else output[0]
