import itertools
import json
import urllib.parse
import warnings
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args

import yaml
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.capabilities import Capability, DataModelInstancesAcl
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.ids import InstanceId
from cognite.client.data_classes.data_modeling.views import SingleEdgeConnection
from cognite.client.exceptions import CogniteAPIError
from pydantic import BaseModel, ValidationInfo, create_model, field_validator
from rdflib import RDF

from cognite.neat._client import NeatClient
from cognite.neat._client._api_client import SchemaAPI
from cognite.neat._constants import DMS_DIRECT_RELATION_LIST_LIMIT, is_readonly_property
from cognite.neat._issues import IssueList, NeatIssue, catch_issues
from cognite.neat._issues.errors import ResourceCreationError, ResourceDuplicatedError, ResourceNotFoundError
from cognite.neat._issues.warnings import (
    PropertyDirectRelationLimitWarning,
    PropertyMultipleValueWarning,
    PropertyTypeNotSupportedWarning,
    ResourceNeatWarning,
)
from cognite.neat._rules.analysis import RulesAnalysis
from cognite.neat._rules.analysis._base import ViewQuery, ViewQueryDict
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.data_types import _DATA_TYPE_BY_DMS_TYPE, Json, String
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._shared import InstanceType
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.auxiliary import create_sha256_hash
from cognite.neat._utils.collection_ import iterate_progress_bar_if_above_config_threshold
from cognite.neat._utils.rdf_ import remove_namespace_from_uri
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.upload import UploadResult

from ._base import _END_OF_CLASS, CDFLoader


@dataclass
class _ViewIterator:
    """This is a helper class to iterate over the views

    Args:
        view_id: The view to iterate over
        instance_count: The number of instances in the view
        hierarchical_properties: The properties that are hierarchical, meaning they point to the same instances.
        query: The query to get the instances from the store.
        view: The view object from the client.
    """

    view_id: dm.ViewId
    instance_count: int
    hierarchical_properties: set[str]
    query: ViewQuery
    view: dm.View | None = None


@dataclass
class _Projection:
    """This is a helper class to project triples to a node and/or edge(s)"""

    view_id: dm.ViewId
    used_for: Literal["node", "edge", "all"]
    pydantic_cls: type[BaseModel]
    edge_by_type: dict[str, tuple[str, dm.EdgeConnection]]
    edge_by_prop_id: dict[str, tuple[str, dm.EdgeConnection]]


