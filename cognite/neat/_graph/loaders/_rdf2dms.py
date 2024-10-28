import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, get_args

import yaml
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.capabilities import Capability, DataModelInstancesAcl
from cognite.client.data_classes.data_modeling import ViewId
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.ids import InstanceId
from cognite.client.data_classes.data_modeling.views import SingleEdgeConnection
from cognite.client.exceptions import CogniteAPIError
from pydantic import BaseModel, ValidationInfo, create_model, field_validator
from rdflib import RDF

from cognite.neat._graph._tracking import LogTracker, Tracker
from cognite.neat._graph.models import InstanceType
from cognite.neat._issues import IssueList, NeatIssue, NeatIssueList
from cognite.neat._issues.errors import (
    ResourceConvertionError,
    ResourceCreationError,
    ResourceDuplicatedError,
    ResourceRetrievalError,
)
from cognite.neat._issues.warnings import PropertyTypeNotSupportedWarning
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.data_types import _DATA_TYPE_BY_DMS_TYPE, Json
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.auxiliary import create_sha256_hash
from cognite.neat._utils.upload import UploadResult

from ._base import CDFLoader


class DMSLoader(CDFLoader[dm.InstanceApply]):
    """Loads Instances to Cognite Data Fusion Data Model Service from NeatGraph.

    Args:
        graph_store (NeatGraphStore): The graph store to load the data into.
        data_model (dm.DataModel[dm.View] | None): The data model to load.
        instance_space (str): The instance space to load the data into.
        class_by_view_id (dict[ViewId, str] | None): A mapping from view id to class name. Defaults to None.
        create_issues (Sequence[NeatIssue] | None): A list of issues that occurred during reading. Defaults to None.
        tracker (type[Tracker] | None): The tracker to use. Defaults to None.
    """

    def __init__(
        self,
        graph_store: NeatGraphStore,
        data_model: dm.DataModel[dm.View] | None,
        instance_space: str,
        class_by_view_id: dict[ViewId, str] | None = None,
        create_issues: Sequence[NeatIssue] | None = None,
        tracker: type[Tracker] | None = None,
    ):
        super().__init__(graph_store)
        self.data_model = data_model
        self.instance_space = instance_space
        self.class_by_view_id = class_by_view_id or {}
        self._issues = IssueList(create_issues or [])
        self._tracker: type[Tracker] = tracker or LogTracker

    @classmethod
    def from_data_model_id(
        cls,
        client: CogniteClient,
        data_model_id: dm.DataModelId,
        graph_store: NeatGraphStore,
        instance_space: str,
    ) -> "DMSLoader":
        issues: list[NeatIssue] = []
        data_model: dm.DataModel[dm.View] | None = None
        try:
            data_model = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True).latest_version()
        except Exception as e:
            issues.append(ResourceRetrievalError(data_model_id, "data model", str(e)))

        return cls(graph_store, data_model, instance_space, {}, issues)

    @classmethod
    def from_rules(cls, rules: DMSRules, graph_store: NeatGraphStore, instance_space: str) -> "DMSLoader":
        issues: list[NeatIssue] = []
        data_model: dm.DataModel[dm.View] | None = None
        try:
            data_model = rules.as_schema().as_read_model()
        except Exception as e:
            issues.append(
                ResourceConvertionError(
                    identifier=rules.metadata.as_identifier(),
                    resource_type="DMS Rules",
                    target_format="read DMS model",
                    reason=str(e),
                )
            )
        return cls(graph_store, data_model, instance_space, {}, issues)

    def _load(self, stop_on_exception: bool = False) -> Iterable[dm.InstanceApply | NeatIssue]:
        if self._issues.has_errors and stop_on_exception:
            raise self._issues.as_exception()
        elif self._issues.has_errors:
            yield from self._issues
            return
        if not self.data_model:
            # There should already be an error in this case.
            return
        view_ids = [repr(v.as_id()) for v in self.data_model.views]
        tracker = self._tracker(type(self).__name__, view_ids, "views")
        for view in self.data_model.views:
            view_id = view.as_id()
            tracker.start(repr(view_id))
            pydantic_cls, edge_by_type, issues = self._create_validation_classes(view)  # type: ignore[var-annotated]
            yield from issues
            tracker.issue(issues)
            class_name = self.class_by_view_id.get(view.as_id(), view.external_id)

            for identifier, properties in self.graph_store.read(class_name):
                try:
                    yield self._create_node(identifier, properties, pydantic_cls, view_id)
                except ValueError as e:
                    error = ResourceCreationError(identifier, "node", error=str(e))
                    tracker.issue(error)
                    if stop_on_exception:
                        raise error from e
                    yield error
                yield from self._create_edges(identifier, properties, edge_by_type, tracker)
            tracker.finish(repr(view_id))

    def write_to_file(self, filepath: Path) -> None:
        if filepath.suffix not in [".json", ".yaml", ".yml"]:
            raise ValueError(f"File format {filepath.suffix} is not supported")
        dumped: dict[str, list] = {"nodes": [], "edges": [], "issues": []}
        for item in self.load(stop_on_exception=False):
            key = {
                dm.NodeApply: "nodes",
                dm.EdgeApply: "edges",
                NeatIssue: "issues",
            }.get(type(item))
            if key is None:
                # This should never happen, and is a bug in neat
                raise ValueError(f"Item {item} is not supported. This is a bug in neat please report it.")
            dumped[key].append(item.dump())
        with filepath.open("w", encoding=self._encoding, newline=self._new_line) as f:
            if filepath.suffix == ".json":
                json.dump(dumped, f, indent=2)
            else:
                yaml.safe_dump(dumped, f, sort_keys=False)

    def _create_validation_classes(
        self, view: dm.View
    ) -> tuple[type[BaseModel], dict[str, tuple[str, dm.EdgeConnection]], NeatIssueList]:
        issues = IssueList()
        field_definitions: dict[str, tuple[type, Any]] = {}
        edge_by_property: dict[str, tuple[str, dm.EdgeConnection]] = {}
        validators: dict[str, classmethod] = {}
        direct_relation_by_property: dict[str, dm.DirectRelation] = {}
        json_fields: list[str] = []
        for prop_name, prop in view.properties.items():
            if isinstance(prop, dm.EdgeConnection):
                edge_by_property[prop.type.external_id] = prop_name, prop
            if isinstance(prop, dm.MappedProperty):
                if isinstance(prop.type, dm.DirectRelation):
                    direct_relation_by_property[prop_name] = prop.type
                    python_type: Any = dict
                else:
                    data_type = _DATA_TYPE_BY_DMS_TYPE.get(prop.type._type)
                    if not data_type:
                        issues.append(
                            PropertyTypeNotSupportedWarning(
                                view.as_id(),
                                "view",
                                prop_name,
                                prop.type._type,
                            )
                        )
                        continue

                    if data_type == Json:
                        json_fields.append(prop_name)
                    python_type = data_type.python
                if isinstance(prop.type, ListablePropertyType) and prop.type.is_list:
                    python_type = list[python_type]
                default_value: Any = prop.default_value
                if prop.nullable:
                    python_type = python_type | None
                else:
                    default_value = ...

                field_definitions[prop_name] = (python_type, default_value)

        def parse_list(cls, value: Any, info: ValidationInfo) -> list[str]:
            if isinstance(value, list) and list.__name__ not in _get_field_value_types(cls, info):
                if len(value) == 1:
                    return value[0]
                raise ValueError(f"Got multiple values for {info.field_name}: {value}")

            return value

        def parse_json_string(cls, value: Any, info: ValidationInfo) -> dict:
            if isinstance(value, dict):
                return value
            elif isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError as error:
                    raise ValueError(f"Not valid JSON string for {info.field_name}: {value}, error {error}") from error
            else:
                raise ValueError(f"Expect valid JSON string or dict for {info.field_name}: {value}")

        if json_fields:
            validators["parse_json_string"] = field_validator(*json_fields, mode="before")(parse_json_string)  # type: ignore[assignment, arg-type]

        validators["parse_list"] = field_validator("*", mode="before")(parse_list)  # type: ignore[assignment, arg-type]

        if direct_relation_by_property:

            def parse_direct_relation(cls, value: list, info: ValidationInfo) -> dict | list[dict]:
                # We validate above that we only get one value for single direct relations.
                if list.__name__ in _get_field_value_types(cls, info):
                    return [{"space": self.instance_space, "externalId": v} for v in value]
                elif value:
                    return {"space": self.instance_space, "externalId": value[0]}
                return {}

            validators["parse_direct_relation"] = field_validator(*direct_relation_by_property.keys(), mode="before")(  # type: ignore[assignment]
                parse_direct_relation  # type: ignore[arg-type]
            )

        pydantic_cls = create_model(view.external_id, __validators__=validators, **field_definitions)  # type: ignore[arg-type, call-overload]
        return pydantic_cls, edge_by_property, issues

    def _create_node(
        self,
        identifier: str,
        properties: dict[str | InstanceType, list[str]],
        pydantic_cls: type[BaseModel],
        view_id: dm.ViewId,
    ) -> dm.InstanceApply:
        type_ = properties.pop(RDF.type, [None])[0]
        created = pydantic_cls.model_validate(properties)

        return dm.NodeApply(
            space=self.instance_space,
            external_id=identifier,
            type=dm.DirectRelationReference(view_id.space, type_) if type_ is not None else None,
            sources=[dm.NodeOrEdgeData(source=view_id, properties=dict(created.model_dump().items()))],
        )

    def _create_edges(
        self,
        identifier: str,
        properties: dict[str, list[str]],
        edge_by_type: dict[str, tuple[str, dm.EdgeConnection]],
        tracker: Tracker,
    ) -> Iterable[dm.EdgeApply | NeatIssue]:
        for predicate, values in properties.items():
            if predicate not in edge_by_type:
                continue
            prop_id, edge = edge_by_type[predicate]
            if isinstance(edge, SingleEdgeConnection) and len(values) > 1:
                error = ResourceDuplicatedError(
                    resource_type="edge",
                    identifier=identifier,
                    location=f"Multiple values for single edge {edge}. Expected only one.",
                )
                tracker.issue(error)
                yield error
            for target in values:
                external_id = f"{identifier}.{prop_id}.{target}"
                yield dm.EdgeApply(
                    space=self.instance_space,
                    external_id=(external_id if len(external_id) < 256 else create_sha256_hash(external_id)),
                    type=edge.type,
                    start_node=dm.DirectRelationReference(self.instance_space, identifier),
                    end_node=dm.DirectRelationReference(self.instance_space, target),
                )

    def _get_required_capabilities(self) -> list[Capability]:
        return [
            DataModelInstancesAcl(
                actions=[
                    DataModelInstancesAcl.Action.Write,
                    DataModelInstancesAcl.Action.Write_Properties,
                    DataModelInstancesAcl.Action.Read,
                ],
                scope=DataModelInstancesAcl.Scope.SpaceID([self.instance_space]),
            )
        ]

    def _upload_to_cdf(
        self,
        client: CogniteClient,
        items: list[dm.InstanceApply],
        dry_run: bool,
        read_issues: NeatIssueList,
    ) -> Iterable[UploadResult]:
        try:
            nodes = [item for item in items if isinstance(item, dm.NodeApply)]
            edges = [item for item in items if isinstance(item, dm.EdgeApply)]
            upserted = client.data_modeling.instances.apply(
                nodes,
                edges,
                auto_create_end_nodes=True,
                auto_create_start_nodes=True,
                skip_on_version_conflict=True,
            )
        except CogniteAPIError as e:
            result = UploadResult[InstanceId](name="Instances", issues=read_issues)
            result.error_messages.append(str(e))
            result.failed_upserted.update(item.as_id() for item in e.failed + e.unknown)
            result.created.update(item.as_id() for item in e.successful)
            yield result
        else:
            for instance_type, instances in {
                "Nodes": upserted.nodes,
                "Edges": upserted.edges,
            }.items():
                result = UploadResult[InstanceId](name=instance_type, issues=read_issues)
                for instance in instances:  # type: ignore[attr-defined]
                    if instance.was_modified and instance.created_time == instance.last_updated_time:
                        result.created.add(instance.as_id())
                    elif instance.was_modified:
                        result.changed.add(instance.as_id())
                    else:
                        result.unchanged.add(instance.as_id())
                yield result


def _get_field_value_types(cls, info):
    return [type_.__name__ for type_ in get_args(cls.model_fields[info.field_name].annotation)]
