import warnings
from pathlib import Path

from cognite.client import data_modeling as dm

from cognite.neat.rules.models._rules.dms_architect_rules import DMSRules
from cognite.neat.rules.models._rules.dms_schema import DMSSchema

from ._base import BaseExporter


class DMSExporter(BaseExporter[DMSSchema]):
    """Class for exporting transformation rules object to CDF Data Model Storage (DMS).

    Args:
        rules: Transformation rules object.
        data_model_id: The id of the data model to be created.
        existing_model: In the case of updating an existing model, this is the existing model.
        report: Report. This is used when the exporter object is created from RawRules
    """

    def _export_to_file(self, filepath: Path) -> None:
        pass

    def __init__(
        self,
        rules: DMSRules,
        data_model_id: dm.DataModelId | None = None,
        existing_model: dm.DataModel[dm.ViewId] | None = None,
        report: str | None = None,
    ):
        self.rules = rules
        self.report = report
        self.data_model_id = data_model_id
        self.existing_model = existing_model

    def export_to_file(self, filepath: Path) -> None:
        if filepath.suffix not in {".zip"}:
            warnings.warn("File extension is not .zip, adding it to the file name", stacklevel=2)
            filepath = filepath.with_suffix(".zip")
            print(filepath)
        raise NotImplementedError("Export to file is not implemented yet")

    def export(self) -> DMSSchema:
        return self.rules.as_schema()
