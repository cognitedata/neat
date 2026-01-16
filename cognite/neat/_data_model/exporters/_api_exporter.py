import warnings
import zipfile
from collections.abc import Iterator
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
        """Export the data model to a YAML files or zip file in API format.

        Args:
            data_model: Request schema
            file_path: The directory or zip file to save the schema to.

        """

        if file_path.is_dir():
            self._export_to_directory(data_model, file_path)
        else:
            self._export_to_zip_file(data_model, file_path)

    def _export_to_zip_file(self, data_model: RequestSchema, zip_file: Path) -> None:
        """Save the schema as a zip file containing a directory as YAML files.
        This is compatible with the Cognite-Toolkit convention.

        Args:
            data_model: Request schema
            zip_file: The zip file path to save the schema to.
        """
        if zip_file.suffix not in {".zip"}:
            warnings.warn("File extension is not .zip, adding it to the file name", stacklevel=2)
            zip_file = zip_file.with_suffix(".zip")

        with zipfile.ZipFile(zip_file, "w") as zip_ref:
            for file_path, yaml_content in self._generate_yaml_entries(data_model):
                zip_ref.writestr(f"data_models/{file_path}", yaml_content)

    def _export_to_directory(self, data_model: RequestSchema, directory: Path) -> None:
        """Save the schema to a directory as YAML files. This is compatible with the Cognite-Toolkit convention.

        Args:
            data_model: Request schema
            directory: The directory to save the schema to.
        """

        subdir = directory / "data_models"
        subdir.mkdir(parents=True, exist_ok=True)

        for file_path, yaml_content in self._generate_yaml_entries(data_model):
            full_path = subdir / file_path
            # Create parent directories if needed (e.g., for views/, containers/, nodes/)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(
                yaml_content,
                encoding=self.ENCODING,
                newline=self.NEW_LINE,
            )

    def _generate_yaml_entries(self, data_model: RequestSchema) -> Iterator[tuple[str, str]]:
        """Generate file paths and YAML content for all data model components.

        This helper method eliminates duplication by centralizing the logic for
        iterating through spaces, views, containers, and node types.

        Args:
            data_model: Request schema

        Yields:
            Tuples of (file_path, yaml_content) for each component.
            File paths are relative to the data_models directory.
        """
        # Export spaces
        for space in data_model.spaces:
            yield (
                f"{space.space}.space.yaml",
                yaml.safe_dump(space.model_dump(mode="json", by_alias=True), sort_keys=False),
            )

        # Export data model
        yield (
            f"{data_model.data_model.external_id}.datamodel.yaml",
            yaml.safe_dump(data_model.data_model.model_dump(mode="json", by_alias=True), sort_keys=False),
        )

        # Export views
        for view in data_model.views:
            yield (
                f"views/{view.external_id}.view.yaml",
                yaml.safe_dump(view.model_dump(mode="json", by_alias=True), sort_keys=False),
            )

        # Export containers
        for container in data_model.containers:
            yield (
                f"containers/{container.external_id}.container.yaml",
                yaml.safe_dump(container.model_dump(mode="json", by_alias=True), sort_keys=False),
            )

        # Export node types
        for node in data_model.node_types:
            yield (
                f"nodes/{node.external_id}.node.yaml",
                yaml.safe_dump(node.model_dump(mode="json", by_alias=True), sort_keys=False),
            )


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
