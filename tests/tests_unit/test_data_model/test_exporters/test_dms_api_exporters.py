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

        # Verify views are exported
        if schema.views:
            views_dir = data_models_dir / "views"
            assert views_dir.exists(), "views directory not created"
            for view in schema.views:
                view_file = views_dir / f"{view.external_id}.view.yaml"
                assert view_file.exists(), f"view file {view_file} not created"

        # Verify containers are exported
        if schema.containers:
            containers_dir = data_models_dir / "containers"
            assert containers_dir.exists(), "containers directory not created"
            for container in schema.containers:
                container_file = containers_dir / f"{container.external_id}.container.yaml"
                assert container_file.exists(), f"container file {container_file} not created"

        # Verify node_types are exported
        if schema.node_types:
            nodes_dir = data_models_dir / "nodes"
            assert nodes_dir.exists(), "nodes directory not created"
            for node in schema.node_types:
                node_file = nodes_dir / f"{node.external_id}.node.yaml"
                assert node_file.exists(), f"node file {node_file} not created"

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
            file_names = zip_ref.namelist()

            # Verify datamodel file exists in zip
            datamodel_name = f"data_models/{schema.data_model.external_id}.datamodel.yaml"
            assert datamodel_name in file_names, f"datamodel file {datamodel_name} not in zip"

            # Verify spaces are in zip
            if schema.spaces:
                for space in schema.spaces:
                    space_name = f"data_models/{space.space}.space.yaml"
                    assert space_name in file_names, f"space file {space_name} not in zip"

            # Verify views are in zip
            if schema.views:
                for view in schema.views:
                    view_name = f"data_models/views/{view.external_id}.view.yaml"
                    assert view_name in file_names, f"view file {view_name} not in zip"

            # Verify containers are in zip
            if schema.containers:
                for container in schema.containers:
                    container_name = f"data_models/containers/{container.external_id}.container.yaml"
                    assert container_name in file_names, f"container file {container_name} not in zip"

            # Verify node_types are in zip
            if schema.node_types:
                for node in schema.node_types:
                    node_name = f"data_models/nodes/{node.external_id}.node.yaml"
                    assert node_name in file_names, f"node file {node_name} not in zip"


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
