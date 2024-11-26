import copy
from collections.abc import Collection
from datetime import datetime, timezone
from typing import Literal, cast

from cognite.client.data_classes.data_modeling import DataModelIdentifier
from rdflib import URIRef

from cognite.neat._client import NeatClient
from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph.transformers import RelationshipToSchemaTransformer
from cognite.neat._graph.transformers._rdfpath import MakeConnectionOnExactMatch
from cognite.neat._rules._shared import InputRules, ReadRules
from cognite.neat._rules.importers import DMSImporter
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.dms import DMSValidation
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._rules.transformers import (
    PrefixEntities,
    ReduceCogniteModel,
    ToCompliantEntities,
    ToExtension,
    VerifyDMSRules,
)
from cognite.neat._store._provenance import Agent as ProvenanceAgent
from cognite.neat._store._provenance import Change

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper

try:
    from rich import print
except ImportError:
    ...


@session_class_wrapper
class PrepareAPI:
    def __init__(self, client: NeatClient | None, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.data_model = DataModelPrepareAPI(client, state, verbose)
        self.instances = InstancePrepareAPI(state, verbose)


@session_class_wrapper
class InstancePrepareAPI:
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


        """

        subject_type, subject_predicate = self._get_type_and_property_uris(*source)
        object_type, object_predicate = self._get_type_and_property_uris(*target)

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
            raise NeatSessionError(f"Type {type_} does not exist in the graph.")
        elif len(type_uri) > 1:
            raise NeatSessionError(f"{type_} has multiple ids found in the graph: {','.join(type_uri)}.")

        if not property_uri:
            raise NeatSessionError(f"Property {property_} does not exist in the graph.")
        elif len(type_uri) > 1:
            raise NeatSessionError(f"{property_} has multiple ids found in the graph: {','.join(property_uri)}.")

        if not self._state.instances.store.queries.type_with_property(type_uri[0], property_uri[0]):
            raise NeatSessionError(f"Property {property_} is not defined for type {type_}. Cannot make connection")
        return type_uri[0], property_uri[0]

    def relationships_as_connections(self, limit: int = 1) -> None:
        """This assumes that you have read a classic CDF knowledge graph including relationships.

        This transformer analyzes the relationships in the graph and modifies them to be part of the schema
        for Assets, Events, Files, Sequences, and TimeSeries. Relationships without any properties
        are replaced by a simple relationship between the source and target nodes. Relationships with
        properties are replaced by a schema that contains the properties as attributes.

        Args:
            limit: The minimum number of relationships that need to be present for it
                to be converted into a schema. Default is 1.

        """
        transformer = RelationshipToSchemaTransformer(limit=limit)
        self._state.instances.store.transform(transformer)


@session_class_wrapper
class DataModelPrepareAPI:
    def __init__(self, client: NeatClient | None, state: SessionState, verbose: bool) -> None:
        self._client = client
        self._state = state
        self._verbose = verbose

    def cdf_compliant_external_ids(self) -> None:
        """Convert data model component external ids to CDF compliant entities."""
        source_id, rules = self._state.data_model.last_info_unverified_rule

        start = datetime.now(timezone.utc)
        transformer = ToCompliantEntities()
        output: ReadRules[InformationInputRules] = transformer.transform(rules)
        end = datetime.now(timezone.utc)

        change = Change.from_rules_activity(
            output,
            transformer.agent,
            start,
            end,
            "Converted external ids to CDF compliant entities",
            self._state.data_model.provenance.source_entity(source_id)
            or self._state.data_model.provenance.target_entity(source_id),
        )

        self._state.data_model.write(output, change)

    def prefix(self, prefix: str) -> None:
        """Prefix all views in the data model with the given prefix.

        Args:
            prefix: The prefix to add to the views in the data model.

        """
        source_id, rules = self._state.data_model.last_unverified_rule

        start = datetime.now(timezone.utc)
        transformer = PrefixEntities(prefix)
        new_rules = cast(InputRules, copy.deepcopy(rules.get_rules()))
        output = transformer.transform(new_rules)
        end = datetime.now(timezone.utc)

        change = Change.from_rules_activity(
            output,
            transformer.agent,
            start,
            end,
            "Added prefix to the data model views",
            self._state.data_model.provenance.source_entity(source_id)
            or self._state.data_model.provenance.target_entity(source_id),
        )

        self._state.data_model.write(output, change)

    def to_enterprise(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "My",
        dummy_property: str = "GUID",
        move_connections: bool = False,
    ) -> None:
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
        if input := self._state.data_model.last_verified_dms_rules:
            source_id, rules = input

            start = datetime.now(timezone.utc)
            transformer = ToExtension(
                new_model_id=data_model_id,
                org_name=org_name,
                type_="enterprise",
                dummy_property=dummy_property,
                move_connections=move_connections,
            )
            output = transformer.transform(rules)
            end = datetime.now(timezone.utc)

            change = Change.from_rules_activity(
                output,
                transformer.agent,
                start,
                end,
                (
                    f"Prepared data model {data_model_id} to be enterprise data "
                    f"model on top of {rules.metadata.as_data_model_id()}"
                ),
                self._state.data_model.provenance.source_entity(source_id)
                or self._state.data_model.provenance.target_entity(source_id),
            )

            self._state.data_model.write(output.rules, change)

    def to_solution(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "My",
        mode: Literal["read", "write"] = "read",
        dummy_property: str = "GUID",
    ) -> None:
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
        if input := self._state.data_model.last_verified_dms_rules:
            source_id, rules = input

            start = datetime.now(timezone.utc)
            transformer = ToExtension(
                new_model_id=data_model_id,
                org_name=org_name,
                type_="solution",
                mode=mode,
                dummy_property=dummy_property,
            )
            output = transformer.transform(rules)
            end = datetime.now(timezone.utc)

            change = Change.from_rules_activity(
                output,
                transformer.agent,
                start,
                end,
                (
                    f"Prepared data model {data_model_id} to be solution data model "
                    f"on top of {rules.metadata.as_data_model_id()}"
                ),
                self._state.data_model.provenance.source_entity(source_id)
                or self._state.data_model.provenance.target_entity(source_id),
            )

            self._state.data_model.write(output.rules, change)

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
            org_name: Organization name to use for the views in the new data model.
            include: The views to include in the data product data model. Can be either "same-space" or "all".
                If you set same-space, only the views in the same space as the data model will be included.
        """
        source_id, rules = self._state.data_model.last_verified_dms_rules

        dms_ref: DMSRules | None = None
        view_ids, container_ids = DMSValidation(rules, self._client).imported_views_and_containers_ids()
        if view_ids or container_ids:
            if self._client is None:
                raise NeatSessionError(
                    "No client provided. You are referencing unknown views and containers in your data model, "
                    "NEAT needs a client to lookup the definitions. "
                    "Please set the client in the session, NeatSession(client=client)."
                )
            schema = self._client.schema.retrieve([v.as_id() for v in view_ids], [c.as_id() for c in container_ids])

            importer = DMSImporter(schema)
            reference_rules = importer.to_rules().rules
            if reference_rules is not None:
                imported = VerifyDMSRules("continue").transform(reference_rules)
                if dms_ref := imported.rules:
                    rules = rules.model_copy(deep=True)
                    if rules.containers is None:
                        rules.containers = dms_ref.containers
                    else:
                        existing_containers = {c.container for c in rules.containers}
                        rules.containers.extend(
                            [c for c in dms_ref.containers or [] if c.container not in existing_containers]
                        )
                    existing_views = {v.view for v in rules.views}
                    rules.views.extend([v for v in dms_ref.views if v.view not in existing_views])
                    existing_properties = {(p.view, p.view_property) for p in rules.properties}
                    rules.properties.extend(
                        [p for p in dms_ref.properties if (p.view, p.view_property) not in existing_properties]
                    )

        start = datetime.now(timezone.utc)
        transformer = ToExtension(
            new_model_id=data_model_id,
            org_name=org_name,
            type_="data_product",
            include=include,
        )
        output = transformer.transform(rules)
        end = datetime.now(timezone.utc)

        change = Change.from_rules_activity(
            output,
            transformer.agent,
            start,
            end,
            (
                f"Prepared data model {data_model_id} to be data product model "
                f"on top of {rules.metadata.as_data_model_id()}"
            ),
            self._state.data_model.provenance.source_entity(source_id)
            or self._state.data_model.provenance.target_entity(source_id),
        )

        self._state.data_model.write(output.rules, change)

    def reduce(self, drop: Collection[Literal["3D", "Annotation", "BaseViews"] | str]) -> None:
        """This is a special method that allow you to drop parts of the data model.
        This only applies to Cognite Data Models.

        Args:
            drop: What to drop from the data model. The values 3D, Annotation, and BaseViews are special values that
                drops multiple views at once. You can also pass externalIds of views to drop individual views.

        """
        if input := self._state.data_model.last_verified_dms_rules:
            source_id, rules = input
            start = datetime.now(timezone.utc)

            transformer = ReduceCogniteModel(drop)
            output = transformer.transform(rules)
            output.rules.metadata.version = f"{rules.metadata.version}.reduced"

            end = datetime.now(timezone.utc)

            change = Change.from_rules_activity(
                output,
                transformer.agent,
                start,
                end,
                (
                    f"Reduced data model {rules.metadata.as_data_model_id()}"
                    f"on top of {rules.metadata.as_data_model_id()}"
                ),
                self._state.data_model.provenance.source_entity(source_id),
            )

            self._state.data_model.write(output.rules, change)

    def include_referenced(self) -> None:
        """Include referenced views and containers in the data model."""
        start = datetime.now(timezone.utc)

        source_id, rules = self._state.data_model.last_verified_dms_rules
        view_ids, container_ids = DMSValidation(rules, self._client).imported_views_and_containers_ids()
        if not (view_ids or container_ids):
            print(
                f"Data model {rules.metadata.as_data_model_id()} does not have any referenced views or containers."
                f"that is not already included in the data model."
            )
            return
        if self._client is None:
            raise NeatSessionError(
                "No client provided. You are referencing unknown views and containers in your data model, "
                "NEAT needs a client to lookup the definitions. "
                "Please set the client in the session, NeatSession(client=client)."
            )
        schema = self._client.schema.retrieve([v.as_id() for v in view_ids], [c.as_id() for c in container_ids])
        copy_ = rules.model_copy(deep=True)
        copy_.metadata.version = f"{rules.metadata.version}_completed"
        importer = DMSImporter(schema)
        imported = importer.to_rules()
        if imported.rules is None:
            self._state.data_model.issue_lists.append(imported.issues)
            raise NeatSessionError(
                "Could not import the referenced views and containers. "
                "See `neat.inspect.issues()` for more information."
            )
        verified = VerifyDMSRules("continue", validate=False).transform(imported.rules)
        if verified.rules is None:
            self._state.data_model.issue_lists.append(verified.issues)
            raise NeatSessionError(
                "Could not verify the referenced views and containers. "
                "See `neat.inspect.issues()` for more information."
            )
        if copy_.containers is None:
            copy_.containers = verified.rules.containers
        else:
            existing_containers = {c.container for c in copy_.containers}
            copy_.containers.extend(
                [c for c in verified.rules.containers or [] if c.container not in existing_containers]
            )
        existing_views = {v.view for v in copy_.views}
        copy_.views.extend([v for v in verified.rules.views if v.view not in existing_views])
        end = datetime.now(timezone.utc)

        change = Change.from_rules_activity(
            copy_,
            ProvenanceAgent(id_=DEFAULT_NAMESPACE["agent/"]),
            start,
            end,
            (f"Included referenced views and containers in the data model {rules.metadata.as_data_model_id()}"),
            self._state.data_model.provenance.source_entity(source_id)
            or self._state.data_model.provenance.target_entity(source_id),
        )

        self._state.data_model.write(copy_, change)
