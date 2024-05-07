import warnings
from collections.abc import Collection, Iterable
from pathlib import Path
from typing import Literal, TypeAlias, cast

from cognite.client import CogniteClient
from cognite.client.data_classes._base import CogniteResource, CogniteResourceList
from cognite.client.data_classes.data_modeling import DataModelApply, DataModelId
from cognite.client.exceptions import CogniteAPIError

from cognite.neat.rules import issues
from cognite.neat.rules._shared import Rules
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models import InformationRules
from cognite.neat.rules.models.dms import DMSRules, DMSSchema, PipelineSchema
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

Component: TypeAlias = Literal["all", "spaces", "data_models", "views", "containers", "node_types"]


class DMSExporter(CDFExporter[DMSSchema]):
    """Class for exporting rules object to CDF Data Model Storage (DMS).

    Args:
        export_components (frozenset[Literal["all", "spaces", "data_models", "views", "containers"]], optional):
            Which components to export. Defaults to frozenset({"all"}).
        include_space (set[str], optional):
            If set, only export components in the given spaces. Defaults to None which means all spaces.
        existing_handling (Literal["fail", "skip", "update", "force"], optional): How to handle existing components.
            Defaults to "update". See below for details.
        export_pipeline (bool, optional): Whether to export the pipeline. Defaults to False. This means setting
            up transformations, RAW databases and tables to populate the data model.
        instance_space (str, optional): The space to use for the instance. Defaults to None.
        suppress_warnings (bool, optional): Suppress warnings. Defaults to False.

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
        export_pipeline: bool = False,
        instance_space: str | None = None,
        suppress_warnings: bool = False,
    ):
        self.export_components = {export_components} if isinstance(export_components, str) else set(export_components)
        self.include_space = include_space
        self.existing_handling = existing_handling
        self.export_pipeline = export_pipeline
        self.instance_space = instance_space
        self.suppress_warnings = suppress_warnings
        self._schema: DMSSchema | None = None

    def export_to_file(self, rules: Rules, filepath: Path) -> None:
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
        exclude = self._create_exclude_set()
        schema.to_directory(directory, exclude=exclude, new_line=self._new_line, encoding=self._encoding)

    def _export_to_zip_file(self, filepath: Path, rules: Rules) -> None:
        if filepath.suffix not in {".zip"}:
            warnings.warn("File extension is not .zip, adding it to the file name", stacklevel=2)
            filepath = filepath.with_suffix(".zip")
        schema = self.export(rules)
        exclude = self._create_exclude_set()
        schema.to_zip(filepath, exclude=exclude)

    def _create_exclude_set(self):
        if "all" in self.export_components:
            exclude = set()
        else:
            exclude = {"spaces", "data_models", "views", "containers", "node_types"} - self.export_components
        return exclude

    def export(self, rules: Rules) -> DMSSchema:
        if isinstance(rules, DMSRules):
            dms_rules = rules
        elif isinstance(rules, InformationRules):
            dms_rules = rules.as_dms_architect_rules()
        else:
            raise ValueError(f"{type(rules).__name__} cannot be exported to DMS")
        return dms_rules.as_schema(
            include_ref=True, include_pipeline=self.export_pipeline, instance_space=self.instance_space
        )

    def delete_from_cdf(self, rules: Rules, client: CogniteClient, dry_run: bool = False) -> Iterable[UploadResult]:
        schema, to_export = self._prepare_schema_and_exporters(rules, client)

        # we need to reverse order in which we are picking up the items to delete
        # as they are sorted in the order of creation and we need to delete them in reverse order
        for all_items, loader in reversed(to_export):
            all_item_ids = loader.get_ids(all_items)
            item_ids = [item_id for item_id in all_item_ids]
            cdf_items = loader.retrieve(item_ids)
            cdf_item_by_id = {loader.get_id(item): item for item in cdf_items}
            items = [item for item in all_items if loader.get_id(item) in item_ids]
            to_delete = []

            for item in items:
                if (
                    isinstance(loader, DataModelingLoader)
                    and self.include_space is not None
                    and not loader.in_space(item, self.include_space)
                ):
                    continue

                cdf_item = cdf_item_by_id.get(loader.get_id(item))
                if cdf_item:
                    to_delete.append(cdf_item)

            deleted = len(to_delete)
            failed_deleted = 0

            error_messages: list[str] = []
            if not dry_run:
                if to_delete:
                    try:
                        loader.delete(to_delete)
                    except CogniteAPIError as e:
                        failed_deleted = len(e.failed) + len(e.unknown)
                        deleted -= failed_deleted
                        error_messages.append(f"Failed delete: {e.message}")

            yield UploadResult(
                name=loader.resource_name,
                deleted=deleted,
                skipped=0,
                failed_deleted=failed_deleted,
                error_messages=error_messages,
            )

    def export_to_cdf(self, rules: Rules, client: CogniteClient, dry_run: bool = False) -> Iterable[UploadResult]:
        schema, to_export = self._prepare_schema_and_exporters(rules, client)

        # The conversion from DMS to GraphQL does not seem to be triggered even if the views
        # are changed. This is a workaround to force the conversion.
        redeploy_data_model = False

        for all_items, loader in to_export:
            issue_list = IssueList()
            all_item_ids = loader.get_ids(all_items)
            item_ids = [item_id for item_id in all_item_ids]
            cdf_items = loader.retrieve(item_ids)
            cdf_item_by_id = {loader.get_id(item): item for item in cdf_items}
            items = [item for item in all_items if loader.get_id(item) in item_ids]
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

            warning_list = self._validate(loader, items)
            issue_list.extend(warning_list)

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
                issues=issue_list,
            )

            if loader.resource_name == "views" and (created or changed) and not redeploy_data_model:
                redeploy_data_model = True

    def _prepare_schema_and_exporters(
        self, rules, client
    ) -> tuple[DMSSchema, list[tuple[CogniteResourceList, ResourceLoader]]]:
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
        return schema, to_export

    def _validate(self, loader: ResourceLoader, items: list[CogniteResource]) -> IssueList:
        issue_list = IssueList()
        if isinstance(loader, DataModelLoader):
            models = cast(list[DataModelApply], items)
            if other_models := self._exist_other_data_models(loader, models):
                warning = issues.dms.OtherDataModelsInSpaceWarning(models[0].space, other_models)
                if not self.suppress_warnings:
                    warnings.warn(warning, stacklevel=2)
                issue_list.append(warning)

        return issue_list

    @classmethod
    def _exist_other_data_models(cls, loader: DataModelLoader, models: list[DataModelApply]) -> list[DataModelId]:
        if not models:
            return []
        space = models[0].space
        external_id = models[0].external_id
        try:
            data_models = loader.client.data_modeling.data_models.list(space=space, limit=25, all_versions=False)
        except CogniteAPIError as e:
            warnings.warn(issues.importing.APIWarning(str(e)), stacklevel=2)
            return []
        else:
            return [
                data_model.as_id()
                for data_model in data_models
                if (data_model.space, data_model.external_id) != (space, external_id)
            ]
