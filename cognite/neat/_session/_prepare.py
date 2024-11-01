from collections.abc import Collection
from typing import Literal, cast

from cognite.client.data_classes.data_modeling import DataModelIdentifier

from cognite.neat._issues._base import IssueList
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._rules.transformers import ReduceCogniteModel, ToCompliantEntities, ToExtension

from ._state import SessionState
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class PrepareAPI:
    def __init__(self, state: SessionState, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.data_model = DataModelPrepareAPI(state, verbose)


@intercept_session_exceptions
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

    def to_enterprise(
        self,
        data_model_id: DataModelIdentifier,
        org_name: str = "My",
        dummy_property: str = "GUID",
    ) -> None:
        """Uses the current data model as a basis to create enterprise data model

        Args:
            data_model_id: The enterprise data model id that is being created
            org_name: Organization name to use for the views in the enterprise data model.
            dummy_property: The dummy property to use as placeholder for the views in the new data model.

        !!! note "Enterprise Data Model Creation"
            Always create an enterprise data model from a Cognite Data Model as this will
            assure all the Cognite Data Fusion applications to run smoothly, such as
            - Search
            - Atlas AI
            - ...

        """
        if dms := self._state.last_verified_dms_rules:
            output = ToExtension(
                new_model_id=data_model_id,
                org_name=org_name,
                type_="enterprise",
                dummy_property=dummy_property,
            ).transform(dms)
            self._state.verified_rules.append(output.rules)

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
        if dms := self._state.last_verified_dms_rules:
            output = ToExtension(
                new_model_id=data_model_id,
                org_name=org_name,
                type_="solution",
                mode=mode,
                dummy_property=dummy_property,
            ).transform(dms)
            self._state.verified_rules.append(output.rules)

    def reduce(self, drop: Collection[Literal["3D", "Annotation", "BaseViews"] | str]) -> None:
        """This is a special method that allow you to drop parts of the data model.
        This only applies to Cognite Data Models.

        Args:
            drop: What to drop from the data model. The values 3D, Annotation, and BaseViews are special values that
                drops multiple views at once. You can also pass externalIds of views to drop individual views.

        """
        if dms := self._state.last_verified_dms_rules:
            output = ReduceCogniteModel(drop).transform(dms)
            self._state.verified_rules.append(output.rules)
