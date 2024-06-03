import json
import warnings
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import yaml
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import ViewId
from pydantic import HttpUrl, TypeAdapter, ValidationError, ValidationInfo, create_model, field_validator
from pydantic.main import Model
from rdflib.query import ResultRow
from rdflib.term import URIRef

from cognite.neat.graph.stores import NeatGraphStoreBase
from cognite.neat.rules.issues import NeatValidationError
from cognite.neat.rules.models import DMSRules
from cognite.neat.rules.models.data_types import _DATA_TYPE_BY_DMS_TYPE

from ._base import CDFLoader


class DMSLoader(CDFLoader[dm.InstanceApply]):
    def __init__(
        self,
        graph_store: NeatGraphStoreBase,
        data_model: dm.DataModel[dm.View],
        class_by_view_id: dict[ViewId, URIRef] | None = None,
        add_class_prefix: bool = False,
    ):
        super().__init__(graph_store)
        self.data_model = data_model
        self.class_by_view_id = class_by_view_id or {}
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
        return cls(graph_store, data_model, {}, add_class_prefix)

    @classmethod
    def from_rules(
        cls, rules: DMSRules, graph_store: NeatGraphStoreBase, add_class_prefix: bool = False
    ) -> "DMSLoader":
        schema = rules.as_schema()
        # Todo add error handling
        return cls(graph_store, schema.as_read_model(), {}, add_class_prefix)

    def _load(self, stop_on_exception: bool = False) -> Iterable[dm.InstanceApply | NeatValidationError]:
        for view in self.data_model.views:
            view_id = view.as_id()
            # Todo Some tracking and creation of a structure to do validation
            validation_structure = self._create_validation_structure(view)  # type: ignore[var-annotated]
            uri_ref = self.class_by_view_id.get(view.as_id(), URIRef(f"{view.space}:{view.external_id}"))
            triples = self.graph_store.queries.list_instances_of_type(uri_ref)
            for identifier, properties in _triples2dictionary(triples).items():
                try:
                    yield self._create_instance(identifier, properties, validation_structure, view_id)
                except Exception:
                    # Todo Convert to NeatValidationError
                    raise

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

    def _create_validation_structure(self, view: dm.View) -> type[Model]:
        field_definitions: dict[str, tuple[type, Any]] = {}
        for prop_name, prop in view.properties.items():
            if not isinstance(prop, dm.MappedProperty):
                continue
            data_type = _DATA_TYPE_BY_DMS_TYPE.get(prop.type._type)
            if not data_type:
                # Todo warning
                continue
            python_type: Any = data_type.python
            if prop.type.is_list:
                python_type = list[python_type]
            default_value: Any = prop.default_value
            if prop.nullable:
                python_type = python_type | None
            else:
                default_value = ...

            field_definitions[prop_name] = (python_type, default_value)

        def parse_list(cls, value: Any, info: ValidationInfo) -> list[str]:
            if isinstance(value, list) and cls.model_fields[info.field_name].annotation is not list:
                if len(value) == 1:
                    return value[0]
                raise ValueError(f"Got multiple values for {info.field_name}: {value}")
            return value

        validators: dict[str, classmethod] = {"parse_list": field_validator("*", mode="before")(parse_list)}  # type: ignore[dict-item,arg-type]

        return create_model(view.external_id, __validators__=validators, **field_definitions)  # type: ignore[arg-type, call-overload]

    def _create_instance(
        self, identifier: str, properties: dict, validation_structure: type[Model], view_id: dm.ViewId
    ) -> dm.InstanceApply:
        created = validation_structure.model_validate(properties)

        return dm.NodeApply(
            space=self.data_model.space,
            external_id=identifier,
            # type=#RDF type
            sources=[dm.NodeOrEdgeData(source=view_id, properties=dict(created.model_dump().items()))],
        )


def _triples2dictionary(
    triples: Iterable[ResultRow],
) -> dict[str, dict[str, list[str]]]:
    """Converts list of triples to dictionary"""
    values_by_property_by_identifier: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for triple in triples:
        id_, property_, value = _remove_namespace(triple, special_separator=":")
        values_by_property_by_identifier[id_][property_].append(value)
    return values_by_property_by_identifier


def _remove_namespace(URI: ResultRow, special_separator: str = "#") -> list[str]:
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

    output: list[str] = []
    for u in uris:
        try:
            _ = TypeAdapter(HttpUrl).validate_python(u)
            output.append(u.split(special_separator if special_separator in u else "#" if "#" in u else "/")[-1])
        except ValidationError:
            u_str = str(u)
            if special_separator in u_str:
                output.append(u_str.split(special_separator)[-1])
            else:
                output.append(u_str)

    return output
