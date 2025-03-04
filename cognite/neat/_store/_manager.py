from typing import TypeAlias

from cognite.neat._graph.extractors import BaseExtractor
from cognite.neat._graph.transformers import BaseTransformer, BaseTransformerStandardised
from cognite.neat._issues import IssueList
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import VerifiedRulesTransformer

from ._graph_store import NeatGraphStore
from ._rules_store import NeatRulesStore
from .exceptions import InvalidAction

Action: TypeAlias = (
    BaseExtractor | BaseTransformerStandardised | BaseTransformer | BaseImporter | VerifiedRulesTransformer
)


class NeatStoreManager:
    def __init__(self, instances: NeatGraphStore, rules: NeatRulesStore) -> None:
        self._instances = instances
        self._rules = rules

    def change(self, action: Action, description: str | None = None) -> IssueList:
        """Perform an action on the state of either the rule or instance store."""
        if error_message := self._can_perform(action):
            raise InvalidAction(description or action.description, error_message)  # type: ignore[union-attr]
        return self._perform(action)

    def _can_perform(self, action: Action) -> str:
        if isinstance(action, BaseExtractor) and not self._rules.empty:
            return "Cannot extract instances when a data model is in the session. You need to restart the session."
        raise NotImplementedError()

    def _perform(self, action: Action) -> IssueList:
        match action:
            case _ if isinstance(action, BaseExtractor):
                return self._instances.write(action)
            case _ if isinstance(action, BaseTransformerStandardised | BaseTransformer):
                return self._instances.transform(action)
            case _ if isinstance(action, BaseImporter):
                return self._rules.import_rules(action)
            case _ if isinstance(action, VerifiedRulesTransformer):
                return self._rules.transform(action)
            case _:
                raise NotImplementedError()
