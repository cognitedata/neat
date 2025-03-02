import itertools
import json
import urllib.parse
import warnings
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args, overload

import yaml
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.capabilities import Capability, DataModelInstancesAcl
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.ids import InstanceId
from cognite.client.data_classes.data_modeling.views import SingleEdgeConnection
from cognite.client.exceptions import CogniteAPIError
from pydantic import BaseModel, ValidationInfo, create_model, field_validator
from rdflib import RDF, URIRef

from cognite.neat._client import NeatClient
from cognite.neat._client._api_client import SchemaAPI
from cognite.neat._constants import DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT, is_readonly_property
from cognite.neat._issues import IssueList, NeatError, NeatIssue, catch_issues
from cognite.neat._issues.errors import (
    AuthorizationError,
    ResourceCreationError,
    ResourceDuplicatedError,
    ResourceNotFoundError,
)
from cognite.neat._issues.warnings import (
    NeatValueWarning,
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
from cognite.neat._utils.rdf_ import namespace_as_space, remove_namespace_from_uri, split_uri
from cognite.neat._utils.text import NamingStandardization
from cognite.neat._utils.upload import UploadResult

from ._base import _END_OF_CLASS, _START_OF_CLASS, CDFLoader


@dataclass
class _ViewIterator:
    """This is a helper class to iterate over the views

    Args:
        view_id: The view to iterate over
        instance_count: The number of instances in the view
        query: The query to get the instances from the store.
        view: The view object from the client.
    """

    view_id: dm.ViewId
    instance_count: int
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
        neat_prefix_by_predicate_uri (dict[URIRef, str] | None): A dictionary that maps a predicate URIRef to a
            prefix that Neat added to the object upon extraction. This is used to remove the prefix from the
            object before creating the instance.
    """

    def __init__(
        self,
        dms_rules: DMSRules,
        info_rules: InformationRules,
        graph_store: NeatGraphStore,
        instance_space: str,
        space_property: str | None = None,
        use_source_space: bool = False,
        client: NeatClient | None = None,
        create_issues: Sequence[NeatIssue] | None = None,
        unquote_external_ids: bool = False,
        neat_prefix_by_predicate_uri: dict[URIRef, str] | None = None,
        neat_prefix_by_type_uri: dict[URIRef, str] | None = None,
    ):
        super().__init__(graph_store)
        self.dms_rules = dms_rules
        self.info_rules = info_rules
        self.neat_prefix_by_predicate_uri = neat_prefix_by_predicate_uri or {}
        self.neat_prefix_by_type_uri = neat_prefix_by_type_uri or {}
        self._instance_space = instance_space
        self._space_property = space_property
        self._use_source_space = use_source_space
        self._space_by_instance_uri: dict[URIRef, str] = defaultdict(lambda: instance_space)
        self._external_id_by_uri: dict[URIRef, str] = {}
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

    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[dm.InstanceApply | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        if self._issues.has_errors and stop_on_exception:
            raise self._issues.as_exception()
        elif self._issues.has_errors:
            yield from self._issues
            return
        view_iterations, issues = self._create_view_iterations()
        yield from issues
        if self._space_property:
            yield from self._lookup_space_by_uri(view_iterations, stop_on_exception)

            if self._client:
                space_creation = self._create_instance_space_if_not_exists()
                yield from space_creation.warnings
                if space_creation.has_errors and stop_on_exception:
                    raise space_creation.as_exception()
                yield from space_creation.errors

        if self.neat_prefix_by_type_uri:
            self._lookup_identifier_by_uri()

        for it in view_iterations:
            view = it.view
            if view is None:
                yield ResourceNotFoundError(it.view_id, "view", more=f"Skipping {it.instance_count} instances...")
                continue
            projection, issues = self._create_projection(view)
            yield from issues
            query = it.query
            reader = self.graph_store.read(
                query.rdf_type,
                property_renaming_config=query.property_renaming_config,
                remove_uri_namespace=False,
            )
            instance_iterable = iterate_progress_bar_if_above_config_threshold(
                reader, it.instance_count, f"Loading {it.view_id!r}"
            )
            yield _START_OF_CLASS(view.external_id)
            for identifier, properties in instance_iterable:
                yield from self._create_instances(identifier, properties, projection, stop_on_exception)
            if reader is instance_iterable:
                print(f"Loaded {it.instance_count} instances for {it.view_id!r}")

            yield _END_OF_CLASS

    def _create_view_iterations(self) -> tuple[list[_ViewIterator], IssueList]:
        view_query_by_id = RulesAnalysis(self.info_rules, self.dms_rules).view_query_by_id
        iterations_by_view_id = self._select_views_with_instances(view_query_by_id)
        if self._client:
            issues = IssueList()
            views = self._client.data_modeling.views.retrieve(
                list(iterations_by_view_id.keys()), include_inherited_properties=True
            )
            if missing := set(iterations_by_view_id) - {view.as_id() for view in views}:
                for missing_view in missing:
                    issues.append(ResourceNotFoundError(missing_view, "view", more="The view is not found in CDF."))
                return [], issues
        else:
            views = dm.ViewList([])
            with catch_issues() as issues:
                read_model = self.dms_rules.as_schema().as_read_model()
                views.extend(read_model.views)
            if issues.has_errors:
                return [], issues
        views_by_id = {view.as_id(): view for view in views}

        def sort_by_instance_type(id_: dm.ViewId) -> int:
            if id_ not in views_by_id:
                return 0
            return {"node": 1, "all": 1, "edge": 3}.get(views_by_id[id_].used_for, 0)

        ordered_view_ids = SchemaAPI.get_view_order_by_direct_relation_constraints(views)
        # Sort is stable in Python, so we will keep the order of the views:
        ordered_view_ids.sort(key=sort_by_instance_type)
        view_iterations: list[_ViewIterator] = []
        for view_id in ordered_view_ids:
            if view_id not in iterations_by_view_id:
                continue
            view_iteration = iterations_by_view_id[view_id]
            view_iteration.view = views_by_id.get(view_id)
            view_iterations.append(view_iteration)
        return view_iterations, issues

    def _select_views_with_instances(self, view_query_by_id: ViewQueryDict) -> dict[dm.ViewId, _ViewIterator]:
        """Selects the views with data."""
        view_iterations: dict[dm.ViewId, _ViewIterator] = {}
        for view_id, query in view_query_by_id.items():
            count = self.graph_store.queries.count_of_type(query.rdf_type)
            if count > 0:
                view_iterations[view_id] = _ViewIterator(view_id, count, query)
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
        neat_prefix = self.neat_prefix_by_predicate_uri.get(space_property_uri)
        warned_spaces: set[str] = set()
        for instance, space in instance_iterable:
            if neat_prefix:
                space = space.removeprefix(neat_prefix)

            clean_space = NamingStandardization.standardize_space_str(space)
            if clean_space != space and space not in warned_spaces:
                issues.append(
                    NeatValueWarning(
                        f"Invalid space in property {self._space_property}: {space}. Fixed to {clean_space}"
                    )
                )
                warned_spaces.add(space)

            self._space_by_instance_uri[instance] = clean_space
        return issues

    def _lookup_identifier_by_uri(self) -> None:
        if not self.neat_prefix_by_type_uri:
            return

        count = sum(count for _, count in self.graph_store.queries.summarize_instances())
        instance_iterable = self.graph_store.queries.list_instances_ids()
        instance_iterable = iterate_progress_bar_if_above_config_threshold(
            instance_iterable, count, f"Looking up identifiers for {count} instances..."
        )
        count_by_identifier: dict[str, list[URIRef]] = defaultdict(list)
        for instance_uri, type in instance_iterable:
            if type not in self.neat_prefix_by_type_uri:
                continue
            prefix = self.neat_prefix_by_type_uri[type]
            identifier = remove_namespace_from_uri(instance_uri)
            if self._unquote_external_ids:
                identifier = urllib.parse.unquote(identifier)
            count_by_identifier[identifier.removeprefix(prefix)].append(instance_uri)

        for identifier, uris in count_by_identifier.items():
            if len(uris) == 1:
                self._external_id_by_uri[uris[0]] = identifier

    def _create_instance_space_if_not_exists(self) -> IssueList:
        issues = IssueList()
        if not self._client:
            return issues

        instance_spaces = set(self._space_by_instance_uri.values()) - {self._instance_space}
        existing_spaces = {space.space for space in self._client.data_modeling.spaces.retrieve(list(instance_spaces))}
        if missing_spaces := (instance_spaces - existing_spaces):
            try:
                self._client.data_modeling.spaces.apply([dm.SpaceApply(space=space) for space in missing_spaces])
            except CogniteAPIError as e:
                issues.append(AuthorizationError(f"Creating {len(missing_spaces)} instance spaces.", str(e)))
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
                    ids = (self._create_instance_id(v, "node", stop_on_exception=True) for v in value)
                    result = [id_.dump(camel_case=True, include_instance_type=False) for id_ in ids]
                    # Todo: Account for max_list_limit
                    if len(result) <= DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT:
                        return result
                    warnings.warn(
                        PropertyDirectRelationLimitWarning(
                            identifier="unknown",
                            resource_type="view property",
                            property_name=cast(str, cls.model_fields[info.field_name].alias or info.field_name),
                            limit=DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT,
                        ),
                        stacklevel=2,
                    )
                    # To get deterministic results, we sort by space and externalId
                    result.sort(key=lambda x: (x["space"], x["externalId"]))
                    return result[:DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT]
                elif value:
                    return self._create_instance_id(value[0], "node", stop_on_exception=True).dump(
                        camel_case=True, include_instance_type=False
                    )
                return {}

            validators["parse_direct_relation"] = field_validator(*direct_relation_by_property.keys(), mode="before")(  # type: ignore[assignment]
                parse_direct_relation  # type: ignore[arg-type]
            )

        if unit_properties:

            def parse_direct_relation_to_unit(cls, value: Any, info: ValidationInfo) -> dict | list[dict]:
                if value:
                    external_id = remove_namespace_from_uri(value[0])
                    if self._unquote_external_ids:
                        external_id = urllib.parse.unquote(external_id)
                    return {"space": "cdf_cdm_units", "externalId": external_id}
                return {}

            validators["parse_direct_relation_to_unit"] = field_validator(*unit_properties, mode="before")(  # type: ignore[assignment]
                parse_direct_relation_to_unit  # type: ignore[arg-type]
            )

        if text_fields:

            def parse_text(cls, value: Any, info: ValidationInfo) -> str | list[str]:
                if isinstance(value, list):
                    return [remove_namespace_from_uri(v) if isinstance(v, URIRef) else str(v) for v in value]
                return remove_namespace_from_uri(value) if isinstance(value, URIRef) else str(value)

            validators["parse_text"] = field_validator(*text_fields, mode="before")(parse_text)  # type: ignore[assignment, arg-type]

        pydantic_cls = create_model(view.external_id, __validators__=validators, **field_definitions)  # type: ignore[arg-type, call-overload]
        return _Projection(view.as_id(), view.used_for, pydantic_cls, edge_by_type, edge_by_prop_id), issues

    def _create_instances(
        self,
        instance_uri: URIRef,
        properties: dict[str | InstanceType, list[Any]],
        projection: _Projection,
        stop_on_exception: Literal[True, False] = False,
    ) -> Iterable[dm.InstanceApply | NeatIssue]:
        instance_id = self._create_instance_id(instance_uri, "node", stop_on_exception)
        if not isinstance(instance_id, InstanceId):
            yield instance_id
            return
        space, external_id = instance_id.space, instance_id.external_id
        start_node, end_node = self._pop_start_end_node(properties)
        is_edge = start_node and end_node
        instance_type = "edge" if is_edge else "node"
        if (projection.used_for == "node" and is_edge) or (projection.used_for == "edge" and not is_edge):
            creation_error = ResourceCreationError(
                external_id,
                instance_type,
                f"View used for {projection.used_for} instance {external_id!s} but is {instance_type}",
            )
            if stop_on_exception:
                raise creation_error from None
            yield creation_error
            return

        if RDF.type not in properties:
            error = ResourceCreationError(external_id, instance_type, "No rdf:type found")
            if stop_on_exception:
                raise error from None
            yield error
            return
        _ = properties.pop(RDF.type)[0]

        sources = []
        with catch_issues() as property_issues:
            sources = [
                dm.NodeOrEdgeData(
                    projection.view_id,
                    projection.pydantic_cls.model_validate(properties).model_dump(
                        exclude_unset=True,
                        exclude_none=True,
                    ),
                )
            ]
        for issue in property_issues:
            if isinstance(issue, ResourceNeatWarning):
                issue.identifier = external_id

        if property_issues.has_errors and stop_on_exception:
            raise property_issues.as_exception()
        yield from property_issues
        if not sources:
            return

        if start_node and end_node:
            start = self._create_instance_id(start_node, "edge", stop_on_exception)
            end = self._create_instance_id(end_node, "edge", stop_on_exception)
            if isinstance(start, NeatError):
                yield start
            if isinstance(end, NeatError):
                yield end
            if isinstance(start, InstanceId) and isinstance(end, InstanceId):
                yield dm.EdgeApply(
                    space=space,
                    external_id=external_id,
                    type=(projection.view_id.space, projection.view_id.external_id),
                    start_node=start.as_tuple(),
                    end_node=end.as_tuple(),
                    sources=sources,
                )
        else:
            yield dm.NodeApply(
                space=space,
                external_id=external_id,
                type=(projection.view_id.space, projection.view_id.external_id),
                sources=sources,
            )
        yield from self._create_edges_without_properties(space, external_id, properties, projection, stop_on_exception)

    def _create_edges_without_properties(
        self,
        space: str,
        identifier: str,
        properties: dict[str | InstanceType, list[str] | list[URIRef]],
        projection: _Projection,
        stop_on_exception: Literal[True, False],
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
                target_id = self._create_instance_id(target, "edge", stop_on_exception)  # type: ignore[call-overload]
                if not isinstance(target_id, InstanceId):
                    yield target_id
                    continue
                if isinstance(target, URIRef):
                    target = remove_namespace_from_uri(target)
                external_id = f"{identifier}.{prop_id}.{target}"

                start_node, end_node = (
                    (space, identifier),
                    target_id.as_tuple(),
                )
                if edge.direction == "inwards":
                    start_node, end_node = end_node, start_node
                yield dm.EdgeApply(
                    space=space,
                    external_id=(external_id if len(external_id) < 256 else create_sha256_hash(external_id)),
                    type=edge.type,
                    start_node=start_node,
                    end_node=end_node,
                )

    @staticmethod
    def _pop_start_end_node(
        properties: dict[str | InstanceType, list[str] | list[URIRef]],
    ) -> tuple[URIRef, URIRef] | tuple[None, None]:
        start_node = properties.pop("startNode", [None])[0]
        if not start_node:
            start_node = properties.pop("start_node", [None])[0]
        end_node = properties.pop("endNode", [None])[0]
        if not end_node:
            end_node = properties.pop("end_node", [None])[0]
        if start_node and end_node:
            return start_node, end_node  # type: ignore[return-value]
        return None, None

    @overload
    def _create_instance_id(
        self, uri: URIRef, instance_type: str, stop_on_exception: Literal[False] = False
    ) -> InstanceId | NeatError: ...

    @overload
    def _create_instance_id(
        self, uri: URIRef, instance_type: str, stop_on_exception: Literal[True] = True
    ) -> InstanceId: ...

    def _create_instance_id(
        self, uri: URIRef, instance_type: str, stop_on_exception: bool = False
    ) -> InstanceId | NeatError:
        space: str | None = None
        external_id: str | None = None
        error: NeatError | None = None
        if self._use_source_space:
            namespace, external_id = split_uri(uri)
            space = namespace_as_space(namespace)
            if space is None:
                error = ResourceCreationError(uri, instance_type, f"Could not find space for {uri!s}.")
        else:
            space = self._space_by_instance_uri[uri]
            if uri in self._external_id_by_uri:
                external_id = self._external_id_by_uri[uri]
            else:
                external_id = remove_namespace_from_uri(uri)

        if external_id and self._unquote_external_ids:
            external_id = urllib.parse.unquote(external_id)
        if space and external_id:
            return InstanceId(space, external_id)
        if error is None:
            raise ValueError(f"Bug in neat. Failed to create instance ID and determine error for {uri!r}")
        if stop_on_exception:
            raise error
        return error

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
        class_name: str | None = None,
    ) -> Iterable[UploadResult]:
        name = class_name or "Instances"
        nodes = [item for item in items if isinstance(item, dm.NodeApply)]
        edges = [item for item in items if isinstance(item, dm.EdgeApply)]
        try:
            upserted = client.data_modeling.instances.apply(
                nodes,
                edges,
                auto_create_end_nodes=True,
                auto_create_start_nodes=True,
                skip_on_version_conflict=True,
            )
        except CogniteAPIError as e:
            if len(items) == 1:
                yield UploadResult(
                    name=name,
                    issues=read_issues,
                    failed_items=items,
                    error_messages=[str(e)],
                    failed_upserted={item.as_id() for item in items},  # type: ignore[attr-defined]
                )
            else:
                half = len(items) // 2
                yield from self._upload_to_cdf(client, items[:half], dry_run, read_issues, class_name)
                yield from self._upload_to_cdf(client, items[half:], dry_run, read_issues, class_name)
        else:
            result = UploadResult(name=name, issues=read_issues)  # type: ignore[var-annotated]
            for instance in itertools.chain(upserted.nodes, upserted.edges):  # type: ignore[attr-defined]
                if instance.was_modified and instance.created_time == instance.last_updated_time:
                    result.created.add(instance.as_id())
                elif instance.was_modified:
                    result.changed.add(instance.as_id())
                else:
                    result.unchanged.add(instance.as_id())
            yield result


def _get_field_value_types(cls, info):
    return [type_.__name__ for type_ in get_args(cls.model_fields[info.field_name].annotation)]
