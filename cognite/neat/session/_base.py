from typing import Literal

from cognite.client import CogniteClient

from cognite.neat.issues import IssueList
from cognite.neat.rules.models import DMSRules
from cognite.neat.rules.transformers import ConvertToRules, VerifyAnyRules

from ._read import ReadAPI
from ._state import SessionState
from ._to import ToAPI


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

    def verify(self) -> IssueList:
        output = VerifyAnyRules("continue").transform(self._state.input_rule)
        if output.rules:
            self._state.verified_rules.append(output.rules)
        return output.issues

    def convert(self, target: Literal["dms"]) -> None:
        converted = ConvertToRules(DMSRules).transform(self._state.verified_rule)
        self._state.verified_rules.append(converted.rules)
        if self._verbose:
            print(f"Rules converted to {target}")