class DMSLoader(CDFLoader[dm.InstanceApply]):
    """Loads Instances to Cognite Data Fusion Data Model Service from NeatGraph.

    Args:
        dms_rules (DMSRules): The DMS rules used by the data model.
        info_rules (InformationRules): The information rules used by the data model, used to
            look+up the instances in the store.
        graph_store (NeatGraphStore): The graph store to load the data from.
        instance_space (str): The instance space to load the data into.
        create_issues (Sequence[NeatIssue] | None): A list of issues that occurred during reading. Defaults to None.
        client (NeatClient | None): This is used to lookup containers such that the loader
            creates instances in accordance with required constraints. Defaults to None.
        unquote_external_ids (bool): If True, the loader will unquote external ids before creating the instances.
    """

    def __init__(
        self,
        dms_rules: DMSRules,
        info_rules: InformationRules,
        graph_store: NeatGraphStore,
        instance_space: str,
        space_property: str | None = None,
        client: NeatClient | None = None,
        create_issues: Sequence[NeatIssue] | None = None,
        unquote_external_ids: bool = False,
    ):
        super().__init__(graph_store)
        self.dms_rules = dms_rules
        self.info_rules = info_rules
        self._instance_space = instance_space
        self._space_property = space_property
        self._space_by_uri: dict[str, str] = defaultdict(lambda: instance_space)
        self._issues = IssueList(create_issues or [])
        self._client = client
        self._unquote_external_ids = unquote_external_ids

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

    def _load(self, stop_on_exception: bool = False) -> Iterable[dm.InstanceApply | NeatIssue | type[_END_OF_CLASS]]:
        if self._issues.has_errors and stop_on_exception:
            raise self._issues.as_exception()
        elif self._issues.has_errors:
            yield from self._issues
            return
        view_iterations, issues = self._create_view_iterations()
        yield from issues
        if self._space_property:
            yield from self._lookup_space_by_uri(view_iterations, stop_on_exception)

        for it in view_iterations:
            view = it.view
            if view is None:
                yield ResourceNotFoundError(it.view_id, "view", more=f"Skipping {it.instance_count} instances...")
                continue
            projection, issues = self._create_projection(view)
            yield from issues
            query = it.query
            reader = self.graph_store.read(query.rdf_type, property_renaming_config=query.property_renaming_config)
            instance_iterable = iterate_progress_bar_if_above_config_threshold(
                reader, it.instance_count, f"Loading {it.view_id!r}"
            )
            for identifier, properties in instance_iterable:
                yield from self._create_instances(
                    identifier, properties, projection, stop_on_exception, exclude=it.hierarchical_properties
                )
            if it.hierarchical_properties:
                # Force the creation of instances, before we create the hierarchical properties.
                yield _END_OF_CLASS
                yield from self._create_hierarchical_properties(it, projection, stop_on_exception)

            yield _END_OF_CLASS

    def _create_hierarchical_properties(
        self, it: _ViewIterator, projection: _Projection, stop_on_exception: bool
    ) -> Iterable[dm.InstanceApply | NeatIssue]:
        reader = self.graph_store.read(it.query.rdf_type, property_renaming_config=it.query.property_renaming_config)
        instance_iterable = iterate_progress_bar_if_above_config_threshold(
            reader,
            it.instance_count,
            f"Loading {it.view_id!r} hierarchical properties: {humanize_collection(it.hierarchical_properties)}",
        )
        for identifier, properties in instance_iterable:
            yield from self._create_instances(
                identifier, properties, projection, stop_on_exception, include=it.hierarchical_properties
            )

    def _create_view_iterations(self) -> tuple[list[_ViewIterator], IssueList]:
        view_query_by_id = RulesAnalysis(self.info_rules, self.dms_rules).view_query_by_id
        iterations_by_view_id = self._select_views_with_instances(view_query_by_id)
        if self._client:
            issues = IssueList()
            views = self._client.data_modeling.views.retrieve(
                list(iterations_by_view_id.keys()), include_inherited_properties=True
            )
        else:
            views = dm.ViewList([])
            with catch_issues() as issues:
                read_model = self.dms_rules.as_schema().as_read_model()
                views.extend(read_model.views)
            if issues.has_errors:
                return [], issues
        views_by_id = {view.as_id(): view for view in views}
        hierarchical_properties_by_view_id = SchemaAPI.get_hierarchical_properties(views)

        def sort_by_instance_type(id_: dm.ViewId) -> int:
            if id_ not in views_by_id:
                return 0
            return {"node": 1, "all": 2, "edge": 3}.get(views_by_id[id_].used_for, 0)

        ordered_view_ids = sorted(iterations_by_view_id.keys(), key=sort_by_instance_type)
        view_iterations: list[_ViewIterator] = []
        for view_id in ordered_view_ids:
            if view_id not in iterations_by_view_id:
                continue
            view_iteration = iterations_by_view_id[view_id]
            view_iteration.view = views_by_id.get(view_id)
            view_iteration.hierarchical_properties = hierarchical_properties_by_view_id.get(view_id, set())
            view_iterations.append(view_iteration)
        return view_iterations, issues

    def _select_views_with_instances(self, view_query_by_id: ViewQueryDict) -> dict[dm.ViewId, _ViewIterator]:
        """Selects the views with data."""
        view_iterations: dict[dm.ViewId, _ViewIterator] = {}
        for view_id, query in view_query_by_id.items():
            count = self.graph_store.queries.count_of_type(query.rdf_type)
            if count > 0:
                view_iterations[view_id] = _ViewIterator(view_id, count, set(), query)
        return view_iterations

    def _lookup_space_by_uri(self, view_iterations: list[_ViewIterator], stop_on_exception: bool = False) -> IssueList:
        issues = IssueList()
        if self._space_property is None:
            return issues
        total = sum(it.instance_count for it in view_iterations)
        properties_by_uriref = self.graph_store.queries.properties()
        space_property_uri = next((k for k, v in properties_by_uriref.items() if v == self._space_property), None)
        if space_property_uri is None:
            error: ResourceNotFoundError[str, str] = ResourceNotFoundError(
                self._space_property,
                "property",
                more=f"Could not find the {self._space_property} in the graph.",
            )
            if stop_on_exception:
                raise error
            issues.append(error)
            return issues

        instance_iterable = self.graph_store.queries.list_instances_ids_by_space(space_property_uri)
        instance_iterable = iterate_progress_bar_if_above_config_threshold(
            instance_iterable, total, f"Looking up spaces for {total} instances..."
        )
        for instance, space in instance_iterable:
            self._space_by_uri[remove_namespace_from_uri(instance)] = space
        return issues

    def _create_projection(self, view: dm.View) -> tuple[_Projection, IssueList]:
        issues = IssueList()
        field_definitions: dict[str, tuple[type, Any]] = {}
        edge_by_type: dict[str, tuple[str, dm.EdgeConnection]] = {}
        edge_by_prop_id: dict[str, tuple[str, dm.EdgeConnection]] = {}
        validators: dict[str, classmethod] = {}
        direct_relation_by_property: dict[str, dm.DirectRelation] = {}
        unit_properties: list[str] = []
        json_fields: list[str] = []
        text_fields: list[str] = []
        for prop_id, prop in view.properties.items():
            if isinstance(prop, dm.EdgeConnection):
                if prop.edge_source:
                    # Edges with properties are created separately
                    continue

                edge_by_type[prop.type.external_id] = prop_id, prop
                edge_by_prop_id[prop_id] = prop_id, prop

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
                    elif data_type == String:
                        text_fields.append(prop_id)
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
                if len(value) > 1:
                    warnings.warn(
                        # the identifier is unknown, it will be cest in the create_instances method
                        PropertyMultipleValueWarning("", "property", str(info.field_name), value=str(value[0])),
                        stacklevel=2,
                    )
                elif not value:
                    return None  # type: ignore[return-value]
                return value[0]

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
                    external_ids = (remove_namespace_from_uri(v) for v in value)
                    result = [{"space": self._space_by_uri[e], "externalId": e} for e in external_ids]
                    # Todo: Account for max_list_limit
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
                    external_id = remove_namespace_from_uri(value[0])
                    return {"space": self._space_by_uri[external_id], "externalId": external_id}
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
        return _Projection(view.as_id(), view.used_for, pydantic_cls, edge_by_type, edge_by_prop_id), issues

    def _create_instances(
        self,
        identifier: str,
        properties: dict[str | InstanceType, list[str]],
        projection: _Projection,
        stop_on_exception: bool = False,
        exclude: set[str] | None = None,
        include: set[str] | None = None,
    ) -> Iterable[dm.InstanceApply | NeatIssue]:
        if self._unquote_external_ids:
            identifier = urllib.parse.unquote(identifier)
        start_node, end_node = self._pop_start_end_node(properties)
        is_edge = start_node and end_node
        instance_type = "edge" if is_edge else "node"
        if (projection.used_for == "node" and is_edge) or (projection.used_for == "edge" and not is_edge):
            creation_error = ResourceCreationError(
                identifier,
                instance_type,
                f"View used for {projection.used_for} instance {identifier!s} but is {instance_type}",
            )
            if stop_on_exception:
                raise creation_error from None
            yield creation_error
            return

        if RDF.type not in properties:
            error = ResourceCreationError(identifier, instance_type, "No rdf:type found")
            if stop_on_exception:
                raise error from None
            yield error
            return
        _ = properties.pop(RDF.type)[0]
        if start_node and self._unquote_external_ids:
            start_node = urllib.parse.unquote(start_node)
        if end_node and self._unquote_external_ids:
            end_node = urllib.parse.unquote(end_node)

        if exclude:
            properties = {k: v for k, v in properties.items() if k not in exclude}
        if include:
            properties = {k: v for k, v in properties.items() if k in include}

        with catch_issues() as property_issues:
            sources = [
                dm.NodeOrEdgeData(
                    projection.view_id,
                    projection.pydantic_cls.model_validate(properties).model_dump(exclude_unset=True),
                )
            ]
        for issue in property_issues:
            if isinstance(issue, ResourceNeatWarning):
                issue.identifier = identifier

        if property_issues.has_errors and stop_on_exception:
            raise property_issues.as_exception()
        yield from property_issues

        if start_node and end_node:
            yield dm.EdgeApply(
                space=self._space_by_uri[identifier],
                external_id=identifier,
                type=(projection.view_id.space, projection.view_id.external_id),
                start_node=(self._space_by_uri[start_node], start_node),
                end_node=(self._space_by_uri[end_node], end_node),
                sources=sources,
            )
        else:
            yield dm.NodeApply(
                space=self._space_by_uri[identifier],
                external_id=identifier,
                type=(projection.view_id.space, projection.view_id.external_id),
                sources=sources,
            )
        yield from self._create_edges_without_properties(identifier, properties, projection)

    def _create_edges_without_properties(
        self, identifier: str, properties: dict[str | InstanceType, list[str]], projection: _Projection
    ) -> Iterable[dm.EdgeApply | NeatIssue]:
        for predicate, values in properties.items():
            if predicate in projection.edge_by_type:
                prop_id, edge = projection.edge_by_type[predicate]
            elif predicate in projection.edge_by_prop_id:
                prop_id, edge = projection.edge_by_prop_id[predicate]
            else:
                continue
            if isinstance(edge, SingleEdgeConnection) and len(values) > 1:
                error = ResourceDuplicatedError(
                    resource_type="edge",
                    identifier=identifier,
                    location=f"Multiple values for single edge {edge}. Expected only one.",
                )
                yield error
                continue
            for target in values:
                external_id = f"{identifier}.{prop_id}.{target}"
                start_node, end_node = (
                    (self._space_by_uri[identifier], identifier),
                    (self._space_by_uri[target], target),
                )
                if edge.direction == "inwards":
                    start_node, end_node = end_node, start_node
                yield dm.EdgeApply(
                    space=self._space_by_uri[identifier],
                    external_id=(external_id if len(external_id) < 256 else create_sha256_hash(external_id)),
                    type=edge.type,
                    start_node=start_node,
                    end_node=end_node,
                )

    @staticmethod
    def _pop_start_end_node(properties: dict[str | InstanceType, list[str]]) -> tuple[str, str] | tuple[None, None]:
        start_node = properties.pop("startNode", [None])[0]
        if not start_node:
            start_node = properties.pop("start_node", [None])[0]
        end_node = properties.pop("endNode", [None])[0]
        if not end_node:
            end_node = properties.pop("end_node", [None])[0]
        if start_node and end_node:
            return start_node, end_node
        return None, None

    def _get_required_capabilities(self) -> list[Capability]:
        return [
            DataModelInstancesAcl(
                actions=[
                    DataModelInstancesAcl.Action.Write,
                    DataModelInstancesAcl.Action.Write_Properties,
                    DataModelInstancesAcl.Action.Read,
                ],
                scope=DataModelInstancesAcl.Scope.SpaceID([self._instance_space]),
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
