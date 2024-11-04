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

from ._inspect import InspectAPI
from ._prepare import PrepareAPI
from ._read import ReadAPI
from ._set import SetAPI
from ._show import ShowAPI
from ._state import SessionState
from ._to import ToAPI
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class NeatSession:
    def __init__(
        self,
        client: CogniteClient | None = None,
        storage: Literal["memory", "oxigraph"] = "memory",
        verbose: bool = True,
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

    @property
    def version(self) -> str:
        return _version.__version__

    def verify(self) -> IssueList:
        output = VerifyAnyRules("continue").try_transform(self._state.input_rule)
        if output.rules:
            self._state.verified_rules.append(output.rules)
            if isinstance(output.rules, InformationRules):
                self._state.store.add_rules(output.rules)
        self._state.issue_lists.append(output.issues)
        if output.issues:
            print("You can inspect the issues with the .inspect.issues(...) method.")
        return output.issues

    def convert(self, target: Literal["dms"]) -> None:
        converted = ConvertToRules(DMSRules).transform(self._state.last_verified_rule)
        self._state.verified_rules.append(converted.rules)
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
    ) -> IssueList:
        """Data model inference from instances.

        Args:
            model_id: The ID of the inferred data model.
            non_existing_node_type: The type of node to use when type of node is not possible to determine.
        """

        model_id = dm.DataModelId.load(model_id)

        input_rules: ReadRules = importers.InferenceImporter.from_graph_store(
            store=self._state.store,
            non_existing_node_type=non_existing_node_type,
        ).to_rules()

        if model_id.space:
            cast(InformationInputRules, input_rules.rules).metadata.prefix = model_id.space
        if model_id.external_id:
            cast(InformationInputRules, input_rules.rules).metadata.name = model_id.external_id

        if model_id.version:
            cast(InformationInputRules, input_rules.rules).metadata.version = model_id.version

        self.read.rdf._store_rules(self._state.store, input_rules, "Data Model Inference")
        return input_rules.issues

    def _repr_html_(self) -> str:
        state = self._state
        if not state.has_store and not state.input_rules:
            return "<strong>Empty session</strong>. Get started by reading something with the <em>.read</em> attribute."

        output = []
        if state.input_rules and not state.verified_rules:
            output.append(f"<H2>Unverified Data Model</H2><br />{state.input_rule.rules._repr_html_()}")  # type: ignore

        if state.verified_rules:
            output.append(f"<H2>Verified Data Model</H2><br />{state.last_verified_rule._repr_html_()}")  # type: ignore

        if state.has_store:
            output.append(f"<H2>Instances</H2> {state.store._repr_html_()}")

        return "<br />".join(output)
