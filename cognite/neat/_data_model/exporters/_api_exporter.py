from pathlib import Path

import yaml
from pyparsing import ABC

from cognite.neat._data_model.exporters._base import DMSExporter
from cognite.neat._data_model.models.dms import RequestSchema


class DMSAPIExporter(DMSExporter[RequestSchema], ABC):
    def export(self, data_model: RequestSchema) -> RequestSchema:
        return data_model


class DMSAPIYAMLExporter(DMSAPIExporter):
    def export_to_file(self, data_model: RequestSchema, file_path: Path) -> None:
        """Export the data model to a YAML file in API format."""
        if file_path.suffix.lower() not in {".yaml", ".yml"}:
            raise ValueError("The file path must have a .yaml or .yml extension.")

        api_format = data_model.model_dump(mode="json")
        file_path.write_text(yaml.safe_dump(api_format, sort_keys=False), encoding=self.ENCODING, newline=self.NEW_LINE)
