import json
import warnings
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import ViewId
from cognite.client.data_classes.data_modeling.views import SingleEdgeConnection
from pydantic import ValidationInfo, create_model, field_validator
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
        instance_space: str,
        class_by_view_id: dict[ViewId, str] | None = None,
    ):
        super().__init__(graph_store)
        self.data_model = data_model
        self.instance_space = instance_space
        self.class_by_view_id = class_by_view_id or {}

    @classmethod
    def from_data_model_id(
        cls,
        client: CogniteClient,
        data_model_id: dm.DataModelId,
        graph_store: NeatGraphStoreBase,
        instance_space: str,
    ) -> "DMSLoader":
        # Todo add error handling
        data_model = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True).latest_version()
        return cls(graph_store, data_model, instance_space, {})

    @classmethod
    def from_rules(cls, rules: DMSRules, graph_store: NeatGraphStoreBase, instance_space: str) -> "DMSLoader":
        schema = rules.as_schema()
        # Todo add error handling
        return cls(graph_store, schema.as_read_model(), instance_space, {})

    def _load(self, stop_on_exception: bool = False) -> Iterable[dm.InstanceApply | NeatValidationError]:
        for view in self.data_model.views:
            view_id = view.as_id()
            # Todo Some tracking and creation of a structure to do validation
            pydantic_cls, edge_by_properties = self._create_validation_classes(view)  # type: ignore[var-annotated]
            class_name = self.class_by_view_id.get(view.as_id(), view.external_id)
            triples = self.graph_store.queries.triples_of_type_instances(class_name)
            for identifier, properties in _triples2dictionary(triples).items():
                try:
                    yield self._create_node(identifier, properties, pydantic_cls, view_id)
                except Exception:
                    # Todo Convert to NeatValidationError
                    raise
                yield from self._create_edges(identifier, properties, edge_by_properties)

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

    def _create_validation_classes(self, view: dm.View) -> tuple[type[Model], dict[str, dm.EdgeConnection]]:
        field_definitions: dict[str, tuple[type, Any]] = {}
        edge_by_property: dict[str, dm.EdgeConnection] = {}
        direct_relation_by_property: dict[str, dm.DirectRelation] = {}
        for prop_name, prop in view.properties.items():
            if isinstance(prop, dm.EdgeConnection):
                edge_by_property[prop_name] = prop
            if isinstance(prop, dm.MappedProperty):
                if isinstance(prop.type, dm.DirectRelation):
                    direct_relation_by_property[prop_name] = prop.type
                    python_type: Any = dict
                else:
                    data_type = _DATA_TYPE_BY_DMS_TYPE.get(prop.type._type)
                    if not data_type:
                        # Todo warning
                        continue
                    python_type = data_type.python
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
        if direct_relation_by_property:

            def parse_direct_relation(cls, value: list, info: ValidationInfo) -> dict | list[dict]:
                # We validate above that we only get one value for single direct relations.
                if cls.model_fields[info.field_name].annotation is list:
                    return [{"space": self.instance_space, "externalId": v} for v in value]
                elif value:
                    return {"space": self.instance_space, "externalId": value[0]}
                return {}

            validators["parse_direct_relation"] = field_validator(*direct_relation_by_property.keys(), mode="before")(  # type: ignore[assignment]
                parse_direct_relation  # type: ignore[arg-type]
            )

        pydantic_cls = create_model(view.external_id, __validators__=validators, **field_definitions)  # type: ignore[arg-type, call-overload]
        return pydantic_cls, edge_by_property

    def _create_node(
        self, identifier: str, properties: dict[str, list[str]], pydantic_cls: type[Model], view_id: dm.ViewId
    ) -> dm.InstanceApply:
        created = pydantic_cls.model_validate(properties)

        return dm.NodeApply(
            space=self.instance_space,
            external_id=identifier,
            # type=#RDF type
            sources=[dm.NodeOrEdgeData(source=view_id, properties=dict(created.model_dump().items()))],
        )

    def _create_edges(
        self, identifier: str, properties: dict[str, list[str]], edge_by_properties: dict[str, dm.EdgeConnection]
    ) -> Iterable[dm.EdgeApply | NeatValidationError]:
        for prop, values in properties.items():
            if prop not in edge_by_properties:
                continue
            edge = edge_by_properties[prop]
            if isinstance(edge, SingleEdgeConnection) and len(values) > 1:
                # Todo convert to NeatValidationError
                raise ValueError(f"Multiple values for single edge {edge}")
            for target in values:
                yield dm.EdgeApply(
                    space=self.instance_space,
                    external_id=f"{identifier}.{prop}.{target}",
                    type=edge.type,
                    start_node=dm.DirectRelationReference(self.instance_space, identifier),
                    end_node=dm.DirectRelationReference(self.instance_space, target),
                )


def _triples2dictionary(
    triples: Iterable[tuple[str, str, str]],
) -> dict[str, dict[str, list[str]]]:
    """Converts list of triples to dictionary"""
    values_by_property_by_identifier: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for id_, property_, value in triples:
        values_by_property_by_identifier[id_][property_].append(value)
    return values_by_property_by_identifier
