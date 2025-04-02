from pathlib import Path

from cognite.neat._client import NeatClient
from cognite.neat._graph.extractors import BaseExtractor
from cognite.neat._graph.loaders import BaseLoader
from cognite.neat._graph.transformers import BaseTransformer
from cognite.neat._issues import IssueList
from cognite.neat._rules.exporters import BaseExporter, CDFExporter
from cognite.neat._rules.exporters._base import T_Export, T_VerifiedRules
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import VerifiedRulesTransformer
from cognite.neat._store import NeatGraphStore, NeatRulesStore
from cognite.neat._utils.upload import UploadResultList

from ._state import EmptyState, State
from ._types import Action
from .exception import InvalidStateTransition


# Todo: This class is in progress and not currently used. Through a series of PRs, it will replace the
#  SessionState class as well as move the logic from the _session into this _state module.
class NeatState:
    """The neat state contains three main components:

    - Instances: stored in a triple store.
    - Conceptual rules: The schema for conceptual rules.
    - Physical rules: The schema for physical rules.
    """

    def __init__(self) -> None:
        self._rule_store = NeatRulesStore()
        self._graph_store = NeatGraphStore.from_memory_store()
        self._state: State = EmptyState(self._rule_store, self._graph_store)

    @property
    def status(self) -> str:
        """Returns the display name of the current state."""
        return self._state.display_name

    def change(self, action: Action) -> IssueList:
        """Perform an action on the current state.

        This methods checks if the action is valid for the current state, performs the action, and if successful,
        transitions to the next state. If the action is not valid, it raises an InvalidStateTransition error.

        Args:
            action (Action): The action to perform.

        Raises:
            InvalidStateTransition: If the action is not valid for the current state.
            TypeError: If the action is of an unknown type.

        Returns:
            IssueList: The issues encountered during the action.

        """
        if not self._state.is_valid_transition(action):
            raise InvalidStateTransition(
                f"Cannot perform {type(action).__name__} action in state {self._state.display_name}"
            )
        if isinstance(action, BaseImporter):
            issues = self._rule_store.import_rules(action)
        elif isinstance(action, BaseExtractor):
            issues = self._graph_store.write(action)
        elif isinstance(action, VerifiedRulesTransformer):
            issues = self._rule_store.transform(action)
        elif isinstance(action, BaseTransformer):
            # The self._graph_store.transform(action) does not return IssueList
            raise NotImplementedError()
        else:
            raise TypeError(f"Unknown action type: {type(action).__name__}")
        if not issues.has_errors:
            self._state = self._state.next_state(action)
        return issues

    def export(self, exporter: BaseExporter[T_VerifiedRules, T_Export]) -> T_Export:  # type: ignore[type-arg, type-var]
        """Export the rules to the specified format."""
        raise NotImplementedError

    def export_to_file(self, exporter: BaseExporter, path: Path) -> None:
        """Export the rules to a file."""
        raise NotImplementedError

    def export_to_cdf(self, exporter: CDFExporter, client: NeatClient, dry_run: bool) -> UploadResultList:
        """Export the rules to CDF."""
        raise NotImplementedError

    def load(self, loader: BaseLoader) -> UploadResultList:
        """Load the instances into CDF."""
        raise NotImplementedError
