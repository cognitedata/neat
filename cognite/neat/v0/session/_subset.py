import warnings

from cognite.neat.v0.core._data_model.models.entities._single_value import (
    ConceptEntity,
    ViewEntity,
)
from cognite.neat.v0.core._data_model.transformers import (
    SubsetConceptualDataModel,
    SubsetPhysicalDataModel,
)
from cognite.neat.v0.core._issues._base import IssueList
from cognite.neat.v0.session._experimental import ExperimentalFlags

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
        if self._state.data_model_store.empty:
            raise NeatSessionError("No data model to set the data model ID.")

        warnings.filterwarnings("default")
        ExperimentalFlags.data_model_subsetting.warn()

        dms = self._state.data_model_store.provenance[-1].target_entity.physical
        information = self._state.data_model_store.provenance[-1].target_entity.conceptual

        if dms:
            views = {
                ViewEntity(
                    space=dms.metadata.space,
                    externalId=concept,
                    version=dms.metadata.version,
                )
                for concept in concepts
            }

            issues = self._state.data_model_transform(SubsetPhysicalDataModel(views=views))
            if not issues:
                after = len(self._state.data_model_store.last_verified_physical_data_model.views)

        elif information:
            classes = {ConceptEntity(prefix=information.metadata.space, suffix=concept) for concept in concepts}

            issues = self._state.data_model_transform(SubsetConceptualDataModel(concepts=classes))
            if not issues:
                after = len(self._state.data_model_store.last_verified_conceptual_data_model.concepts)

        else:
            raise NeatSessionError("Something went terrible wrong. Please contact the neat team.")

        if not issues:
            print(f"Subset to {after} concepts.")

        return issues
