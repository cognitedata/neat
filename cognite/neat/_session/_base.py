from datetime import datetime, timezone
from typing import Literal, cast

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat import _version
from cognite.neat._issues import IssueList
from cognite.neat._rules import importers
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.importers._rdf._base import DEFAULT_NON_EXISTING_NODE_TYPE
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.data_types import AnyURI
from cognite.neat._rules.models.entities._single_value import UnknownEntity
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._rules.transformers import ConvertToRules, VerifyAnyRules
from cognite.neat._store._provenance import (
    INSTANCES_ENTITY,
    Change,
)

from ._inspect import InspectAPI
from ._prepare import PrepareAPI
from ._read import ReadAPI
from ._set import SetAPI
from ._show import ShowAPI
from ._state import SessionState
from ._to import ToAPI
from .engine import load_neat_engine
from .exceptions import NeatSessionError, intercept_session_exceptions


@intercept_session_exceptions
class NeatSession:
    def __init__(
        self,
        client: CogniteClient | None = None,
        storage: Literal["memory", "oxigraph"] = "memory",
        verbose: bool = True,
        load_engine: Literal["newest", "cache", "skip"] = "cache",
    ) -> None:
        self._client = client
        self._verbose = verbose
        self._state = SessionState(store_type=storage)
        self.read = ReadAPI(self._state, client, verbose)
        self.to = ToAPI(self._state, client, verbose)
        self.prepare = PrepareAPI(self._state, verbose)
        self.show = ShowAPI(self._state)
        self.set = SetAPI(self._state, verbose)
        self.inspect = InspectAPI(self._state)
        if load_engine != "skip" and (engine_version := load_neat_engine(client, load_engine)):
            print(f"Neat Engine {engine_version} loaded.")

    @property
    def version(self) -> str:
        return _version.__version__

    def verify(self) -> IssueList:
        source_id, last_unverified_rule = self._state.data_model.last_unverified_rule
        transformer = VerifyAnyRules("continue")
        start = datetime.now(timezone.utc)
        output = transformer.try_transform(last_unverified_rule)
        end = datetime.now(timezone.utc)

        if output.rules:
            change = Change.from_rules_activity(
                output.rules,
                transformer.agent,
                start,
                end,
                f"Verified data model {source_id} as {output.rules.id_}",
                self._state.data_model.provenance.source_entity(source_id)
                or self._state.data_model.provenance.target_entity(source_id),
            )

            self._state.data_model.write(output.rules, change)

            if isinstance(output.rules, InformationRules):
                self._state.instances.store.add_rules(output.rules)

        output.issues.action = "verify"
        self._state.data_model.issue_lists.append(output.issues)
        if output.issues:
            print("You can inspect the issues with the .inspect.issues(...) method.")
        return output.issues

    def convert(self, target: Literal["dms", "information"]) -> None:
        start = datetime.now(timezone.utc)
        if target == "dms":
            source_id, info_rules = self._state.data_model.last_verified_information_rules
            converter = ConvertToRules(DMSRules)
            converted_rules = converter.transform(info_rules).rules
        elif target == "information":
            source_id, dms_rules = self._state.data_model.last_verified_dms_rules
            converter = ConvertToRules(InformationRules)
            converted_rules = converter.transform(dms_rules).rules
        else:
            raise NeatSessionError(f"Target {target} not supported.")
        end = datetime.now(timezone.utc)

        # Provenance
        change = Change.from_rules_activity(
            converted_rules,
            converter.agent,
            start,
            end,
            f"Converted data model {source_id} to {converted_rules.id_}",
            self._state.data_model.provenance.source_entity(source_id)
            or self._state.data_model.provenance.target_entity(source_id),
        )

        self._state.data_model.write(converted_rules, change)

        if self._verbose:
            print(f"Rules converted to {target}")

    def infer(
        self,
        model_id: dm.DataModelId | tuple[str, str, str] = (
            "neat_space",
            "NeatInferredDataModel",
            "v1",
        ),
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
        max_number_of_instance: int = 100,
    ) -> IssueList:
        """Data model inference from instances.

        Args:
            model_id: The ID of the inferred data model.
            non_existing_node_type: The type of node to use when type of node is not possible to determine.
        """

        model_id = dm.DataModelId.load(model_id)

        start = datetime.now(timezone.utc)
        importer = importers.InferenceImporter.from_graph_store(
            store=self._state.instances.store,
            non_existing_node_type=non_existing_node_type,
            max_number_of_instance=max_number_of_instance,
        )
        inferred_rules: ReadRules = importer.to_rules()
        end = datetime.now(timezone.utc)

        if model_id.space:
            cast(InformationInputRules, inferred_rules.rules).metadata.prefix = model_id.space
        if model_id.external_id:
            cast(InformationInputRules, inferred_rules.rules).metadata.name = model_id.external_id

        if model_id.version:
            cast(InformationInputRules, inferred_rules.rules).metadata.version = model_id.version

        # Provenance
        change = Change.from_rules_activity(
            inferred_rules,
            importer.agent,
            start,
            end,
            "Inferred data model",
            INSTANCES_ENTITY,
        )

        self._state.data_model.write(inferred_rules, change)
        return inferred_rules.issues

    def _repr_html_(self) -> str:
        state = self._state
        if (
            not state.instances.has_store
            and not state.data_model.has_unverified_rules
            and not state.data_model.has_verified_rules
        ):
            return "<strong>Empty session</strong>. Get started by reading something with the <em>.read</em> attribute."

        output = []

        if state.data_model.has_unverified_rules and not state.data_model.has_verified_rules:
            rules: ReadRules = state.data_model.last_unverified_rule[1]
            output.append(f"<H2>Unverified Data Model</H2><br />{rules.rules._repr_html_()}")  # type: ignore

        if state.data_model.has_verified_rules:
            output.append(f"<H2>Verified Data Model</H2><br />{state.data_model.last_verified_rule[1]._repr_html_()}")  # type: ignore

        if state.instances.has_store:
            output.append(f"<H2>Instances</H2> {state.instances.store._repr_html_()}")

        return "<br />".join(output)
