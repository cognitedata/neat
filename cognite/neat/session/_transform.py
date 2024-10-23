from pathlib import Path
from typing import Any, cast, overload

from cognite.client import CogniteClient

from cognite.neat.rules._shared import ReadRules, VerifiedRules, InformationInputRules
from cognite.neat.rules.transformers import ToCompliantEntities
from cognite.neat.issues import IssueList
from ._state import SessionState


class TransformAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.data_model = DataModelTransformAPI(state, verbose)


class DataModelTransformAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def to_dms_compliant_external_ids(self) -> None:
        if input := self._state.information_input_rule:
            output = ToCompliantEntities().transform(input)
            self._state.input_rules.append(
                ReadRules(
                    rules=cast(InformationInputRules, output.rules),
                    issues=IssueList(),
                    read_context={},
                )
            )
