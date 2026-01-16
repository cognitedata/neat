import warnings
import zipfile
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

        if file_path.is_dir():
            self._export_to_directory(data_model, file_path)
        else:
            self._export_to_zip_file(data_model, file_path)

    def _export_to_zip_file(self, data_model: RequestSchema, zip_file: Path) -> None:
        """Save the schema as a zip file containing a directory as YAML files.
        This is compatible with the Cognite-Toolkit convention.

        Args:
            data_model: RequestSchema
            zip_file Path: The zip file to save the schema to.
        """
        if zip_file.suffix not in {".zip"}:
            warnings.warn("File extension is not .zip, adding it to the file name", stacklevel=2)
            zip_file = zip_file.with_suffix(".zip")

        with zipfile.ZipFile(zip_file, "w") as zip_ref:
            for space in data_model.spaces:
                zip_ref.writestr(
                    f"data_models/{space.space}.space.yaml",
                    yaml.safe_dump(space.model_dump(mode="json", by_alias=True), sort_keys=False),
                )

            zip_ref.writestr(
                f"data_models/{data_model.data_model.external_id}.datamodel.yaml",
                yaml.safe_dump(data_model.data_model.model_dump(mode="json", by_alias=True), sort_keys=False),
            )

            for view in data_model.views:
                zip_ref.writestr(
                    f"data_models/views/{view.external_id}.view.yaml",
                    yaml.safe_dump(view.model_dump(mode="json", by_alias=True), sort_keys=False),
                )

            for container in data_model.containers:
                zip_ref.writestr(
                    f"data_models/containers/{container.external_id}.container.yaml",
                    yaml.safe_dump(container.model_dump(mode="json", by_alias=True), sort_keys=False),
                )

            for node in data_model.node_types:
                zip_ref.writestr(
                    f"data_models/nodes/{node.external_id}.node.yaml",
                    yaml.safe_dump(container.model_dump(mode="json", by_alias=True), sort_keys=False),
                )

    def _export_to_directory(self, data_model: RequestSchema, directory: Path) -> None:
        """Save the schema to a directory as YAML files. This is compatible with the Cognite-Toolkit convention.

        Args:
            data_model: RequestSchema
            directory Path: The directory to save the schema to.
        """

        subdir = directory / "data_models"
        subdir.mkdir(parents=True, exist_ok=True)

        if data_model.spaces:
            for space in data_model.spaces:
                (subdir / f"{space.space}.space.yaml").write_text(
                    yaml.safe_dump(space.model_dump(mode="json", by_alias=True), sort_keys=False),
                    encoding=self.ENCODING,
                    newline=self.NEW_LINE,
                )

        (subdir / f"{data_model.data_model.external_id}.datamodel.yaml").write_text(
            yaml.safe_dump(data_model.data_model.model_dump(mode="json", by_alias=True), sort_keys=False),
            encoding=self.ENCODING,
            newline=self.NEW_LINE,
        )

        if data_model.views:
            views_dir = subdir / "views"
            views_dir.mkdir(parents=True, exist_ok=True)

            for view in data_model.views:
                (views_dir / f"{view.external_id}.view.yaml").write_text(
                    yaml.safe_dump(view.model_dump(mode="json", by_alias=True), sort_keys=False),
                    encoding=self.ENCODING,
                    newline=self.NEW_LINE,
                )

        if data_model.containers:
            containers_dir = subdir / "containers"
            containers_dir.mkdir(parents=True, exist_ok=True)

            for container in data_model.views:
                (containers_dir / f"{container.external_id}.container.yaml").write_text(
                    yaml.safe_dump(container.model_dump(mode="json", by_alias=True), sort_keys=False),
                    encoding=self.ENCODING,
                    newline=self.NEW_LINE,
                )

        if data_model.node_types:
            nodes_dir = subdir / "nodes"
            nodes_dir.mkdir(parents=True, exist_ok=True)

            for node in data_model.node_types:
                (nodes_dir / f"{node.external_id}.node.yaml").write_text(
                    yaml.safe_dump(node.model_dump(mode="json", by_alias=True), sort_keys=False),
                    encoding=self.ENCODING,
                    newline=self.NEW_LINE,
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
