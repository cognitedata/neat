import difflib
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from cognite.neat._client import NeatClient
from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.importers._base import DMSImporter
from cognite.neat._data_model.models.dms import (
    DataModelReference,
    RequestSchema,
    SpaceReference,
)
from cognite.neat._data_model.models.dms._data_model import DataModelRequest
from cognite.neat._data_model.models.dms._references import ViewReference
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._data_model.models.entities._parser import parse_entities
from cognite.neat._exceptions import (
    CDFAPIException,
    DataModelCreateException,
    DataModelImportException,
    FileReadException,
)
from cognite.neat._issues import ConsistencyError, ModelSyntaxError
from cognite.neat._utils.http_client import FailedRequestMessage
from cognite.neat._utils.text import humanize_collection
from cognite.neat._utils.validation import ValidationContext, humanize_validation_error


class DMSAPIImporter(DMSImporter):
    """Imports DMS in the API format."""

    ENCODING = "utf-8"

    def __init__(self, schema: RequestSchema | dict[str, Any]) -> None:
        self._schema = schema

    def to_data_model(self) -> RequestSchema:
        if isinstance(self._schema, RequestSchema):
            return self._schema
        try:
            return RequestSchema.model_validate(self._schema)
        except ValidationError as e:
            context = ValidationContext()
            errors = [
                ModelSyntaxError(message=humanize_validation_error(error, context))
                for error in e.errors(include_input=True, include_url=False)
            ]
            raise DataModelImportException(errors) from None

    @classmethod
    def from_cdf(cls, data_model: DataModelReference, client: NeatClient) -> "DMSAPIImporter":
        """Create a DMSAPIImporter from a data model in CDF."""
        data_models = client.data_models.retrieve([data_model])
        if not data_models:
            available_data_models = [
                str(model.as_reference()) for model in client.data_models.list(limit=1000, include_global=True)
            ]
            close_matches = difflib.get_close_matches(str(data_model), available_data_models, n=1, cutoff=0.9)
            suggestion_msg = ""
            if close_matches:
                suggestion_msg = f" Did you mean: {close_matches[0]!r}?"
            raise CDFAPIException(
                messages=[
                    FailedRequestMessage(message=f"Data model '{data_model!s}' not found in CDF.{suggestion_msg}")
                ]
            )
        data_model = data_models[0]
        views = client.views.retrieve(data_model.views or [])
        if missing_views := set(data_model.views or []) - {view.as_reference() for view in views}:
            raise CDFAPIException(
                messages=[
                    FailedRequestMessage(
                        message=f"Views {humanize_collection(missing_views)} not found in CDF "
                        f"for data model {data_model}."
                    )
                ]
            )
        container_ids = list({container for view in views for container in view.mapped_containers})
        containers = client.containers.retrieve(container_ids)
        if missing_containers := set(container_ids) - {container.as_reference() for container in containers}:
            raise CDFAPIException(
                messages=[
                    FailedRequestMessage(
                        message=f"Containers {humanize_collection(missing_containers)} not found in CDF "
                        f"for data model {data_model}."
                    )
                ]
            )
        node_types = [nt for view in views for nt in view.node_types]
        space_ids = list(
            {data_model.space}
            | {view.space for view in views}
            | {container.space for container in containers}
            | {nt.space for nt in node_types}
        )
        spaces = client.spaces.retrieve([SpaceReference(space=space_id) for space_id in space_ids])
        if missing_spaces := set(space_ids) - {space.space for space in spaces}:
            raise CDFAPIException(
                messages=[
                    FailedRequestMessage(
                        message=f"Spaces {humanize_collection(missing_spaces)} not found in CDF "
                        f"for data model {data_model}."
                    )
                ]
            )
        return DMSAPIImporter(
            RequestSchema(
                dataModel=data_model.as_request(),
                views=[view.as_request() for view in views],
                containers=[container.as_request() for container in containers],
                nodeTypes=node_types,
                spaces=[space.as_request() for space in spaces],
            )
        )

    @classmethod
    def from_yaml(cls, yaml_file: Path) -> "DMSAPIImporter":
        """Create a DMSTableImporter from a YAML file."""
        source = cls._display_name(yaml_file)
        if yaml_file.suffix.lower() in {".yaml", ".yml", ".json"}:
            return cls(yaml.safe_load(yaml_file.read_text(encoding=cls.ENCODING)))
        elif yaml_file.is_dir():
            return cls(cls._read_yaml_files(yaml_file))
        raise FileReadException(source.as_posix(), f"Unsupported file type: {source.suffix}")

    @classmethod
    def from_json(cls, json_file: Path) -> "DMSAPIImporter":
        """Create a DMSTableImporter from a JSON file."""
        return cls.from_yaml(json_file)

    @classmethod
    def _display_name(cls, filepath: Path) -> Path:
        """Get a display-friendly version of the file path."""
        cwd = Path.cwd()
        source = filepath
        if filepath.is_relative_to(cwd):
            source = filepath.relative_to(cwd)
        return source

    @classmethod
    def _read_yaml_files(cls, directory: Path) -> dict[str, Any]:
        """Read all YAML files in a directory and combine them into a single dictionary."""
        schema_data: dict[str, Any] = {}
        data_model: dict[str, Any] | None = None
        for yaml_file in directory.rglob("**/*"):
            if yaml_file.suffix.lower() not in {".yaml", ".yml", ".json"}:
                continue
            stem = yaml_file.stem.casefold()
            if stem.endswith("datamodel") and data_model is not None:
                raise FileReadException(
                    cls._display_name(directory).as_posix(),
                    "Multiple data model files found in directory.",
                )
            data = yaml.safe_load(yaml_file.read_text(encoding=cls.ENCODING))
            list_data = data if isinstance(data, list) else [data]
            if stem.endswith("datamodel"):
                data_model = data
            elif stem.endswith("container"):
                schema_data.setdefault("containers", []).extend(list_data)
            elif stem.endswith("view"):
                schema_data.setdefault("views", []).extend(list_data)
            elif stem.endswith("space"):
                schema_data.setdefault("spaces", []).extend(list_data)
            elif stem.endswith("node"):
                schema_data.setdefault("nodeTypes", []).extend(list_data)
            # Ignore other files
        if data_model is None:
            raise FileReadException(
                cls._display_name(directory).as_posix(),
                "No data model file found in directory.",
            )
        schema_data["dataModel"] = data_model
        return schema_data


