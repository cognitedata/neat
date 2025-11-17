from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import yaml

from cognite.neat._data_model.exporters import DMSAPIJSONExporter, DMSAPIYAMLExporter
from cognite.neat._data_model.models.dms import RequestSchema


class TestYAMLExporter:
    def test_export_to_yaml(self, example_dms_schema_request: dict[str, Any]) -> None:
        """Test exporting DMS to YAML file."""
        schema = RequestSchema.model_validate(example_dms_schema_request)
        exporter = DMSAPIYAMLExporter()

        file_path = MagicMock(spec=Path)
        file_path.suffix = ".yaml"
        exporter.export_to_file(schema, file_path)

        content = file_path.write_text.call_args.args[0]
        loaded_content = yaml.safe_load(content)

        assert loaded_content == example_dms_schema_request, "Exported YAML content does not match the original schema."


class TestDMSAPIJSONExporter:
    def test_export_to_json(self, example_dms_schema_request: dict[str, Any]) -> None:
        """Test exporting DMS to JSON file."""
        schema = RequestSchema.model_validate(example_dms_schema_request)
        exporter = DMSAPIJSONExporter()

        file_path = MagicMock(spec=Path)
        file_path.suffix = ".json"
        exporter.export_to_file(schema, file_path)

        content = file_path.write_text.call_args.args[0]
        loaded_content = yaml.safe_load(content)  # Using yaml.safe_load to parse JSON content

        assert loaded_content == example_dms_schema_request, "Exported JSON content does not match the original schema."
