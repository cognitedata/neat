import warnings
from collections.abc import Collection, Hashable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, Literal, cast

from cognite.client.data_classes._base import (
    CogniteResourceList,
    T_CogniteResourceList,
    T_WritableCogniteResource,
    T_WriteClass,
)
from cognite.client.data_classes.data_modeling import (
    DataModelApply,
    DataModelApplyList,
    DataModelId,
    SpaceApplyList,
    ViewApplyList,
)
from cognite.client.exceptions import CogniteAPIError

from cognite.neat._client import DataModelingLoader, NeatClient
from cognite.neat._client.data_classes.data_modeling import Component
from cognite.neat._client.data_classes.schema import DMSSchema
from cognite.neat._issues import IssueList
from cognite.neat._issues.warnings import (
    PrincipleOneModelOneSpaceWarning,
    ResourceRetrievalWarning,
)
from cognite.neat._rules.models.dms import DMSRules
from cognite.neat._shared import T_ID
from cognite.neat._utils.upload import UploadResult

from ..._client._api.data_modeling_loaders import T_WritableCogniteResourceList
from ._base import CDFExporter


@dataclass
class ItemCategorized(Generic[T_ID, T_WriteClass]):
    to_create: list[T_WriteClass] = field(default_factory=list)
    to_update: list[T_WriteClass] = field(default_factory=list)
    to_delete: list[T_ID] = field(default_factory=list)
    unchanged: list[T_WriteClass] = field(default_factory=list)


