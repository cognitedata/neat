import warnings
from collections.abc import Callable
from typing import Any

from rdflib import URIRef

from cognite.neat._alpha import ExperimentalFlags
from cognite.neat._graph.transformers import (
    ConnectionToLiteral,
    ConvertLiteral,
    LiteralToEntity,
    RelationshipAsEdgeTransformer,
)
from cognite.neat._graph.transformers._rdfpath import MakeConnectionOnExactMatch
from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules.transformers import PrefixEntities, StandardizeNaming
from cognite.neat._rules.transformers._converters import StandardizeSpaceAndVersion
from cognite.neat._utils.text import humanize_collection

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class PrepareAPI:
    """Apply various operations on the knowledge graph as a necessary preprocessing step before for instance
    inferring a data model or exporting the knowledge graph to a desired destination.
    """

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.data_model = DataModelPrepareAPI(state, verbose)
        self.instances = InstancePrepareAPI(state, verbose)


@session_class_wrapper
class InstancePrepareAPI:
    """Operations to perform on instances of data in the knowledge graph."""

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

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


@session_class_wrapper
class DataModelPrepareAPI:
    """Operations to perform on a data model as part of a workflow before writing the data model
    to a desired destination.
    """

    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def prefix(self, prefix: str) -> IssueList:
        """Prefix all views in the data model with the given prefix.

        Args:
            prefix: The prefix to add to the views in the data model.

        """

        return self._state.rule_transform(PrefixEntities(prefix))  # type: ignore[arg-type]

    def standardize_naming(self) -> IssueList:
        """Standardize the naming of all views/classes/properties in the data model.

        For classes/views/containers, the naming will be standardized to PascalCase.
        For properties, the naming will be standardized to camelCase.
        """
        warnings.filterwarnings("default")
        ExperimentalFlags.standardize_naming.warn()
        return self._state.rule_transform(StandardizeNaming())

    def standardize_space_and_version(self) -> IssueList:
        """Standardize space and version in the data model.

        This method will standardize the space and version in the data model to the Cognite standard.
        """
        warnings.filterwarnings("default")
        ExperimentalFlags.standardize_space_and_version.warn()
        return self._state.rule_transform(StandardizeSpaceAndVersion())
