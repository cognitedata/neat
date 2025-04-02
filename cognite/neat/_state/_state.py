from abc import ABC, abstractmethod

from cognite.neat._graph.extractors import BaseExtractor
from cognite.neat._graph.transformers import BaseTransformer
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import InformationToDMS, VerifiedRulesTransformer
from cognite.neat._store import NeatGraphStore, NeatRulesStore

from ._types import Action


class State(ABC):
    def __init__(self, rule_store: NeatRulesStore, graph_store: NeatGraphStore) -> None:
        self._rule_store = rule_store
        self._graph_store = graph_store

    @property
    def display_name(self) -> str:
        return type(self).__name__.removesuffix("State")

    @abstractmethod
    def is_valid_transition(self, action: Action) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def next_state(self, action: Action) -> "State":
        raise NotImplementedError()


class EmptyState(State):
    def is_valid_transition(self, action: Action) -> bool:
        return isinstance(action, BaseImporter | BaseExtractor)

    def next_state(self, action: Action) -> "State":
        if isinstance(action, BaseExtractor):
            return InstancesState(self._rule_store, self._graph_store)
        elif isinstance(action, BaseImporter):
            return ConceptualState(self._rule_store, self._graph_store)
        raise NotImplementedError()


class InstancesState(State):
    def is_valid_transition(self, action: Action) -> bool:
        return isinstance(action, BaseTransformer)

    def next_state(self, action: Action) -> "State":
        raise NotImplementedError()


class ConceptualState(State):
    def is_valid_transition(self, action: Action) -> bool:
        return isinstance(action, VerifiedRulesTransformer)

    def next_state(self, action: Action) -> "State":
        if isinstance(action, InformationToDMS):
            return PhysicalState(self._rule_store, self._graph_store)
        return self


class PhysicalState(State):
    def is_valid_transition(self, action: Action) -> bool:
        return isinstance(action, VerifiedRulesTransformer)

    def next_state(self, action: Action) -> "State":
        return self
