import warnings
from pathlib import Path

from cognite.neat.rules.models._rules.dms_architect_rules import DMSRules
from cognite.neat.rules.models._rules.dms_schema import DMSSchema

from ._base import BaseExporter


class DMSExporter(BaseExporter[DMSSchema]):
    """Class for exporting rules object to CDF Data Model Storage (DMS).

    Args:
        rules: Domain Model Service Architect rules object.
    """

    def __init__(
        self,
        rules: DMSRules,
    ):
        self.rules = rules

    def export_to_file(self, filepath: Path) -> None:
        if filepath.suffix not in {".zip"}:
            warnings.warn("File extension is not .zip, adding it to the file name", stacklevel=2)
            filepath = filepath.with_suffix(".zip")
        raise NotImplementedError("Export to file is not implemented yet")

    def export(self) -> DMSSchema:
        return self.rules.as_schema()
