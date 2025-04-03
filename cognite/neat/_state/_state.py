from abc import ABC, abstractmethod

from cognite.neat._graph.extractors import BaseExtractor
from cognite.neat._graph.transformers import BaseTransformer
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.transformers import InformationToDMS, VerifiedRulesTransformer
from cognite.neat._store import NeatGraphStore, NeatRulesStore

from ._types import Action


class InternalState(ABC):
    """This is the base class for all internal states (internal to this module)

    This implements a state machine which is used by the NeatState which is the
    external (related to this module) API.
    """

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
    def next_state(self, action: Action) -> "InternalState":
        raise NotImplementedError()


class EmptyState(InternalState):
    def is_valid_transition(self, action: Action) -> bool:
        return isinstance(action, BaseImporter | BaseExtractor)

    def next_state(self, action: Action) -> "InternalState":
        if isinstance(action, BaseExtractor):
            return InstancesState(self._rule_store, self._graph_store)
        elif isinstance(action, BaseImporter):
            return ConceptualState(self._rule_store, self._graph_store)
        raise NotImplementedError()


class InstancesState(InternalState):
    def is_valid_transition(self, action: Action) -> bool:
        return isinstance(action, BaseTransformer)

    def next_state(self, action: Action) -> "InternalState":
        raise NotImplementedError()


class ConceptualState(InternalState):
    def is_valid_transition(self, action: Action) -> bool:
        return isinstance(action, VerifiedRulesTransformer)

    def next_state(self, action: Action) -> "InternalState":
        if isinstance(action, InformationToDMS):
            return PhysicalState(self._rule_store, self._graph_store)
        return self


class PhysicalState(InternalState):
    def is_valid_transition(self, action: Action) -> bool:
        return isinstance(action, VerifiedRulesTransformer)

    def next_state(self, action: Action) -> "InternalState":
        return self
