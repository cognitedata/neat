import itertools
import json
import warnings
from collections import defaultdict
from collections.abc import Iterable, Sequence
from graphlib import TopologicalSorter
from pathlib import Path
from typing import Any, cast, get_args

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
from rdflib import RDF, URIRef

from cognite.neat._client import NeatClient
from cognite.neat._constants import DMS_DIRECT_RELATION_LIST_LIMIT, is_readonly_property
from cognite.neat._graph._tracking import LogTracker, Tracker
from cognite.neat._issues import IssueList, NeatIssue, NeatIssueList
from cognite.neat._issues.errors import (
    ResourceConversionError,
    ResourceCreationError,
    ResourceDuplicatedError,
    ResourceRetrievalError,
)
from cognite.neat._issues.warnings import PropertyDirectRelationLimitWarning, PropertyTypeNotSupportedWarning
from cognite.neat._rules.analysis._dms import DMSAnalysis
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.data_types import _DATA_TYPE_BY_DMS_TYPE, Json
from cognite.neat._rules.models.entities._single_value import ViewEntity
from cognite.neat._shared import InstanceType
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.auxiliary import create_sha256_hash
from cognite.neat._utils.rdf_ import remove_namespace_from_uri
from cognite.neat._utils.upload import UploadResult

from ._base import _END_OF_CLASS, CDFLoader


