from collections.abc import Collection
from typing import Literal, cast

from cognite.client.data_classes.data_modeling import DataModelIdentifier

from cognite.neat._issues._base import IssueList
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._rules.transformers import ReduceCogniteModel, ToCompliantEntities, ToExtension

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

    def to_extension(self, new_data_model_id: DataModelIdentifier, prefix: str | None = None) -> None:
        """Uses the current data model as a basis to extend from.

        Args:
            new_data_model_id: The new data model that is extending the current data model.
            prefix: Prefix to use for the views in the new data model. This is required if the
                current data model is a Cognite Data Model.

        """
        if dms := self._state.last_verified_dms_rules:
            output = ToExtension(new_data_model_id, prefix).transform(dms)
            self._state.verified_rules.append(output.rules)

    def reduce(self, drop: Collection[Literal["3D", "Annotation", "BaseViews"]]) -> None:
        """This is a special method that allow you to drop parts of the data model.
        This only applies to Cognite Data Models.

        Args:
            drop: Which parts of the data model to drop.

        """
        if dms := self._state.last_verified_dms_rules:
            output = ReduceCogniteModel(drop).transform(dms)
            self._state.verified_rules.append(output.rules)
