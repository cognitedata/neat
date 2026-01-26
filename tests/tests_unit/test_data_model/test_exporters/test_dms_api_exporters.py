import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import yaml

from cognite.neat._data_model.exporters import DMSAPIJSONExporter, DMSAPIYAMLExporter
from cognite.neat._data_model.models.dms import RequestSchema


class TestYAMLExporter:
    def test_export_to_directory(self, example_dms_schema_request: dict[str, Any], tmp_path: Path) -> None:
        """Test exporting DMS to a directory as multiple YAML files."""
        schema = RequestSchema.model_validate(example_dms_schema_request)
        exporter = DMSAPIYAMLExporter()

        export_dir = tmp_path / "export"
        export_dir.mkdir(parents=True, exist_ok=True)  # Create the directory first
        exporter.export_to_file(schema, export_dir)

        # Verify data_models directory was created
        data_models_dir = export_dir / "data_models"
        assert data_models_dir.exists(), "data_models directory not created"

        # Verify datamodel file exists
        datamodel_file = data_models_dir / f"{schema.data_model.external_id}.datamodel.yaml"
        assert datamodel_file.exists(), "datamodel YAML file not created"

        # Verify spaces are exported
        if schema.spaces:
            for space in schema.spaces:
                space_file = data_models_dir / f"{space.space}.space.yaml"
                assert space_file.exists(), f"space file {space_file} not created"

        # Verify views, containers, and node_types are exported
        component_checks: list[tuple[str, list, str]] = [
            ("views", schema.views, "view"),
            ("containers", schema.containers, "container"),
            ("nodes", schema.node_types, "node"),
        ]

        for dir_name, components, suffix in component_checks:
            if not components:
                continue

            component_dir = data_models_dir / dir_name
            assert component_dir.exists(), f"{dir_name} directory not created"
            for component in components:  # type: ignore[attr-defined]
                component_file = component_dir / f"{component.external_id}.{suffix}.yaml"
                assert component_file.exists(), f"file for {component.external_id} not created"

    def test_export_to_zip_file(self, example_dms_schema_request: dict[str, Any], tmp_path: Path) -> None:
        """Test exporting DMS to a zip file containing YAML files."""
        schema = RequestSchema.model_validate(example_dms_schema_request)
        exporter = DMSAPIYAMLExporter()

        zip_file = tmp_path / "export.zip"
        exporter.export_to_file(schema, zip_file)

        # Verify zip file was created
        assert zip_file.exists(), "Zip file not created"
        assert zipfile.is_zipfile(zip_file), "File is not a valid zip file"

        # Verify contents of zip file
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            actual_files = set(zip_ref.namelist())

            expected_files = {f"data_models/{schema.data_model.external_id}.datamodel.yaml"}
            if schema.spaces:
                expected_files.update(f"data_models/{s.space}.space.yaml" for s in schema.spaces)
            component_checks: list[tuple[str, list, str]] = [
                ("views", schema.views, "view"),
                ("containers", schema.containers, "container"),
                ("nodes", schema.node_types, "node"),
            ]
            for dir_name, components, suffix in component_checks:
                if components:
                    expected_files.update(f"data_models/{dir_name}/{c.external_id}.{suffix}.yaml" for c in components)  # type: ignore[attr-defined]

            assert actual_files == expected_files


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
        if "nodeTypes" not in example_dms_schema_request:
            assert loaded_content["nodeTypes"] is None or loaded_content["nodeTypes"] == []
            loaded_content.pop("nodeTypes", None)

        assert loaded_content == example_dms_schema_request, "Exported JSON content does not match the original schema."
