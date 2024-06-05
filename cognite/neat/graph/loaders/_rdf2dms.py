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
        class_by_view_id: dict[ViewId, str] | None = None,
    ):
        super().__init__(graph_store)
        self.data_model = data_model
        self.class_by_view_id = class_by_view_id or {}

    @classmethod
    def from_data_model_id(
        cls,
        client: CogniteClient,
        data_model_id: dm.DataModelId,
        graph_store: NeatGraphStoreBase,
    ) -> "DMSLoader":
        # Todo add error handling
        data_model = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True).latest_version()
        return cls(graph_store, data_model, {})

    @classmethod
    def from_rules(
        cls, rules: DMSRules, graph_store: NeatGraphStoreBase
    ) -> "DMSLoader":
        schema = rules.as_schema()
        # Todo add error handling
        return cls(graph_store, schema.as_read_model(), {},)

    def _load(self, stop_on_exception: bool = False) -> Iterable[dm.InstanceApply | NeatValidationError]:
        for view in self.data_model.views:
            view_id = view.as_id()
            # Todo Some tracking and creation of a structure to do validation
            pydantic_cls = self._create_pydantic_class(view)  # type: ignore[var-annotated]
            class_name = self.class_by_view_id.get(view.as_id(), view.external_id)
            triples = self.graph_store.queries.literals_of_type(class_name)
            for identifier, properties in _triples2dictionary(triples).items():
                try:
                    yield self._create_node(identifier, properties, pydantic_cls, view_id)
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

    def _create_pydantic_class(self, view: dm.View) -> type[Model]:
        field_definitions: dict[str, tuple[type, Any]] = {}
        for prop_name, prop in view.properties.items():
            if not isinstance(prop, dm.MappedProperty):
                # Todo handle edges.
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

    def _create_node(
        self, identifier: str, properties: dict, pydantic_cls: type[Model], view_id: dm.ViewId
    ) -> dm.InstanceApply:
        created = pydantic_cls.model_validate(properties)

        return dm.NodeApply(
            space=self.data_model.space,
            external_id=identifier,
            # type=#RDF type
            sources=[dm.NodeOrEdgeData(source=view_id, properties=dict(created.model_dump().items()))],
        )


def _triples2dictionary(
    triples: Iterable[tuple[str, str, str]],
) -> dict[str, dict[str, list[str]]]:
    """Converts list of triples to dictionary"""
    values_by_property_by_identifier: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for id_, property_, value in triples:
        values_by_property_by_identifier[id_][property_].append(value)
    return values_by_property_by_identifier

