import warnings
import zipfile
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

        schema = self.export()
        with zipfile.ZipFile(filepath, "w") as zip_ref:
            for space in schema.spaces:
                zip_ref.writestr(f"data_models/{space.space}.space.yaml", space.dump_yaml())
            for model in schema.data_models:
                zip_ref.writestr(f"data_models/{model.external_id}.datamodel.yaml", model.dump_yaml())
            for view in schema.views:
                zip_ref.writestr(f"data_models/{view.external_id}.view.yaml", view.dump_yaml())
            for container in schema.containers:
                zip_ref.writestr(f"data_models/{container.external_id}.container.yaml", container.dump_yaml())

    def export(self) -> DMSSchema:
        return self.rules.as_schema()