class DMSLoader(CDFLoader[dm.InstanceApply]):
    """Loads Instances to Cognite Data Fusion Data Model Service from NeatGraph.

    Args:
        graph_store (NeatGraphStore): The graph store to load the data into.
        data_model (dm.DataModel[dm.View] | None): The data model to load.
        instance_space (str): The instance space to load the data into.
        class_neat_id_by_view_id (dict[ViewId, URIRef] | None): A mapping from view id to class name. Defaults to None.
        create_issues (Sequence[NeatIssue] | None): A list of issues that occurred during reading. Defaults to None.
        tracker (type[Tracker] | None): The tracker to use. Defaults to None.
        rules (DMSRules | None): The DMS rules used by the data model. This is used to lookup the
            instances in the store. Defaults to None.
        client (NeatClient | None): This is used to lookup containers such that the loader
            creates instances in accordance with required constraints. Defaults to None.
    """

    def __init__(
        self,
        graph_store: NeatGraphStore,
        data_model: dm.DataModel[dm.View] | None,
        instance_space: str,
        class_neat_id_by_view_id: dict[ViewId, URIRef] | None = None,
        create_issues: Sequence[NeatIssue] | None = None,
        tracker: type[Tracker] | None = None,
        rules: DMSRules | None = None,
        client: NeatClient | None = None,
    ):
        super().__init__(graph_store)
        self.data_model = data_model
        self.instance_space = instance_space
        self.class_neat_id_by_view_id = class_neat_id_by_view_id or {}
        self._issues = IssueList(create_issues or [])
        self._tracker: type[Tracker] = tracker or LogTracker
        self.rules = rules
        self._client = client

    @classmethod
    def from_data_model_id(
        cls,
        client: NeatClient,
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

        return cls(graph_store, data_model, instance_space, {}, issues, client=client)

    @classmethod
    def from_rules(
        cls, rules: DMSRules, graph_store: NeatGraphStore, instance_space: str, client: NeatClient | None = None
    ) -> "DMSLoader":
        issues: list[NeatIssue] = []
        data_model: dm.DataModel[dm.View] | None = None
        try:
            data_model = rules.as_schema().as_read_model()
        except Exception as e:
            issues.append(
                ResourceConversionError(
                    identifier=rules.metadata.as_identifier(),
                    resource_type="DMS Rules",
                    target_format="read DMS model",
                    reason=str(e),
                )
            )

        class_neat_id_by_view_id = {view.view.as_id(): view.logical for view in rules.views if view.logical}

        return cls(
            graph_store,
            data_model,
            instance_space,
            class_neat_id_by_view_id,
            issues,
            rules=rules,
            client=client,
        )

    def _load(self, stop_on_exception: bool = False) -> Iterable[dm.InstanceApply | NeatIssue | type[_END_OF_CLASS]]:
        if self._issues.has_errors and stop_on_exception:
            raise self._issues.as_exception()
        elif self._issues.has_errors:
            yield from self._issues
            return
        if not self.data_model:
            # There should already be an error in this case.
            return

        views_with_linked_properties = (
            DMSAnalysis(self.rules).views_with_properties_linked_to_classes(consider_inheritance=True)
            if self.rules and self.rules.metadata.logical
            else None
        )
        view_and_count_by_id = self._select_views_with_instances(self.data_model.views)
        if self._client:
            view_and_count_by_id, properties_point_to_self = self._sort_by_direct_relation_dependencies(
                view_and_count_by_id
            )
        else:
            properties_point_to_self = {}

        view_ids: list[str] = []
        for view_id in view_and_count_by_id.keys():
            view_ids.append(repr(view_id))
            if view_id in properties_point_to_self:
                # If the views have a dependency on themselves, we need to run it twice.
                view_ids.append(f"{view_id!r} (self)")

        tracker = self._tracker(type(self).__name__, view_ids, "views")
        for view_id, (view, _) in view_and_count_by_id.items():
            pydantic_cls, edge_by_type, issues = self._create_validation_classes(view)  # type: ignore[var-annotated]
            yield from issues
            tracker.issue(issues)

            if view_id in properties_point_to_self:
                # If the view has a dependency on itself, we need to run it twice.
                # First, to ensure that all nodes are created, and then to add the direct relations.
                # This only applies if there is a require constraint on the container, if not
                # we can create an empty node on the fly.
                iterations = [properties_point_to_self[view_id], set()]
            else:
                iterations = [set()]

            for skip_properties in iterations:
                if skip_properties:
                    track_id = f"{view_id} (self)"
                else:
                    track_id = repr(view_id)
                tracker.start(track_id)
                if views_with_linked_properties:
                    # we need graceful exit if the view is not in the view_property_pairs
                    property_link_pairs = views_with_linked_properties.get(ViewEntity.from_id(view_id))

                    if class_neat_id := self.class_neat_id_by_view_id.get(view_id):
                        reader = self.graph_store._read_via_rules_linkage(class_neat_id, property_link_pairs)
                    else:
                        error_view = ResourceRetrievalError(view_id, "view", "View not linked to class")
                        tracker.issue(error_view)
                        if stop_on_exception:
                            raise error_view
                        yield error_view
                        continue
                else:
                    # this assumes no changes in the suffix of view and class
                    reader = self.graph_store.read(view.external_id)

                for identifier, properties in reader:
                    if skip_properties:
                        properties = {k: v for k, v in properties.items() if k not in skip_properties}
                    try:
                        yield self._create_node(identifier, properties, pydantic_cls, view_id)
                    except ValueError as e:
                        error_node = ResourceCreationError(identifier, "node", error=str(e))
                        tracker.issue(error_node)
                        if stop_on_exception:
                            raise error_node from e
                        yield error_node
                    yield from self._create_edges(identifier, properties, edge_by_type, tracker)
                tracker.finish(track_id)
                yield _END_OF_CLASS

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

    def _select_views_with_instances(self, views: list[dm.View]) -> dict[dm.ViewId, tuple[dm.View, int]]:
        """Selects the views with data."""
        view_and_count_by_id: dict[dm.ViewId, tuple[dm.View, int]] = {}
        uri_by_type: dict[str, URIRef] = {
            remove_namespace_from_uri(uri[0]): uri[0]  # type: ignore[misc]
            for uri in self.graph_store.queries.list_types()
        }
        for view in views:
            view_id = view.as_id()
            neat_id = self.class_neat_id_by_view_id.get(view_id)
            if neat_id is not None:
                count = self.graph_store.count_of_id(neat_id)
            elif view.external_id in uri_by_type:
                count = self.graph_store.count_of_type(uri_by_type[view.external_id])
            else:
                continue
            if count > 0:
                view_and_count_by_id[view_id] = view, count

        return view_and_count_by_id

    def _sort_by_direct_relation_dependencies(
        self, view_and_count_by_id: dict[dm.ViewId, tuple[dm.View, int]]
    ) -> tuple[dict[dm.ViewId, tuple[dm.View, int]], dict[dm.ViewId, set[str]]]:
        """Sorts the views by container constraints."""
        if not self._client:
            return view_and_count_by_id, {}
        # We need to retrieve the views to ensure we get all properties, such that we can find all
        # the containers that the view is linked to.
        views = self._client.data_modeling.views.retrieve(
            list(view_and_count_by_id.keys()), include_inherited_properties=True
        )
        container_ids_by_view_id = {view.as_id(): view.referenced_containers() for view in views}
        referenced_containers = {
            container for containers in container_ids_by_view_id.values() for container in containers
        }
        containers = self._client.data_modeling.containers.retrieve(list(referenced_containers))
        container_by_id = {container.as_id(): container for container in containers}

        dependency_on_self: dict[dm.ViewId, set[str]] = defaultdict(set)
        view_id_by_dependencies: dict[dm.ViewId, set[dm.ViewId]] = {}
        for view in views:
            view_id = view.as_id()
            dependencies = set()
            for prop_id, prop in view.properties.items():
                if isinstance(prop, dm.MappedProperty) and isinstance(prop.type, dm.DirectRelation) and prop.source:
                    container = container_by_id[prop.container]
                    has_require_constraint = any(
                        isinstance(constraint, dm.RequiresConstraint) for constraint in container.constraints.values()
                    )
                    if has_require_constraint and prop.source == view_id:
                        dependency_on_self[view_id].add(prop_id)
                    elif has_require_constraint:
                        dependencies.add(prop.source)
            view_id_by_dependencies[view_id] = dependencies

        ordered_view_ids = TopologicalSorter(view_id_by_dependencies).static_order()

        return {
            view_id: view_and_count_by_id[view_id] for view_id in ordered_view_ids if view_id in view_and_count_by_id
        }, dict(dependency_on_self)

    def _create_validation_classes(
        self, view: dm.View
    ) -> tuple[type[BaseModel], dict[str, tuple[str, dm.EdgeConnection]], NeatIssueList]:
        issues = IssueList()
        field_definitions: dict[str, tuple[type, Any]] = {}
        edge_by_property: dict[str, tuple[str, dm.EdgeConnection]] = {}
        validators: dict[str, classmethod] = {}
        direct_relation_by_property: dict[str, dm.DirectRelation] = {}
        unit_properties: list[str] = []
        json_fields: list[str] = []
        for prop_id, prop in view.properties.items():
            if isinstance(prop, dm.EdgeConnection):
                edge_by_property[prop_id] = prop_id, prop
            if isinstance(prop, dm.MappedProperty):
                if is_readonly_property(prop.container, prop.container_property_identifier):
                    continue

                if isinstance(prop.type, dm.DirectRelation):
                    if prop.container == dm.ContainerId("cdf_cdm", "CogniteTimeSeries") and prop_id == "unit":
                        unit_properties.append(prop_id)
                    else:
                        direct_relation_by_property[prop_id] = prop.type
                    python_type: Any = dict
                else:
                    data_type = _DATA_TYPE_BY_DMS_TYPE.get(prop.type._type)
                    if not data_type:
                        issues.append(
                            PropertyTypeNotSupportedWarning(
                                view.as_id(),
                                "view",
                                prop_id,
                                prop.type._type,
                            )
                        )
                        continue

                    if data_type == Json:
                        json_fields.append(prop_id)
                    python_type = data_type.python
                if isinstance(prop.type, ListablePropertyType) and prop.type.is_list:
                    python_type = list[python_type]
                default_value: Any = prop.default_value
                if prop.nullable:
                    python_type = python_type | None
                else:
                    default_value = ...

                field_definitions[prop_id] = (python_type, default_value)

        def parse_list(cls, value: Any, info: ValidationInfo) -> list[str]:
            if isinstance(value, list) and list.__name__ not in _get_field_value_types(cls, info):
                if len(value) == 1:
                    return value[0]
                raise ValueError(f"Got multiple values for {info.field_name}: {value}")

            return value

        def parse_json_string(cls, value: Any, info: ValidationInfo) -> dict | list:
            if isinstance(value, dict):
                return value
            elif isinstance(value, list):
                try:
                    return [json.loads(v) if isinstance(v, str) else v for v in value]
                except json.JSONDecodeError as error:
                    raise ValueError(f"Not valid JSON string for {info.field_name}: {value}, error {error}") from error
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
                    result = [{"space": self.instance_space, "externalId": remove_namespace_from_uri(v)} for v in value]
                    if len(result) <= DMS_DIRECT_RELATION_LIST_LIMIT:
                        return result
                    warnings.warn(
                        PropertyDirectRelationLimitWarning(
                            identifier="unknown",
                            resource_type="view property",
                            property_name=cast(str, cls.model_fields[info.field_name].alias or info.field_name),
                            limit=DMS_DIRECT_RELATION_LIST_LIMIT,
                        ),
                        stacklevel=2,
                    )
                    # To get deterministic results, we sort by space and externalId
                    result.sort(key=lambda x: (x["space"], x["externalId"]))
                    return result[:DMS_DIRECT_RELATION_LIST_LIMIT]
                elif value:
                    return {"space": self.instance_space, "externalId": remove_namespace_from_uri(value[0])}
                return {}

            validators["parse_direct_relation"] = field_validator(*direct_relation_by_property.keys(), mode="before")(  # type: ignore[assignment]
                parse_direct_relation  # type: ignore[arg-type]
            )

        if unit_properties:

            def parse_direct_relation_to_unit(cls, value: Any, info: ValidationInfo) -> dict | list[dict]:
                if value:
                    return {"space": "cdf_cdm_units", "externalId": remove_namespace_from_uri(value[0])}
                return {}

            validators["parse_direct_relation_to_unit"] = field_validator(*unit_properties, mode="before")(  # type: ignore[assignment]
                parse_direct_relation_to_unit  # type: ignore[arg-type]
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
            type=(dm.DirectRelationReference(view_id.space, view_id.external_id) if type_ is not None else None),
            sources=[
                dm.NodeOrEdgeData(source=view_id, properties=dict(created.model_dump(exclude_unset=True).items()))
            ],
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
        read_issues: IssueList,
    ) -> Iterable[UploadResult]:
        nodes: list[dm.NodeApply] = []
        edges: list[dm.EdgeApply] = []
        source_by_node_id: dict[dm.NodeId, str] = {}
        source_by_edge_id: dict[dm.EdgeId, str] = {}
        for item in items:
            if isinstance(item, dm.NodeApply):
                nodes.append(item)
                if item.sources:
                    source_by_node_id[item.as_id()] = item.sources[0].source.external_id
                else:
                    source_by_node_id[item.as_id()] = "node"
            elif isinstance(item, dm.EdgeApply):
                edges.append(item)
                if item.sources:
                    source_by_edge_id[item.as_id()] = item.sources[0].source.external_id
                else:
                    source_by_edge_id[item.as_id()] = "edge"
        try:
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
            for instances, ids_by_source in [
                (upserted.nodes, source_by_node_id),
                (upserted.edges, source_by_edge_id),
            ]:
                for name, subinstances in itertools.groupby(
                    sorted(instances, key=lambda i: ids_by_source.get(i.as_id(), "")),  # type: ignore[call-overload, index, attr-defined]
                    key=lambda i: ids_by_source.get(i.as_id(), ""),  # type: ignore[index, attr-defined]
                ):
                    result = UploadResult(name=name, issues=read_issues)
                    for instance in subinstances:  # type: ignore[attr-defined]
                        if instance.was_modified and instance.created_time == instance.last_updated_time:
                            result.created.add(instance.as_id())
                        elif instance.was_modified:
                            result.changed.add(instance.as_id())
                        else:
                            result.unchanged.add(instance.as_id())
                    yield result


def _get_field_value_types(cls, info):
    return [type_.__name__ for type_ in get_args(cls.model_fields[info.field_name].annotation)]
