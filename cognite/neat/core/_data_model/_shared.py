from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from cognite.neat.core._data_model.models import (
    DMSRules,
    ConceptualDataModel,
)
from cognite.neat.core._data_model.models.physical._rules_input import DMSInputRules
from cognite.neat.core._data_model.models.conceptual._unvalidate_data_model import (
    ConceptualUnvalidatedDataModel,
)
from cognite.neat.core._utils.spreadsheet import SheetRowTracker

VerifiedRules: TypeAlias = ConceptualDataModel | DMSRules

T_VerifiedRules = TypeVar("T_VerifiedRules", bound=VerifiedRules)
InputRules: TypeAlias = DMSInputRules | ConceptualUnvalidatedDataModel
T_InputRules = TypeVar("T_InputRules", bound=InputRules)


@dataclass
class ReadRules(Generic[T_InputRules]):
    """This represents a rules that has been read."""

    rules: T_InputRules | None
    read_context: dict[str, SheetRowTracker]

    @classmethod
    def display_type_name(cls) -> str:
        return "UnverifiedModel"

    @property
    def display_name(self) -> str:
        if self.rules is None:
            return "FailedRead"
        return self.rules.display_name


ReadInputRules: TypeAlias = (
    ReadRules[DMSInputRules] | ReadRules[ConceptualUnvalidatedDataModel]
)
T_ReadInputRules = TypeVar("T_ReadInputRules", bound=ReadInputRules)

Rules: TypeAlias = (
    ConceptualDataModel
    | DMSRules
    | ReadRules[DMSInputRules]
    | ReadRules[ConceptualUnvalidatedDataModel]
)
T_Rules = TypeVar("T_Rules", bound=Rules)
