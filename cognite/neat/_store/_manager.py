from typing import TypeAlias

from cognite.neat._graph.extractors import BaseExtractor
from cognite.neat._graph.transformers import Transformers
from cognite.neat._issues import IssueList
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import RulesTransformer

from ._graph_store import NeatGraphStore
from ._rules_store import NeatRulesStore
from .exceptions import InvalidAction

Action: TypeAlias = BaseExtractor | Transformers | BaseImporter | RulesTransformer


class NeatStoreManager:
    def __init__(self, instances: NeatGraphStore, rules: NeatRulesStore) -> None:
        self._instances = instances
        self._rules = rules

    def change(self, action: Action, description: str | None = None) -> IssueList:
        """Perform an action on the state of either the rule or instance store."""
        if error_message := self._can_perform(action):
            raise InvalidAction(description or action.description, error_message)  # type: ignore[union-attr]
        return self._perform(action, description)

    def _can_perform(self, action: Action) -> str:
        if isinstance(action, BaseExtractor) and not self._rules.empty:
            return "Cannot extract instances after a data model has been imported."
        raise NotImplementedError()

    def _perform(self, action: Action, description: str | None = None) -> IssueList:
        raise NotImplementedError()
