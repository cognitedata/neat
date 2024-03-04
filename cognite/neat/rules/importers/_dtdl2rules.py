from pathlib import Path
from typing import Literal, overload

from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.validation import IssueList

from ._base import BaseImporter


class DTDLImporter(BaseImporter):
    def __init__(
        self,
    ):
        ...

    @classmethod
    def from_directory(cls, directory: Path) -> "DTDLImporter":
        raise NotImplementedError()

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> InformationRules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[InformationRules | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[InformationRules | None, IssueList] | InformationRules:
        raise NotImplementedError()
