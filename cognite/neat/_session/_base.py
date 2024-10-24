from typing import Literal, cast

import pandas as pd
from cognite.client import CogniteClient

from cognite.neat._issues import IssueList
from cognite.neat._rules import importers
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models._base_input import InputComponent
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._rules.transformers import ConvertToRules, VerifyAnyRules

from ._read import ReadAPI
from ._state import SessionState
from ._to import ToAPI
from ._prepare import PrepareAPI


class NeatSession:
    def __init__(
        self,
        client: CogniteClient | None = None,
        storage: Literal["memory", "oxigraph"] = "oxigraph",
        verbose: bool = True,
    ) -> None:
        self._client = client
        self._verbose = verbose
        self._state = SessionState(store_type=storage)
        self.read = ReadAPI(self._state, client, verbose)
        self.to = ToAPI(self._state, client, verbose)
        self.transform = TransformAPI(self._state, verbose)

    def verify(self) -> IssueList:
        output = VerifyAnyRules("continue").try_transform(self._state.input_rule)
        if output.rules:
            self._state.verified_rules.append(output.rules)
            if isinstance(output.rules, InformationRules):
                self._state.store.add_rules(output.rules)
        return output.issues

    def convert(self, target: Literal["dms"]) -> None:
        converted = ConvertToRules(DMSRules).transform(self._state.verified_rule)
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

        self.read._store_rules(self._state.store, input_rules, "Data Model Inference")
        return input_rules.issues

    def _repr_html_(self) -> str:
        state = self._state
        if not state.has_store and not state.input_rules:
            return "<strong>Empty session</strong>. Get started by reading something with the <em>.read</em> attribute."

        output = []
        if state.input_rules and not state.verified_rules:
            metadata = cast(InputComponent, state.input_rule.rules.metadata)  # type: ignore[union-attr]
            table = pd.DataFrame([metadata.dump()]).T._repr_html_()  # type: ignore[operator]
            output.append(f"<strong>Raw DataModel</strong><br />{table}")

        if state.verified_rules:
            table = pd.DataFrame([state.verified_rule.metadata.model_dump()]).T._repr_html_()  # type: ignore[operator]
            output.append(f"<strong>DataModel</strong><br />{table}")

        if state.has_store:
            output.append(f"<strong>Metadata</strong> {state.store._repr_html_()}")

        return "<br />".join(output)