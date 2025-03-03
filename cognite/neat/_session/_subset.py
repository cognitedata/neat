from typing import cast
import warnings


from cognite.client.data_classes.data_modeling import DataModelId


from cognite.neat._constants import COGNITE_CORE_CONCEPTS, COGNITE_CORE_FEATURES
from cognite.neat._alpha import ExperimentalFlags
from cognite.neat._client._api_client import NeatClient
from cognite.neat._issues._base import IssueList
from cognite.neat._rules import importers
from cognite.neat._rules.models.entities._single_value import ClassEntity, ViewEntity
from cognite.neat._rules.transformers import SubsetDMSRules, SubsetInformationRules
from cognite.neat._rules.transformers._converters import ToEnterpriseModel

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper

try:
    from rich import print
except ImportError:
    ...


@session_class_wrapper
class SubsetAPI:
    """
    Subset data model and instances in the session based on the desired subset of concepts.

    """

    def __init__(self, state: SessionState):
        self._state = state

    def data_model(self, concepts: str | list[str]) -> IssueList:
        """Subset the data model to the desired concepts.

        Args:
            concepts: The concepts to subset the data model to.

        Returns:
            IssueList: A list of issues that occurred during the transformation.

        Example:
            Read the CogniteCore data model and reduce the data model to only the 'CogniteAsset' concept.
            ```python
            neat = NeatSession(CogniteClient())

            neat.read.examples.core_data_model()

            neat.subset.data_model("CogniteAsset")
            ```
        """
        if self._state.rule_store.empty:
            raise NeatSessionError("No rules to set the data model ID.")

        warnings.filterwarnings("default")
        ExperimentalFlags.data_model_subsetting.warn()

        dms = self._state.rule_store.provenance[-1].target_entity.dms
        information = self._state.rule_store.provenance[-1].target_entity.information

        if dms:
            views = {
                ViewEntity(
                    space=dms.metadata.space,
                    externalId=concept,
                    version=dms.metadata.version,
                )
                for concept in concepts
            }

            issues = self._state.rule_transform(SubsetDMSRules(views=views))
            if not issues:
                after = len(self._state.rule_store.last_verified_dms_rules.views)

        elif information:
            classes = {ClassEntity(prefix=information.metadata.space, suffix=concept) for concept in concepts}

            issues = self._state.rule_transform(SubsetInformationRules(classes=classes))
            if not issues:
                after = len(self._state.rule_store.last_verified_information_rules.classes)

        else:
            raise NeatSessionError("Something went terrible wrong. Please contact the neat team.")

        if not issues:
            print(f"Subset to {after} concepts.")

        return issues


@session_class_wrapper
class DataModelSubsetAPI:
    def __init__(self, state: SessionState):
        self._state = state

    def __call__(self, concepts: str | list[str]) -> IssueList:
        """Subset the data model to the desired concepts.

        Args:
            concepts: The concepts to subset the data model to.

        Returns:
            IssueList: A list of issues that occurred during the transformation.

        Example:
            Read the CogniteCore data model and reduce the data model to only the 'CogniteAsset' concept.
            ```python
            neat = NeatSession(CogniteClient())

            neat.read.examples.core_data_model()

            neat.subset.data_model("CogniteAsset")
            ```
        """
        if self._state.rule_store.empty:
            raise NeatSessionError("No rules to set the data model ID.")

        warnings.filterwarnings("default")
        ExperimentalFlags.data_model_subsetting.warn()

        dms = self._state.rule_store.provenance[-1].target_entity.dms
        information = self._state.rule_store.provenance[-1].target_entity.information

        if dms:
            views = {
                ViewEntity(
                    space=dms.metadata.space,
                    externalId=concept,
                    version=dms.metadata.version,
                )
                for concept in concepts
            }

            issues = self._state.rule_transform(SubsetDMSRules(views=views))
            if not issues:
                after = len(self._state.rule_store.last_verified_dms_rules.views)

        elif information:
            classes = {
                ClassEntity(prefix=information.metadata.space, suffix=concept)
                for concept in concepts
            }

            issues = self._state.rule_transform(SubsetInformationRules(classes=classes))
            if not issues:
                after = len(
                    self._state.rule_store.last_verified_information_rules.classes
                )

        else:
            raise NeatSessionError(
                "Something went terrible wrong. Please contact the neat team."
            )

        if not issues:
            print(f"Subset to {after} concepts.")

        return issues

    def core_data_model(self, concepts: str | list[str]) -> IssueList:
        """Subset the data model to the desired concepts.

        Args:
            concepts: The concepts to subset the data model to.

        Returns:
            IssueList: A list of issues that occurred during the transformation.

        Example:
            Read the CogniteCore data model and reduce the data model to only the 'CogniteAsset' concept.
            ```python
            neat = NeatSession(CogniteClient())

            neat.subset.data_model.core_data_model(concepts=["CogniteAsset", "CogniteEquipment"])
            ```

        !!! note "Bundle of actions"
            This method is helper method that bundles the following actions:
            - Import the Cognite Core Data Model
            - Makes editable copy of the Cognite Core Data Model concepts
            - Subsets the copy to the desired concepts
            which will be otherwise done by calling multiple methods

        """

        concepts = concepts if isinstance(concepts, list | set) else [concepts]

        self._state._raise_exception_if_condition_not_met(
            "Subset Core Data Model",
            empty_rules_store_required=True,
            client_required=True,
        )

        warnings.filterwarnings("default")
        ExperimentalFlags.core_data_model_subsetting.warn()

        if not_in_cognite_core := set(concepts) - COGNITE_CORE_CONCEPTS.union(
            COGNITE_CORE_FEATURES
        ):
            raise NeatSessionError(
                f"Concept(s) {', '.join(not_in_cognite_core)} is/are not part of the Cognite Core Data Model"
            )

        cdm_v1 = DataModelId.load(("cdf_cdm", "CogniteCore", "v1"))
        importer: importers.DMSImporter = importers.DMSImporter.from_data_model_id(
            cast(NeatClient, self._state), cdm_v1
        )
        issues = self._state.rule_import(importer)

        if issues.has_errors:
            return issues

        issues.extend(
            self._state.rule_transform(
                ToEnterpriseModel(
                    new_model_id=("my_space", "MyCDMSubset", "v1"),
                    org_name="CopyOf",
                    dummy_property="GUID",
                    move_connections=True,
                )
            )
        )

        if issues.has_errors:
            return issues

        views_to_remove = { for view in self._state.rule_store.last_verified_dms_rules.views if view.view.external_id not in concepts}
