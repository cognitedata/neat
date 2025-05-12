from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from cognite.neat.core._data_model.models import (
    ConceptualDataModel,
    PhysicalDataModel,
)
from cognite.neat.core._data_model.models.conceptual._unverified import (
    UnverifiedConceptualDataModel,
)
from cognite.neat.core._data_model.models.dms._unverified import (
    UnverifiedPhysicalDataModel,
)
from cognite.neat.core._utils.spreadsheet import SpreadsheetRead

VerifiedRules: TypeAlias = ConceptualDataModel | PhysicalDataModel

T_VerifiedRules = TypeVar("T_VerifiedRules", bound=VerifiedRules)
InputRules: TypeAlias = UnverifiedPhysicalDataModel | UnverifiedConceptualDataModel
T_InputRules = TypeVar("T_InputRules", bound=InputRules)


@dataclass
class ReadRules(Generic[T_InputRules]):
    """This represents a rules that has been read."""

    rules: T_InputRules | None
    read_context: dict[str, SpreadsheetRead]

    @classmethod
    def display_type_name(cls) -> str:
        return "UnverifiedModel"

    @property
    def display_name(self) -> str:
        if self.rules is None:
            return "FailedRead"
        return self.rules.display_name


ReadInputRules: TypeAlias = ReadRules[UnverifiedPhysicalDataModel] | ReadRules[UnverifiedConceptualDataModel]
T_ReadInputRules = TypeVar("T_ReadInputRules", bound=ReadInputRules)

Rules: TypeAlias = (
    ConceptualDataModel
    | PhysicalDataModel
    | ReadRules[UnverifiedPhysicalDataModel]
    | ReadRules[UnverifiedConceptualDataModel]
)
T_Rules = TypeVar("T_Rules", bound=Rules)
