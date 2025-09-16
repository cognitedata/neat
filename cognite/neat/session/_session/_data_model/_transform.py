from cognite.neat.core._data_model.transformers._converters import (
    PrefixEntities,
    StandardizeNaming,
    StandardizeSpaceAndVersion,
    ToCompliantEntities,
)
from cognite.neat.core._issues._base import IssueList
from cognite.neat.session._state import SessionState
from cognite.neat.session.exceptions import session_class_wrapper


@session_class_wrapper
class TransformAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def cdf_compliant_external_ids(self) -> IssueList:
        """Convert conceptual data model component external ids to CDF compliant ids."""
        return self._state.data_model_transform(ToCompliantEntities())

    def prefix(self, prefix: str) -> IssueList:
        """Prefix all views in the data model with the given prefix.

        Args:
            prefix: The prefix to add to the views in the data model.

        """

        return self._state.data_model_transform(PrefixEntities(prefix))  # type: ignore[arg-type]

    def standardize_naming(self) -> IssueList:
        """Standardize the naming of all views/concepts/properties in the data model.

        For concepts/views/containers, the naming will be standardized to PascalCase.
        For properties, the naming will be standardized to camelCase.
        """
        return self._state.data_model_transform(StandardizeNaming())

    def standardize_space_and_version(self) -> IssueList:
        """Standardize space and version in the data model.

        This method will standardize the space and version in the data model to the Cognite standard.
        """
        return self._state.data_model_transform(StandardizeSpaceAndVersion())
