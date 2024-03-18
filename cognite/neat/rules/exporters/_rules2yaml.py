from pathlib import Path
from typing import Literal, get_args

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models._rules.base import RoleTypes
from ._base import BaseExporter


class YAMLExporter(BaseExporter[str]):
    """Export rules to YAML.

    Args:
        format: Whether to output the rules as multiple or a single YAML file(s). Defaults to "multiple".

    The following formats are available:

    - "single": A single YAML file will containe the entire rules.
    - "multiple": Each section in the rules (e.g. same as sheets in the spreadsheet exporter) will be exported to
                    a separate YAML file.
    .. note::

        YAML files are typically used for storing rules when checked into version control systems, e.g., git-history.
        The advantage of using YAML files over Excel is that tools like git can show the differences between different
        versions of the rules.

    """

    Format = Literal["single", "multiple"]

    format_options = get_args(Format)

    def __init__(self, format_: Format = "multiple", output_role: RoleTypes | None = None):
        if format_ not in self.format_options:
            raise ValueError(f"Invalid format: {format_}. Valid options are {self.format_options}")
        self.format = format_
        self.output_role = output_role

    def export_to_file(self, filepath: Path, rules: Rules) -> None:
        """Exports transformation rules to YAML file(s)."""
        raise NotImplementedError()

    def export(self, rules: Rules) -> str:
        rules = self._convert_to_output_role(rules, self.output_role)
