import inspect
from abc import ABC, abstractmethod
from functools import lru_cache
from types import UnionType
from typing import Generic, TypeVar, Union, get_args, get_origin

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._rules._shared import ReadRules, Rules, VerifiedRules
from cognite.neat._rules.models import DMSInputRules, InformationInputRules
from cognite.neat._store._provenance import Agent as ProvenanceAgent

T_RulesIn = TypeVar("T_RulesIn", bound=Rules)
T_RulesOut = TypeVar("T_RulesOut", bound=Rules)
T_VerifiedIn = TypeVar("T_VerifiedIn", bound=VerifiedRules)
T_VerifiedOut = TypeVar("T_VerifiedOut", bound=VerifiedRules)


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

    def is_valid_input(self, rules: T_RulesIn) -> bool:
        """Check if the input rules are valid."""
        types = self.transform_type_hint()
        for type_ in types:
            if get_origin(type_) is ReadRules:
                inner = get_args(type_)[0]
                if isinstance(rules, ReadRules) and isinstance(rules.rules, inner):
                    return True
            elif isinstance(rules, type_):
                return True
        return False

    @classmethod
    @lru_cache(maxsize=1)
    def transform_type_hint(cls) -> tuple[type, ...]:
        # This is an expensive operation, so we cache the result
        signature = inspect.signature(cls.transform)
        annotation = signature.parameters["rules"].annotation
        if isinstance(annotation, TypeVar):
            if annotation.__bound__ is None:
                raise TypeError(f"TypeVar {annotation} must be bound to a type.")
            annotation = annotation.__bound__
        # The annotation can be a type or a generic
        if get_origin(annotation) in [UnionType, Union]:
            return get_args(annotation)

        if get_origin(annotation) is ReadRules and isinstance(get_args(annotation)[0], TypeVar):
            # Hardcoded for now, as we only have two types of ReadRules
            return ReadRules[DMSInputRules], ReadRules[InformationInputRules]

        return (annotation,)


class VerifiedRulesTransformer(RulesTransformer[T_VerifiedIn, T_VerifiedOut], ABC): ...
