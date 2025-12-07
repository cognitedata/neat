from cognite.neat._data_model.deployer.data_classes import DeploymentResult
from cognite.neat._session._html._render import render
from cognite.neat._store import NeatStore

from ._deployment._physical.serializer import serialize_deployment_result


class Result:
    """Class to handle deployment results in the NeatSession."""

    def __init__(self, store: NeatStore) -> None:
        self._store = store

    @property
    def _result(self) -> DeploymentResult | None:
        """Get deployment result from the last change in the store."""
        if change := self._store.provenance.last_change:
            if change.result:
                return change.result
        return None

    def _repr_html_(self) -> str:
        """Generate interactive HTML representation."""
        if not self._result:
            return "<p>No deployment result available</p>"

        if isinstance(self._result, DeploymentResult):
            serialized_result = serialize_deployment_result(self._result)
            return render("deployment", serialized_result)
        else:
            raise NotImplementedError(f"HTML rendering for the result type {type(self._result)} is not implemented.")
