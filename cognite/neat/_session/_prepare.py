from collections.abc import Collection
from datetime import datetime, timezone
from typing import Literal

from cognite.client.data_classes.data_modeling import DataModelIdentifier
from rdflib import URIRef

from cognite.neat._graph.transformers._rdfpath import MakeConnectionOnExactMatch
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._rules.transformers import ReduceCogniteModel, ToCompliantEntities, ToExtension
from cognite.neat._store._provenance import Change

from ._state import SessionState
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class PrepareAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.data_model = DataModelPrepareAPI(state, verbose)
        self.instances = InstancePrepareAPI(state, verbose)


@intercept_session_exceptions
class InstancePrepareAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def make_connection_on_exact_match(
        self,
        source: tuple[URIRef, URIRef],
        target: tuple[URIRef, URIRef],
        connection: URIRef | None = None,
        limit: int | None = 100,
    ) -> None:
        """Make connection on exact match.

        Args:
            source: The source of the connection. A tuple of (rdf type, property) where
                    where property is the property that should be matched on the source
                    to make the connection with the target.
            target: The target of the connection. A tuple of (rdf type, property) where
                    where property is the property that should be matched on the target
                    to make the connection with the source.

            connection: new property to use for the connection. If None, the connection
                    will be made by lowercasing the target type.
            limit: The maximum number of connections to make. If None, all connections


        """

        subject_type, subject_predicate = source
        object_type, object_predicate = target

        transformer = MakeConnectionOnExactMatch(
            subject_type,
            subject_predicate,
            object_type,
            object_predicate,
            connection,
            limit,
        )

        self._state.instances.store.transform(transformer)


@intercept_session_exceptions
class DataModelPrepareAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def cdf_compliant_external_ids(self) -> None:
        """Convert data model component external ids to CDF compliant entities."""
        if input := self._state.data_model.last_info_unverified_rule:
            source_id, rules = input

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
        dummy_property: str = "dummy",
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
