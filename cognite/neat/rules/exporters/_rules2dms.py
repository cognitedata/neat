import warnings
import zipfile
from collections.abc import Collection, Iterable
from pathlib import Path
from typing import Literal, TypeAlias

from cognite.client import CogniteClient
from cognite.client.data_classes._base import CogniteResourceList
from cognite.client.exceptions import CogniteAPIError

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models._rules import InformationRules
from cognite.neat.rules.models._rules.dms_architect_rules import DMSRules
from cognite.neat.rules.models._rules.dms_schema import DMSSchema, PipelineSchema
from cognite.neat.utils.cdf_loaders import (
    ContainerLoader,
    DataModelingLoader,
    DataModelLoader,
    RawDatabaseLoader,
    RawTableLoader,
    ResourceLoader,
    SpaceLoader,
    TransformationLoader,
    ViewLoader,
)

from ._base import CDFExporter
from ._models import UploadResult

Component: TypeAlias = Literal["all", "spaces", "data_models", "views", "containers"]


class DMSExporter(CDFExporter[DMSSchema]):
    """Class for exporting rules object to CDF Data Model Storage (DMS).

    Args:
        export_components (frozenset[Literal["all", "spaces", "data_models", "views", "containers"]], optional):
            Which components to export. Defaults to frozenset({"all"}).
        include_space (set[str], optional):
            If set, only export components in the given spaces. Defaults to None which means all spaces.
        existing_handling (Literal["fail", "skip", "update", "force"], optional): How to handle existing components.
            Defaults to "update". See below for details.
        standardize_casing(bool, optional): Whether to standardize the casing. This means PascalCase for external ID
            of views, containers, and data models, and camelCase for properties.
        export_pipeline (bool, optional): Whether to export the pipeline. Defaults to False. This means setting
            up transformations, RAW databases and tables to populate the data model.
        instance_space (str, optional): The space to use for the instance. Defaults to None.
    ... note::

        - "fail": If any component already exists, the export will fail.
        - "skip": If any component already exists, it will be skipped.
        - "update": If any component already exists, it will be updated.
        - "force": If any component already exists, it will be deleted and recreated.

    """

    def __init__(
        self,
        export_components: Component | Collection[Component] = "all",
        include_space: set[str] | None = None,
        existing_handling: Literal["fail", "skip", "update", "force"] = "update",
        standardize_casing: bool = True,
        export_pipeline: bool = False,
        instance_space: str | None = None,
    ):
        self.export_components = {export_components} if isinstance(export_components, str) else set(export_components)
        self.include_space = include_space
        self.existing_handling = existing_handling
        self.standardize_casing = standardize_casing
        self.export_pipeline = export_pipeline
        self.instance_space = instance_space
        self._schema: DMSSchema | None = None

    def export_to_file(self, filepath: Path, rules: Rules) -> None:
        """Export the rules to a file(s).

        If the file is a directory, the components will be exported to separate files, otherwise they will be
        exported to a zip file.

        Args:
            filepath: Directory or zip file path to export to.
            rules:
        """
        if filepath.is_dir():
            self._export_to_directory(filepath, rules)
        else:
            self._export_to_zip_file(filepath, rules)

    def _export_to_directory(self, directory: Path, rules: Rules) -> None:
        schema = self.export(rules)
        data_models = directory / "data_models"
        data_models.mkdir(exist_ok=True, parents=True)
        if self.export_components.intersection({"all", "spaces"}):
            for space in schema.spaces:
                (data_models / f"{space.space}.space.yaml").write_text(space.dump_yaml())
        if self.export_components.intersection({"all", "data_models"}):
            for model in schema.data_models:
                (data_models / f"{model.external_id}.datamodel.yaml").write_text(model.dump_yaml())
        if self.export_components.intersection({"all", "views"}):
            for view in schema.views:
                (data_models / f"{view.external_id}.view.yaml").write_text(view.dump_yaml())
        if self.export_components.intersection({"all", "containers"}):
            for container in schema.containers:
                (data_models / f"{container.external_id}.container.yaml").write_text(container.dump_yaml())
        if isinstance(schema, PipelineSchema):
            transformations = directory / "transformations"
            transformations.mkdir(exist_ok=True, parents=True)
            for transformation in schema.transformations:
                (transformations / f"{transformation.external_id}.yaml").write_text(transformation.dump_yaml())
            # The RAW Databases are not written to file. This is because cognite-toolkit expects the RAW databases
            # to be in the same file as the RAW tables.
            raw = directory / "raw"
            raw.mkdir(exist_ok=True, parents=True)
            for raw_table in schema.raw_tables:
                (raw / f"{raw_table.name}.yaml").write_text(raw_table.dump_yaml())

    def _export_to_zip_file(self, filepath: Path, rules: Rules) -> None:
        if filepath.suffix not in {".zip"}:
            warnings.warn("File extension is not .zip, adding it to the file name", stacklevel=2)
            filepath = filepath.with_suffix(".zip")
        schema = self.export(rules)
        with zipfile.ZipFile(filepath, "w") as zip_ref:
            if self.export_components.intersection({"all", "spaces"}):
                for space in schema.spaces:
                    zip_ref.writestr(f"data_models/{space.space}.space.yaml", space.dump_yaml())
            if self.export_components.intersection({"all", "data_models"}):
                for model in schema.data_models:
                    zip_ref.writestr(f"data_models/{model.external_id}.datamodel.yaml", model.dump_yaml())
            if self.export_components.intersection({"all", "views"}):
                for view in schema.views:
                    zip_ref.writestr(f"data_models/{view.external_id}.view.yaml", view.dump_yaml())
            if self.export_components.intersection({"all", "containers"}):
                for container in schema.containers:
                    zip_ref.writestr(f"data_models/{container.external_id}.container.yaml", container.dump_yaml())
            if isinstance(schema, PipelineSchema):
                for transformation in schema.transformations:
                    zip_ref.writestr(f"transformations/{transformation.external_id}.yaml", transformation.dump_yaml())
                # The RAW Databases are not written to file. This is because cognite-toolkit expects the RAW databases
                # to be in the same file as the RAW tables.
                for raw_table in schema.raw_tables:
                    zip_ref.writestr(f"raw/{raw_table.name}.yaml", raw_table.dump_yaml())

    def export(self, rules: Rules) -> DMSSchema:
        if isinstance(rules, DMSRules):
            return rules.as_schema(self.standardize_casing, self.export_pipeline, self.instance_space)
        elif isinstance(rules, InformationRules):
            return rules.as_dms_architect_rules().as_schema(
                self.standardize_casing, self.export_pipeline, self.instance_space
            )
        else:
            raise ValueError(f"{type(rules).__name__} cannot be exported to DMS")

    def export_to_cdf(self, client: CogniteClient, rules: Rules, dry_run: bool = False) -> Iterable[UploadResult]:
        schema = self.export(rules)
        to_export: list[tuple[CogniteResourceList, ResourceLoader]] = []
        if self.export_components.intersection({"all", "spaces"}):
            to_export.append((schema.spaces, SpaceLoader(client)))
        if self.export_components.intersection({"all", "containers"}):
            to_export.append((schema.containers, ContainerLoader(client)))
        if self.export_components.intersection({"all", "views"}):
            to_export.append((schema.views, ViewLoader(client, self.existing_handling)))
        if self.export_components.intersection({"all", "data_models"}):
            to_export.append((schema.data_models, DataModelLoader(client)))
        if isinstance(schema, PipelineSchema):
            to_export.append((schema.databases, RawDatabaseLoader(client)))
            to_export.append((schema.raw_tables, RawTableLoader(client)))
            to_export.append((schema.transformations, TransformationLoader(client)))

        # The conversion from DMS to GraphQL does not seem to be triggered even if the views
        # are changed. This is a workaround to force the conversion.
        redeploy_data_model = False

        for items, loader in to_export:
            item_ids = loader.get_ids(items)
            cdf_items = loader.retrieve(item_ids)
            cdf_item_by_id = {loader.get_id(item): item for item in cdf_items}
            to_create, to_update, unchanged, to_delete = [], [], [], []
            is_redeploying = loader.resource_name == "data_models" and redeploy_data_model
            for item in items:
                if (
                    isinstance(loader, DataModelingLoader)
                    and self.include_space is not None
                    and not loader.in_space(item, self.include_space)
                ):
                    continue

                cdf_item = cdf_item_by_id.get(loader.get_id(item))
                if cdf_item is None:
                    to_create.append(item)
                elif is_redeploying:
                    to_update.append(item)
                    to_delete.append(cdf_item)
                elif loader.are_equal(item, cdf_item):
                    unchanged.append(item)
                else:
                    to_update.append(item)

            created = len(to_create)
            failed_created = 0

            skipped = 0
            if self.existing_handling in ["update", "force"]:
                changed = len(to_update)
                failed_changed = 0
            elif self.existing_handling == "skip":
                changed = 0
                failed_changed = 0
                skipped += len(to_update)
            elif self.existing_handling == "fail":
                failed_changed = len(to_update)
                changed = 0
            else:
                raise ValueError(f"Unsupported existing_handling {self.existing_handling}")

            error_messages: list[str] = []
            if not dry_run:
                if to_delete:
                    try:
                        loader.delete(to_delete)
                    except CogniteAPIError as e:
                        error_messages.append(f"Failed delete: {e.message}")

                if isinstance(loader, DataModelingLoader):
                    to_create = loader.sort_by_dependencies(to_create)

                try:
                    loader.create(to_create)
                except CogniteAPIError as e:
                    failed_created = len(e.failed) + len(e.unknown)
                    created -= failed_created
                    error_messages.append(e.message)

                if self.existing_handling in ["update", "force"]:
                    try:
                        loader.update(to_update)
                    except CogniteAPIError as e:
                        failed_changed = len(e.failed) + len(e.unknown)
                        changed -= failed_changed
                        error_messages.append(e.message)

            yield UploadResult(
                name=loader.resource_name,
                created=created,
                changed=changed,
                unchanged=len(unchanged),
                skipped=skipped,
                failed_created=failed_created,
                failed_changed=failed_changed,
                error_messages=error_messages,
            )

            if loader.resource_name == "views" and (created or changed) and not redeploy_data_model:
                redeploy_data_model = True