class DMSExporter(CDFExporter[DMSRules, DMSSchema]):
    """Export rules to Cognite Data Fusion's Data Model Storage (DMS) service.

    Args:
        export_components (frozenset[Literal["all", "spaces", "data_models", "views", "containers"]], optional):
            Which components to export. Defaults to frozenset({"all"}).
        include_space (set[str], optional):
            If set, only export components in the given spaces. Defaults to None which means all spaces.
        existing (Literal["fail", "skip", "update", "force"], optional): How to handle existing components.
            Defaults to "update". See below for details.
        instance_space (str, optional): The space to use for the instance. Defaults to None.
        suppress_warnings (bool, optional): Suppress warnings. Defaults to False.
        remove_cdf_spaces (bool, optional): Skip views and containers that are system are in system spaces.

    ... note::

        - "fail": If any component already exists, the export will fail.
        - "skip": If any component already exists, it will be skipped.
        - "update": If any component already exists, it will
        - "force": If any component already exists, it will be deleted and recreated.

    """

    def __init__(
        self,
        export_components: Component | Collection[Component] | None = None,
        include_space: set[str] | None = None,
        existing: Literal["fail", "skip", "update", "force", "recreate"] = "update",
        instance_space: str | None = None,
        suppress_warnings: bool = False,
        drop_data: bool = False,
        remove_cdf_spaces: bool = True,
    ):
        self.export_components = export_components
        self.include_space = include_space
        self.existing = existing
        self.drop_data = drop_data
        self.instance_space = instance_space
        self.suppress_warnings = suppress_warnings
        self._schema: DMSSchema | None = None
        self.remove_cdf_spaces = remove_cdf_spaces

    def export_to_file(self, rules: DMSRules, filepath: Path) -> None:
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

    def _export_to_directory(self, directory: Path, rules: DMSRules) -> None:
        schema = self.export(rules)
        exclude = self._create_exclude_set()
        schema.to_directory(directory, exclude=exclude, new_line=self._new_line, encoding=self._encoding)

    def _export_to_zip_file(self, filepath: Path, rules: DMSRules) -> None:
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

    def export(self, rules: DMSRules) -> DMSSchema:
        # We do not want to include CogniteCore/CogniteProcess Inudstries in the schema
        return rules.as_schema(instance_space=self.instance_space, remove_cdf_spaces=self.remove_cdf_spaces)

    def delete_from_cdf(
        self, rules: DMSRules, client: NeatClient, dry_run: bool = False, skip_space: bool = False
    ) -> Iterable[UploadResult]:
        to_export = self._prepare_exporters(rules)

        # we need to reverse order in which we are picking up the items to delete
        # as they are sorted in the order of creation and we need to delete them in reverse order
        for items in reversed(to_export):
            loader = client.loaders.get_loader(items)
            if skip_space and isinstance(items, SpaceApplyList):
                continue
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
        self, rules: DMSRules, client: NeatClient, dry_run: bool = False
    ) -> Iterable[UploadResult]:
        schema = self.export(rules)

        categorized_items_by_loader: dict[
            DataModelingLoader[
                T_ID, T_WriteClass, T_WritableCogniteResource, T_CogniteResourceList, T_WritableCogniteResourceList
            ],
            ItemCategorized[T_ID, T_WriteClass],
        ] = {}
        redeploy_data_model = False
        for loader in client.loaders.by_dependency_order(self.export_components):
            items = loader.items_from_schema(schema)
            # The conversion from DMS to GraphQL does not seem to be triggered even if the views
            # are changed. This is a workaround to force the conversion.
            is_redeploying = isinstance(items, DataModelApplyList) and redeploy_data_model

            categorized = self._categorize_items_for_upload(loader, items, is_redeploying)
            categorized_items_by_loader[loader] = categorized

            if isinstance(items, ViewApplyList) and (categorized.to_create or categorized.to_update):
                redeploy_data_model = True

        for loader, items in categorized_items_by_loader.items():
            result_by_name: dict[str, UploadResult] = {}

            issue_list = IssueList()
            warning_list = self._validate(items, client)
            issue_list.extend(warning_list)

            created: set[Hashable] = set()
            skipped: set[Hashable] = set()
            changed: set[Hashable] = set()
            deleted: set[Hashable] = set()
            failed_created: set[Hashable] = set()
            failed_changed: set[Hashable] = set()
            failed_deleted: set[Hashable] = set()
            error_messages: list[str] = []
            if dry_run:
                if self.existing in ["update", "force"]:
                    changed.update(loader.get_id(item) for item in to_update)
                elif self.existing == "skip":
                    skipped.update(loader.get_id(item) for item in to_update)
                elif self.existing == "fail":
                    failed_changed.update(loader.get_id(item) for item in to_update)
                else:
                    raise ValueError(f"Unsupported existing_handling {self.existing}")
                created.update(loader.get_id(item) for item in to_create)
                deleted.update(loader.get_id(item) for item in to_delete)
            else:
                if to_delete:
                    try:
                        loader.delete(to_delete)
                    except CogniteAPIError as e:
                        if True:
                            for item in to_delete:
                                try:
                                    loader.delete([item])
                                except CogniteAPIError as item_e:
                                    failed_deleted.add(loader.get_id(item))
                                    error_messages.append(f"Failed delete: {item_e!s}")
                                else:
                                    deleted.add(loader.get_id(item))
                        else:
                            error_messages.append(f"Failed delete: {e!s}")
                            failed_deleted.update(loader.get_id(item) for item in e.failed + e.unknown)
                    else:
                        deleted.update(loader.get_id(item) for item in to_delete)

                if isinstance(items, DataModelApplyList):
                    to_create = loader.sort_by_dependencies(to_create)

                try:
                    loader.create(to_create)
                except CogniteAPIError as e:
                    if True:
                        for item in to_create:
                            try:
                                loader.create([item])
                            except CogniteAPIError as item_e:
                                failed_created.add(loader.get_id(item))
                                error_messages.append(f"Failed create: {item_e!s}")
                            else:
                                created.add(loader.get_id(item))
                    else:
                        failed_created.update(loader.get_id(item) for item in e.failed + e.unknown)
                        created.update(loader.get_id(item) for item in e.successful)
                        error_messages.append(f"Failed create: {e!s}")
                else:
                    created.update(loader.get_id(item) for item in to_create)

                if self.existing in ["update", "force"]:
                    try:
                        loader.update(to_update)
                    except CogniteAPIError as e:
                        if True:
                            for item in to_update:
                                try:
                                    loader.update([item])
                                except CogniteAPIError as e_item:
                                    failed_changed.add(loader.get_id(item))
                                    error_messages.append(f"Failed update: {e_item!s}")
                                else:
                                    changed.add(loader.get_id(item))
                        else:
                            failed_changed.update(loader.get_id(item) for item in e.failed + e.unknown)
                            changed.update(loader.get_id(item) for item in e.successful)
                            error_messages.append(f"Failed update: {e!s}")
                    else:
                        changed.update(loader.get_id(item) for item in to_update)
                elif self.existing == "skip":
                    skipped.update(loader.get_id(item) for item in to_update)
                elif self.existing == "fail":
                    failed_changed.update(loader.get_id(item) for item in to_update)

            if loader.resource_name in result_by_name:
                delete_result = result_by_name[loader.resource_name]
                deleted.update(delete_result.deleted)
                failed_deleted.update(delete_result.failed_deleted)
                error_messages.extend(delete_result.error_messages)

            yield UploadResult(
                name=loader.resource_name,
                created=created,
                changed=changed,
                deleted=deleted,
                unchanged={loader.get_id(item) for item in unchanged},
                skipped=skipped,
                failed_created=failed_created,
                failed_changed=failed_changed,
                failed_deleted=failed_deleted,
                error_messages=error_messages,
                issues=issue_list,
            )

    def _categorize_items_for_upload(
        self,
        loader: DataModelingLoader[
            T_ID, T_WriteClass, T_WritableCogniteResource, T_CogniteResourceList, T_WritableCogniteResourceList
        ],
        items: T_CogniteResourceList,
        is_redeploying: bool,
    ) -> ItemCategorized[T_ID, T_WriteClass]:
        item_ids = loader.get_ids(items)
        cdf_items = loader.retrieve(item_ids)
        cdf_item_by_id = {loader.get_id(item): item for item in cdf_items}
        categorized = ItemCategorized()
        for item in items:
            if (
                isinstance(items, DataModelApplyList)
                and self.include_space is not None
                and not loader.in_space(item, self.include_space)
            ):
                continue

            cdf_item = cdf_item_by_id.get(loader.get_id(item))
            if cdf_item is None:
                categorized.to_create.append(item)
            elif is_redeploying or self.existing == "recreate":
                categorized.to_delete.append(loader.get_id(cdf_item))
                categorized.to_create.append(item)
            elif loader.are_equal(item, cdf_item):
                categorized.unchanged.append(item)
            else:
                categorized.to_update.append(item)
        return categorized

    def _validate(self, items: CogniteResourceList, client: NeatClient) -> IssueList:
        issue_list = IssueList()
        if isinstance(items, DataModelApplyList):
            models = cast(list[DataModelApply], items)
            if other_models := self._exist_other_data_models(client, models):
                warning = PrincipleOneModelOneSpaceWarning(
                    f"There are multiple data models in the same space {models[0].space}. "
                    f"Other data models in the space are {other_models}.",
                )
                if not self.suppress_warnings:
                    warnings.warn(warning, stacklevel=2)
                issue_list.append(warning)

        return issue_list

    @classmethod
    def _exist_other_data_models(cls, client: NeatClient, models: list[DataModelApply]) -> list[DataModelId]:
        if not models:
            return []
        space = models[0].space
        external_id = models[0].external_id
        try:
            data_models = client.data_modeling.data_models.list(space=space, limit=25, all_versions=False)
        except CogniteAPIError as e:
            warnings.warn(ResourceRetrievalWarning(frozenset({space}), "space", str(e)), stacklevel=2)
            return []
        else:
            return [
                data_model.as_id()
                for data_model in data_models
                if (data_model.space, data_model.external_id) != (space, external_id)
            ]
