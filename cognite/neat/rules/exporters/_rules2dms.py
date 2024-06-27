import warnings
from collections.abc import Collection, Hashable, Iterable, Sequence
from pathlib import Path
from typing import Literal, TypeAlias, cast

from cognite.client import CogniteClient
from cognite.client.data_classes._base import CogniteResource, CogniteResourceList
from cognite.client.data_classes.data_modeling import (
    ContainerApplyList,
    DataModelApply,
    DataModelApplyList,
    DataModelId,
    SpaceApplyList,
    ViewApplyList,
)
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
from cognite.neat.utils.upload import UploadResult

from ._base import CDFExporter

Component: TypeAlias = Literal["all", "spaces", "data_models", "views", "containers", "node_types"]


class DMSExporter(CDFExporter[DMSSchema]):
    """Export rules to Cognite Data Fusion's Data Model Storage (DMS) service.

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
        return dms_rules.as_schema(include_pipeline=self.export_pipeline, instance_space=self.instance_space)

    def delete_from_cdf(self, rules: Rules, client: CogniteClient, dry_run: bool = False) -> Iterable[UploadResult]:
        to_export = self._prepare_exporters(rules, client)

        # we need to reverse order in which we are picking up the items to delete
        # as they are sorted in the order of creation and we need to delete them in reverse order
        for items, loader in reversed(to_export):
            item_ids = loader.get_ids(items)
            existing_items = loader.retrieve(item_ids)
            existing_ids = loader.get_ids(existing_items)
            to_delete: list[Hashable] = []
            for item_id in item_ids:
                if (
                    isinstance(loader, DataModelingLoader)
                    and self.include_space is not None
                    and not loader.in_space(item_id, self.include_space)
                ):
                    continue

                if item_id in existing_ids:
                    to_delete.append(item_id)

            deleted: set[Hashable] = set()
            failed_deleted: set[Hashable] = set()
            error_messages: list[str] = []
            if dry_run:
                deleted.update(to_delete)
            elif to_delete:
                try:
                    loader.delete(to_delete)
                except CogniteAPIError as e:
                    failed_deleted.update(loader.get_id(item) for item in e.failed + e.unknown)
                    deleted.update(loader.get_id(item) for item in e.successful)
                    error_messages.append(f"Failed delete: {e.message}")
                else:
                    deleted.update(to_delete)

            yield UploadResult(
                name=loader.resource_name,
                deleted=deleted,
                failed_deleted=failed_deleted,
                error_messages=error_messages,
            )

    def export_to_cdf_iterable(
        self, rules: Rules, client: CogniteClient, dry_run: bool = False
    ) -> Iterable[UploadResult]:
        to_export = self._prepare_exporters(rules, client)

        redeploy_data_model = False
        for items, loader in to_export:
            # The conversion from DMS to GraphQL does not seem to be triggered even if the views
            # are changed. This is a workaround to force the conversion.
            is_redeploying = loader is DataModelingLoader and redeploy_data_model

            to_create, to_delete, to_update, unchanged = self._categorize_items_for_upload(
                loader, items, is_redeploying
            )

            issue_list = IssueList()
            warning_list = self._validate(loader, items)
            issue_list.extend(warning_list)

            created: set[Hashable] = set()
            skipped: set[Hashable] = set()
            changed: set[Hashable] = set()
            failed_created: set[Hashable] = set()
            failed_changed: set[Hashable] = set()
            error_messages: list[str] = []
            if dry_run:
                if self.existing_handling in ["update", "force"]:
                    changed.update(loader.get_id(item) for item in to_update)
                elif self.existing_handling == "skip":
                    skipped.update(loader.get_id(item) for item in to_update)
                elif self.existing_handling == "fail":
                    failed_changed.update(loader.get_id(item) for item in to_update)
                else:
                    raise ValueError(f"Unsupported existing_handling {self.existing_handling}")
            else:
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
                    failed_created.update(loader.get_id(item) for item in e.failed + e.unknown)
                    created.update(loader.get_id(item) for item in e.successful)
                    error_messages.append(e.message)
                else:
                    created.update(loader.get_id(item) for item in to_create)

                if self.existing_handling in ["update", "force"]:
                    try:
                        loader.update(to_update)
                    except CogniteAPIError as e:
                        failed_changed.update(loader.get_id(item) for item in e.failed + e.unknown)
                        changed.update(loader.get_id(item) for item in e.successful)
                        error_messages.append(e.message)
                    else:
                        changed.update(loader.get_id(item) for item in to_update)
                elif self.existing_handling == "skip":
                    skipped.update(loader.get_id(item) for item in to_update)
                elif self.existing_handling == "fail":
                    failed_changed.update(loader.get_id(item) for item in to_update)

            yield UploadResult(
                name=loader.resource_name,
                created=created,
                changed=changed,
                unchanged={loader.get_id(item) for item in unchanged},
                skipped=skipped,
                failed_created=failed_created,
                failed_changed=failed_changed,
                error_messages=error_messages,
                issues=issue_list,
            )

            if loader is ViewLoader and (created or changed):
                redeploy_data_model = True

    def _categorize_items_for_upload(
        self, loader: ResourceLoader, items: Sequence[CogniteResource], is_redeploying
    ) -> tuple[list[CogniteResource], list[CogniteResource], list[CogniteResource], list[CogniteResource]]:
        item_ids = loader.get_ids(items)
        cdf_items = loader.retrieve(item_ids)
        cdf_item_by_id = {loader.get_id(item): item for item in cdf_items}
        to_create, to_update, unchanged, to_delete = [], [], [], []
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
        return to_create, to_delete, to_update, unchanged

    def _prepare_exporters(self, rules, client) -> list[tuple[CogniteResourceList, ResourceLoader]]:
        schema = self.export(rules)
        to_export: list[tuple[CogniteResourceList, ResourceLoader]] = []
        if self.export_components.intersection({"all", "spaces"}):
            to_export.append((SpaceApplyList(schema.spaces.values()), SpaceLoader(client)))
        if self.export_components.intersection({"all", "containers"}):
            to_export.append((ContainerApplyList(schema.containers.values()), ContainerLoader(client)))
        if self.export_components.intersection({"all", "views"}):
            to_export.append((ViewApplyList(schema.views.values()), ViewLoader(client, self.existing_handling)))
        if self.export_components.intersection({"all", "data_models"}):
            to_export.append((DataModelApplyList([schema.data_model]), DataModelLoader(client)))
        if isinstance(schema, PipelineSchema):
            to_export.append((schema.databases, RawDatabaseLoader(client)))
            to_export.append((schema.raw_tables, RawTableLoader(client)))
            to_export.append((schema.transformations, TransformationLoader(client)))
        return to_export

    def _validate(self, loader: ResourceLoader, items: CogniteResourceList) -> IssueList:
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
