from typing import Literal, cast

from cognite.client import CogniteClient

from cognite.neat._issues import IssueList
from cognite.neat._rules import importers
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._rules.transformers import ConvertToRules, VerifyAnyRules

from ._prepare import PrepareAPI
from ._read import ReadAPI
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

    def verify(self) -> IssueList:
        output = VerifyAnyRules("continue").try_transform(self._state.input_rule)
        if output.rules:
            self._state.verified_rules.append(output.rules)
            if isinstance(output.rules, InformationRules):
                self._state.store.add_rules(output.rules)
        return output.issues

    def convert(self, target: Literal["dms"]) -> None:
        converted = ConvertToRules(DMSRules).transform(self._state.last_verified_rule)
        self._state.verified_rules.append(converted.rules)
        if self._verbose:
            print(f"Rules converted to {target}")

    def infer(
        self,
        space: str = "inference_space",
        external_id: str = "InferredDataModel",
        version: str = "v1",
    ) -> IssueList:
        input_rules: ReadRules = importers.InferenceImporter.from_graph_store(self._state.store).to_rules()

        cast(InformationInputRules, input_rules.rules).metadata.prefix = space
        cast(InformationInputRules, input_rules.rules).metadata.name = external_id
        cast(InformationInputRules, input_rules.rules).metadata.version = version

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