class DMSAPICreator(DMSImporter):
    """Creates data model from the existing schema components in CDF"""

    def __init__(
        self,
        cdf_snapshot: SchemaSnapshot,
        space: str,
        external_id: str,
        version: str,
        views: list[str],
        name: str | None = None,
        description: str | None = None,
        kind: Literal["solution"] = "solution",
    ) -> None:
        self._resources = ValidationResources("rebuild", local=cdf_snapshot, cdf=cdf_snapshot)
        self._space = space
        self._external_id = external_id
        self._version = version
        self._name = name
        self._description = description
        self._kind = kind
        self._views = views

    def to_data_model(self) -> RequestSchema:
        if self._kind == "solution":
            return self._to_solution_model()
        else:
            raise NotImplementedError(f"Data model kind '{self._kind}' is not supported yet.")

    def _to_solution_model(self) -> RequestSchema:
        """Creates solution data model from provided views"""

        errors, view_refs = self._parse_view_references(self._views)

        # Check if all views exist in the cdf snapshot:
        for view in view_refs:
            if not self._resources.select_view(view):
                errors.append(
                    ConsistencyError(
                        message=f"View '{view}' not found in the provided CDF snapshot. Cannot create data model."
                    )
                )

        if errors:
            raise DataModelCreateException(errors)

        # now we iterate over the views, expand them and add them to the data model
        expanded_views: list[ViewRequest] = []

        for view in view_refs:
            expanded_view = self._resources.expand_view_properties(view)
            if not expanded_view:
                raise RuntimeError(f"Failed to expand view '{view}' despite earlier checks. This is a bug.")

            # remove implements after expansion
            expanded_view.implements = None

            # set space and version to data model values
            expanded_view.space = self._space
            expanded_view.version = self._version

            expanded_views.append(expanded_view)

        data_model = DataModelRequest(
            space=self._space,
            externalId=self._external_id,
            version=self._version,
            name=self._name,
            description=self._description,
            views=[view.as_reference() for view in expanded_views],
        )

        return RequestSchema(dataModel=data_model, views=expanded_views)

    @classmethod
    def _parse_view_references(
        cls, views: list[str]
    ) -> tuple[list[ModelSyntaxError | ConsistencyError], list[ViewReference]]:
        """Parses list of view strings in to list of view references

        Args:
            views : list of view references in a short string format

        Returns:
            Tuple of errors and view references
        """
        view_references: list[ViewReference] = []
        errors: list[ModelSyntaxError | ConsistencyError] = []

        for view in views:
            try:
                entity = parse_entities(view)
                if not entity:
                    errors.append(ModelSyntaxError(message=f"Invalid view reference '{view}': Could not parse entity."))
                    continue

                if len(entity) != 1:
                    errors.append(
                        ModelSyntaxError(message=f"Invalid view reference '{view}': Expected a single entity.")
                    )
                    continue

                if "version" not in entity[0].properties:
                    errors.append(
                        ModelSyntaxError(message=f"Invalid view reference '{view}': Missing 'version' property.")
                    )
                    continue

                try:
                    view_ref = ViewReference(
                        space=entity[0].prefix,
                        external_id=entity[0].suffix,
                        version=str(entity[0].properties["version"]),
                    )
                    view_references.append(view_ref)
                except ValidationError:
                    errors.append(ModelSyntaxError(message=f"Invalid view reference '{view}', cannot parse it!"))

            except ValueError:
                errors.append(ModelSyntaxError(message=f"Invalid view reference '{view}', cannot parse it!"))

        if errors:
            raise DataModelCreateException(errors)

        return errors, view_references
