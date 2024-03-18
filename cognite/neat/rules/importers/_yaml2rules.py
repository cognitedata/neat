from pathlib import Path
from typing import Literal, overload, Any

from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models._rules import RoleTypes
from ._base import BaseImporter, Rules


class YAMLImporter(BaseImporter):
    """Imports the rules from a YAML file.

    Args:
        raw_data: The raw data to be imported.

    .. note::

        YAML files are typically used for storing rules when checked into version control systems, e.g., git-history.
        The advantage of using YAML files over Excel is that tools like git can show the differences between different
        versions of the rules.

    """
    def __init__(self, raw_data: dict[str, Any]):
        self.raw_data = raw_data

    @classmethod
    def from_file(cls, filepath: Path):
        ...

    @classmethod
    def from_directory(cls, directory: Path):
        ...

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        ...
