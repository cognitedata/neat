from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._rules._shared import Rules
from cognite.neat._store._provenance import Agent as ProvenanceAgent

T_RulesIn = TypeVar("T_RulesIn", bound=Rules)
T_RulesOut = TypeVar("T_RulesOut", bound=Rules)


class RulesTransformer(ABC, Generic[T_RulesIn, T_RulesOut]):
    """This is the base class for all rule transformers."""

    @abstractmethod
    def transform(self, rules: T_RulesIn) -> T_RulesOut:
        """Transform the input rules into the output rules."""
        raise NotImplementedError()

    @property
    def agent(self) -> ProvenanceAgent:
        """Provenance agent for the importer."""
        return ProvenanceAgent(id_=DEFAULT_NAMESPACE[f"agent/{type(self).__name__}"])

    @property
    def description(self) -> str:
        """Get the description of the transformer."""
        return "MISSING DESCRIPTION"
