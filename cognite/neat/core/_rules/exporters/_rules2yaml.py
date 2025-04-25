import json
import warnings
from pathlib import Path
from typing import Literal, get_args

import yaml

from cognite.neat._rules._shared import VerifiedRules

from ._base import BaseExporter


class YAMLExporter(BaseExporter[VerifiedRules, str]):
    """Export rules (Information, DMS or Domain) to YAML.

    Args:
        files: The number of files to output. Defaults to "single".
        output: The format to output the rules. Defaults to "yaml".

    The following formats are available:

    - "single": A single YAML file will contain the entire rules.

    .. note::

        YAML files are typically used for storing rules when checked into version control systems, e.g., git-history.
        The advantage of using YAML files over Excel is that tools like git can show the differences between different
        versions of the rules.

    """

    Files = Literal["single"]
    Format = Literal["yaml", "json"]

    file_option = get_args(Files)
    format_option = get_args(Format)

    def __init__(self, files: Files = "single", output: Format = "yaml"):
        if files not in self.file_option:
            raise ValueError(f"Invalid files: {files}. Valid options are {self.file_option}")
        if output not in self.format_option:
            raise ValueError(f"Invalid output: {output}. Valid options are {self.format_option}")
        self.files = files
        self.output = output

    @property
    def description(self) -> str:
        return "Export verified model to YAML."

    def export_to_file(self, rules: VerifiedRules, filepath: Path) -> None:
        """Exports transformation rules to YAML/JSON file(s)."""
        if self.files == "single":
            if filepath.suffix != f".{self.output}":
                warnings.warn(f"File extension is not .{self.output}, adding it to the file name", stacklevel=2)
                filepath = filepath.with_suffix(f".{self.output}")
            filepath.write_text(self.export(rules), encoding=self._encoding, newline=self._new_line)
        else:
            raise NotImplementedError(f"Exporting to {self.files} files is not supported")

    def export(self, rules: VerifiedRules) -> str:
        """Export rules to YAML (or JSON) format.

        This will export the rules to YAML format if the output is set to "yaml" and JSON format if the output is set.
        All None and Unset values are excluded from the output to keep the output clean, i.e., only the values the user
        has set.

        Args:
            rules: The rules to be exported.

        Returns:
            str: The rules in YAML (or JSON) format.
        """
        # model_dump_json ensures that the output is in JSON format,
        # if we don't do this, we will get Enums and other types that are not serializable to YAML
        json_output = rules.dump(mode="json", sort=True, exclude_none=True, exclude_unset=True)
        if self.output == "json":
            return json.dumps(json_output)
        elif self.output == "yaml":
            return yaml.safe_dump(json_output)
        else:
            raise ValueError(f"Invalid output: {self.output}. Valid options are {self.format_option}")
