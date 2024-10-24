


from typing import cast
from cognite.neat._issues._base import IssueList
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._rules.transformers._converters import ToCompliantEntities
from ._state import SessionState


class PrepareAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.data_model = DataModelPrepareAPI(state, verbose)


class DataModelPrepareAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose

    def cdf_compliant_external_ids(self) -> None:
        """Convert data model component external ids to CDF compliant entities."""
        if input := self._state.information_input_rule:
            output = ToCompliantEntities().transform(input)
            self._state.input_rules.append(
                ReadRules(
                    rules=cast(InformationInputRules, output.get_rules()),
                    issues=IssueList(),
                    read_context={},
                )
            )