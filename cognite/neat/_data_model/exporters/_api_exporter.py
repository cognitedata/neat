from pathlib import Path

import yaml

from cognite.neat._data_model.exporters._base import DMSExporter, DMSFileExporter
from cognite.neat._data_model.models.dms import RequestSchema


class DMSAPIExporter(DMSExporter[RequestSchema]):
    def export(self, data_model: RequestSchema) -> RequestSchema:
        return data_model

    def export_to_file(self, data_model: RequestSchema, file_path: Path) -> None:
        raise RuntimeError(f"{type(self).__name__} does not support export_to_file method.")


class DMSAPIYAMLExporter(DMSAPIExporter, DMSFileExporter[RequestSchema]):
    def export_to_file(self, data_model: RequestSchema, file_path: Path) -> None:
        """Export the data model to a YAML file in API format."""
        if file_path.suffix.lower() not in {".yaml", ".yml"}:
            raise ValueError("The file path must have a .yaml or .yml extension.")

        api_format = data_model.model_dump(mode="json", by_alias=True)
        file_path.write_text(yaml.safe_dump(api_format, sort_keys=False), encoding=self.ENCODING, newline=self.NEW_LINE)


class DMSAPIJSONExporter(DMSAPIExporter, DMSFileExporter[RequestSchema]):
    def export_to_file(self, data_model: RequestSchema, file_path: Path) -> None:
        """Export the data model to a JSON file in API format."""
        if file_path.suffix.lower() != ".json":
            raise ValueError("The file path must have a .json extension.")

        file_path.write_text(
            data_model.model_dump_json(by_alias=True),
            encoding=self.ENCODING,
            newline=self.NEW_LINE,
        )
