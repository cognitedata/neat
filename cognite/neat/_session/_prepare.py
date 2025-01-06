from collections.abc import Callable, Collection
from typing import Any, Literal, cast

from cognite.client.data_classes.data_modeling import DataModelIdentifier
from rdflib import URIRef

from cognite.neat._client import NeatClient
from cognite.neat._constants import (
    get_default_prefixes_and_namespaces,
)
from cognite.neat._graph import extractors
from cognite.neat._graph.transformers import (
    AttachPropertyFromTargetToSource,
    ConnectionToLiteral,
    ConvertLiteral,
    LiteralToEntity,
    PruneDeadEndEdges,
    PruneInstancesOfUnknownType,
    PruneTypes,
    RelationshipAsEdgeTransformer,
    Transformers,
)
from cognite.neat._graph.transformers._rdfpath import MakeConnectionOnExactMatch
from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules.models.dms import DMSValidation
from cognite.neat._rules.transformers import (
    AddClassImplements,
    IncludeReferenced,
    PrefixEntities,
    ReduceCogniteModel,
    RulesTransformer,
    ToCompliantEntities,
    ToDataProductModel,
    ToEnterpriseModel,
    ToSolutionModel,
)
from cognite.neat._utils.text import humanize_collection

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class PrepareAPI:
    """Apply various operations on the knowledge graph as a necessary preprocessing step before for instance
    inferring a data model or exporting the knowledge graph to a desired destination.
    """

    def __init__(self, client: NeatClient | None, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.data_model = DataModelPrepareAPI(client, state, verbose)
        self.instances = InstancePrepareAPI(state, verbose)


@session_class_wrapper
class InstancePrepareAPI:
    """Operations to perform on instances of data in the knowledge graph."""

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def dexpi(self) -> None:
        """Prepares extracted DEXPI graph for further usage in CDF

        !!! note "This method bundles several graph transformers which"
            - attach values of generic attributes to nodes
            - create associations between nodes
            - remove unused generic attributes
            - remove associations between nodes that do not exist in the extracted graph
            - remove edges to nodes that do not exist in the extracted graph

        and therefore safeguard CDF from a bad graph

        Example:
            Apply Dexpi specific transformations:
            ```python
            neat.prepare.instances.dexpi()
            ```
        """

        DEXPI = get_default_prefixes_and_namespaces()["dexpi"]

        transformers = [
            # Remove any instance which type is unknown
            PruneInstancesOfUnknownType(),
            # Directly connect generic attributes
            AttachPropertyFromTargetToSource(
                target_property=DEXPI.Value,
                target_property_holding_new_property=DEXPI.Name,
                target_node_type=DEXPI.GenericAttribute,
                delete_target_node=True,
            ),
            # Directly connect associations
            AttachPropertyFromTargetToSource(
                target_property=DEXPI.ItemID,
                target_property_holding_new_property=DEXPI.Type,
                target_node_type=DEXPI.Association,
                delete_target_node=True,
            ),
            # Remove unused generic attributes and associations
            PruneTypes([DEXPI.GenericAttribute, DEXPI.Association]),
            # Remove edges to nodes that do not exist in the extracted graph
            PruneDeadEndEdges(),
        ]

        for transformer in transformers:
            self._state.instances.store.transform(cast(Transformers, transformer))

    def aml(self) -> None:
        """Prepares extracted AutomationML graph for further usage in CDF

        !!! note "This method bundles several graph transformers which"
            - attach values of attributes to nodes
            - remove unused attributes
            - remove edges to nodes that do not exist in the extracted graph

        and therefore safeguard CDF from a bad graph

        Example:
            Apply AML specific transformations:
            ```python
            neat.prepare.instances.aml()
            ```
        """

        AML = get_default_prefixes_and_namespaces()["aml"]

        transformers = [
            # Remove any instance which type is unknown
            PruneInstancesOfUnknownType(),
            # Directly connect generic attributes
            AttachPropertyFromTargetToSource(
                target_property=AML.Value,
                target_property_holding_new_property=AML.Name,
                target_node_type=AML.Attribute,
                delete_target_node=True,
            ),
            # Prune unused attributes
            PruneTypes([AML.Attribute]),
            # # Remove edges to nodes that do not exist in the extracted graph
            PruneDeadEndEdges(),
        ]

        for transformer in transformers:
            self._state.instances.store.transform(cast(Transformers, transformer))

    def make_connection_on_exact_match(
        self,
        source: tuple[str, str],
        target: tuple[str, str],
        connection: str | None = None,
        limit: int | None = 100,
    ) -> None:
        """Make connection on exact match.

        Args:
            source: The source of the connection. A tuple of (type, property) where
                    where property is the property that should be matched on the source
                    to make the connection with the target.
            target: The target of the connection. A tuple of (type, property) where
                    where property is the property that should be matched on the target
                    to make the connection with the source.

            connection: new property to use for the connection. If None, the connection
                    will be made by lowercasing the target type.
            limit: The maximum number of connections to make. If None, all connections

        !!! note "Make Connection on Exact Match"
            This method will make a connection between the source and target based on the exact match:
            (SourceType)-[sourceProperty]->(sourceValue) == (TargetType)-[targetProperty]->(targetValue)

            The connection will be made by creating a new property on the source type that will contain the
            target value, as follows:
            (SourceType)-[connection]->(TargetType)

        Example:
            Make connection on exact match:
            ```python
            # From an active NeatSession
            neat.read.csv("workitem.Table.csv",
                          type = "Activity",
                          primary_key="sourceId")

            neat.read.csv("assets.Table.csv",
                          type="Asset",
                          primary_key="WMT_TAG_GLOBALID")

            # Here we specify what column from the source table we should use when we link it with a column in the
            # target table. In this case, it is the "workorderItemname" column in the source table
            source = ("Activity", "workorderItemname")

            # Here we give a name to the new property that is created when a match between the source and target is
            # found
            connection = "asset"

            # Here we specify what column from the target table we should use when searching for a match.
            # In this case, it is the "wmtTagName" column in the target table
            target = ("Asset", "wmtTagName")

            neat.prepare.instances.make_connection_on_exact_match(source, target, connection)
            ```
        """
        try:
            subject_type, subject_predicate = self._get_type_and_property_uris(*source)
            object_type, object_predicate = self._get_type_and_property_uris(*target)
        except NeatValueError as e:
            raise NeatSessionError(f"Cannot make connection: {e}") from None

        transformer = MakeConnectionOnExactMatch(
            subject_type,
            subject_predicate,
            object_type,
            object_predicate,
            connection,
            limit,
        )

        self._state.instances.store.transform(transformer)

    def _get_type_and_property_uris(self, type_: str, property_: str) -> tuple[URIRef, URIRef]:
        type_uri = self._state.instances.store.queries.type_uri(type_)
        property_uri = self._state.instances.store.queries.property_uri(property_)

        if not type_uri:
            raise NeatValueError(f"Type {type_} does not exist in the graph.")
        elif len(type_uri) > 1:
            raise NeatValueError(f"{type_} has multiple ids found in the graph: {humanize_collection(type_uri)}.")

        if not property_uri:
            raise NeatValueError(f"Property {property_} does not exist in the graph.")
        elif len(type_uri) > 1:
            raise NeatValueError(
                f"{property_} has multiple ids found in the graph: {humanize_collection(property_uri)}."
            )

        if not self._state.instances.store.queries.type_with_property(type_uri[0], property_uri[0]):
            raise NeatValueError(f"Property {property_} is not defined for type {type_}.")
        return type_uri[0], property_uri[0]

    def relationships_as_edges(self, min_relationship_types: int = 1, limit_per_type: int | None = None) -> None:
        """This assumes that you have read a classic CDF knowledge graph including relationships.

        This method converts relationships into edges in the graph. This is useful as the
        edges will be picked up as part of the schema connected to Assets, Events, Files, Sequences,
        and TimeSeries in the InferenceImporter.

        Args:
            min_relationship_types: The minimum number of relationship types that must exists to convert those
                relationships to edges. For example, if there is only 5 relationships between Assets and TimeSeries,
                and limit is 10, those relationships will not be converted to edges.
            limit_per_type: The number of conversions to perform per relationship type. For example, if there are 10
                relationships between Assets and TimeSeries, and limit_per_type is 1, only 1 of those relationships
                will be converted to an edge. If None, all relationships will be converted.

        """
        transformer = RelationshipAsEdgeTransformer(min_relationship_types, limit_per_type)
        self._state.instances.store.transform(transformer)

    def convert_data_type(self, source: tuple[str, str], *, convert: Callable[[Any], Any] | None = None) -> None:
        """Convert the data type of the given property.

        This is, for example, useful when you have a boolean property that you want to convert to an enum.

        Args:
            source: The source of the conversion. A tuple of (type, property)
                    where property is the property that should be converted.
            convert: The function to use for the conversion. The function should take the value of the property
                    as input and return the converted value. Default to assume you have a string that should be
                    converted to int, float, bool, or datetime.

        Example:
            Convert a boolean property to a string:
            ```python
            neat.prepare.instances.convert_data_type(
                ("TimeSeries", "isString"),
                convert=lambda is_string: "string" if is_string else "numeric"
            )
            ```

        """
        try:
            subject_type, subject_predicate = self._get_type_and_property_uris(*source)
        except NeatValueError as e:
            raise NeatSessionError(f"Cannot convert data type: {e}") from None

        transformer = ConvertLiteral(subject_type, subject_predicate, convert)
        self._state.instances.store.transform(transformer)

    def property_to_type(self, source: tuple[str | None, str], type: str, new_property: str | None = None) -> None:
        """Convert a property to a new type.

        Args:
            source: The source of the conversion. A tuple of (type, property)
                    where property is the property that should be converted.
                    You can pass (None, property) to covert all properties with the given name.
            type: The new type of the property.
            new_property: Add the identifier as a new property. If None, the new entity will not have a property.

        Example:
            Convert the property 'source' to SourceSystem
            ```python
            neat.prepare.instances.property_to_type(
                (None, "source"), "SourceSystem"
            )
            ```
        """
        subject_type: URIRef | None = None
        if source[0] is not None:
            try:
                subject_type, subject_predicate = self._get_type_and_property_uris(*source)  # type: ignore[arg-type, assignment]
            except NeatValueError as e:
                raise NeatSessionError(f"Cannot convert to type: {e}") from None
        else:
            subject_predicate = self._state.instances.store.queries.property_uri(source[1])[0]

        transformer = LiteralToEntity(subject_type, subject_predicate, type, new_property)
        self._state.instances.store.transform(transformer)

    def connection_to_data_type(self, source: tuple[str | None, str]) -> None:
        """Converts a connection to a data type.

        Args:
            source: The source of the conversion. A tuple of (type, property)
                    where property is the property that should be converted.
                    You can pass (None, property) to covert all properties with the given name.

        Example:

            Convert all properties 'labels' from a connection to a string:

            ```python
            neat.prepare.instances.connection_to_data_type(
                (None, "labels")
            )
            ```

        """
        subject_type: URIRef | None = None
        if source[0] is not None:
            try:
                subject_type, subject_predicate = self._get_type_and_property_uris(*source)  # type: ignore[arg-type, assignment]
            except NeatValueError as e:
                raise NeatSessionError(f"Cannot convert to data type: {e}") from None
        else:
            subject_predicate = self._state.instances.store.queries.property_uri(source[1])[0]
        transformer = ConnectionToLiteral(subject_type, subject_predicate)
        self._state.instances.store.transform(transformer)

    def classic_to_core(self) -> None:
        """Prepares extracted CDF classic graph for the Core Data model.

        !!! note "This method bundles several graph transformers which"
            - Convert relationships to edges
            - Convert TimeSeries.type from bool to enum
            - Convert all properties 'source' to a connection to SourceSystem
            - Convert all properties 'labels' from a connection to a string

        Example:
            Apply classic to core transformations:
            ```python
            neat.prepare.instances.classic_to_core()
            ```
        """
        self.relationships_as_edges()
        self.convert_data_type(
            ("TimeSeries", "isString"), convert=lambda is_string: "string" if is_string else "numeric"
        )
        self.property_to_type((None, "source"), "SourceSystem", "name")
        for type_ in [
            extractors.EventsExtractor._default_rdf_type,
            extractors.AssetsExtractor._default_rdf_type,
            extractors.FilesExtractor._default_rdf_type,
        ]:
            try:
                subject_type, subject_predicate = self._get_type_and_property_uris(type_, "labels")
            except NeatValueError:
                # If the type_.labels does not exist, continue. This is not an error, it just means that the
                # Labels is not used in the graph for that type.
                continue
            else:
                transformer = ConnectionToLiteral(subject_type, subject_predicate)
                self._state.instances.store.transform(transformer)


@session_class_wrapper
class DataModelPrepareAPI:
    """Operations to perform on a data model as part of a workflow before writing the data model
    to a desired destination.
    """

    def __init__(self, client: NeatClient | None, state: SessionState, verbose: bool) -> None:
        self._client = client
        self._state = state
        self._verbose = verbose

    def cdf_compliant_external_ids(self) -> IssueList:
        """Convert data model component external ids to CDF compliant entities."""
        return self._state.rule_transform(ToCompliantEntities())

    def prefix(self, prefix: str) -> IssueList:
        """Prefix all views in the data model with the given prefix.

        Args:
            prefix: The prefix to add to the views in the data model.

        """
        return self._state.rule_transform(PrefixEntities(prefix))

    def to_enterprise(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "My",
        dummy_property: str = "GUID",
        move_connections: bool = False,
    ) -> IssueList:
        """Uses the current data model as a basis to create enterprise data model

        Args:
            data_model_id: The enterprise data model id that is being created
            org_name: Organization name to use for the views in the enterprise data model.
            dummy_property: The dummy property to use as placeholder for the views in the new data model.
            move_connections: If True, the connections will be moved to the new data model.

        !!! note "Enterprise Data Model Creation"

            Always create an enterprise data model from a Cognite Data Model as this will
            assure all the Cognite Data Fusion applications to run smoothly, such as
                - Search
                - Atlas AI
                - ...

        !!! note "Move Connections"

            If you want to move the connections to the new data model, set the move_connections
            to True. This will move the connections to the new data model and use new model
            views as the source and target views.

        """
        return self._state.rule_transform(
            ToEnterpriseModel(
                new_model_id=data_model_id,
                org_name=org_name,
                dummy_property=dummy_property,
                move_connections=move_connections,
            )
        )

    def to_solution(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "My",
        mode: Literal["read", "write"] = "read",
        dummy_property: str = "GUID",
    ) -> IssueList:
        """Uses the current data model as a basis to create solution data model

        Args:
            data_model_id: The solution data model id that is being created.
            org_name: Organization name to use for the views in the new data model.
            mode: The mode of the solution data model. Can be either "read" or "write".
            dummy_property: The dummy property to use as placeholder for the views in the new data model.

        !!! note "Solution Data Model Mode"

            The read-only solution model will only be able to read from the existing containers
            from the enterprise data model, therefore the solution data model will not have
            containers in the solution data model space. Meaning the solution data model views
            will be read-only.

            The write mode will have additional containers in the solution data model space,
            allowing in addition to reading through the solution model views, also writing to
            the containers in the solution data model space.

        """
        return self._state.rule_transform(
            ToSolutionModel(
                new_model_id=data_model_id,
                org_name=org_name,
                mode=mode,
                dummy_property=dummy_property,
            )
        )

    def to_data_product(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "",
        include: Literal["same-space", "all"] = "same-space",
    ) -> None:
        """Uses the current data model as a basis to create data product data model.

        A data product model is a data model that ONLY maps to containers and do not use implements. This is
        typically used for defining the data in a data product.

        Args:
            data_model_id: The data product data model id that is being created.
            org_name: Organization name used as prefix if the model is building on top of a Cognite Data Model.
            include: The views to include in the data product data model. Can be either "same-space" or "all".
                If you set same-space, only the properties of the views in the same space as the data model
                will be included.
        """

        view_ids, container_ids = DMSValidation(
            self._state.rule_store.last_verified_dms_rules
        ).imported_views_and_containers_ids()
        transformers: list[RulesTransformer] = []
        if (view_ids or container_ids) and self._client is None:
            raise NeatSessionError(
                "No client provided. You are referencing unknown views and containers in your data model, "
                "NEAT needs a client to lookup the definitions. "
                "Please set the client in the session, NeatSession(client=client)."
            )
        elif (view_ids or container_ids) and self._client:
            transformers.append(IncludeReferenced(self._client, include_properties=True))

        transformers.append(
            ToDataProductModel(
                new_model_id=data_model_id,
                org_name=org_name,
                include=include,
            )
        )

        self._state.rule_transform(*transformers)

    def reduce(self, drop: Collection[Literal["3D", "Annotation", "BaseViews"] | str]) -> IssueList:
        """This is a special method that allow you to drop parts of the data model.
        This only applies to Cognite Data Models.

        Args:
            drop: What to drop from the data model. The values 3D, Annotation, and BaseViews are special values that
                drops multiple views at once. You can also pass externalIds of views to drop individual views.

        """
        return self._state.rule_transform(ReduceCogniteModel(drop))

    def include_referenced(self) -> IssueList:
        """Include referenced views and containers in the data model."""
        if self._client is None:
            raise NeatSessionError(
                "No client provided. You are referencing unknown views and containers in your data model, "
                "NEAT needs a client to lookup the definitions. "
                "Please set the client in the session, NeatSession(client=client)."
            )
        return self._state.rule_transform(IncludeReferenced(self._client))

    def add_implements_to_classes(self, suffix: Literal["Edge"], implements: str = "Edge") -> IssueList:
        """All classes with the suffix will have the implements property set to the given value.

        Args:
            suffix: The suffix of the classes to add the implements property to.
            implements:  The value of the implements property to set.

        """
        return self._state.rule_transform(AddClassImplements(implements, suffix))
