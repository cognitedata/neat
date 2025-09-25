import warnings
from collections.abc import Callable, Collection, Hashable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, Literal

from cognite.client import data_modeling as dm
from cognite.client.data_classes._base import (
    T_CogniteResourceList,
    T_WritableCogniteResource,
    T_WriteClass,
)
from cognite.client.data_classes.data_modeling import (
    DataModelApplyList,
    DataModelId,
    SpaceApply,
    ViewApplyList,
)
from cognite.client.exceptions import CogniteAPIError

from cognite.neat.v0.core._client import DataModelingLoader, NeatClient
from cognite.neat.v0.core._client._api.data_modeling_loaders import (
    MultiCogniteAPIError,
    T_WritableCogniteResourceList,
)
from cognite.neat.v0.core._client.data_classes.data_modeling import (
    Component,
    ViewApplyDict,
)
from cognite.neat.v0.core._client.data_classes.schema import DMSSchema
from cognite.neat.v0.core._data_model.models.physical import PhysicalDataModel
from cognite.neat.v0.core._issues import IssueList
from cognite.neat.v0.core._issues.warnings import (
    PrincipleOneModelOneSpaceWarning,
    ResourceRetrievalWarning,
)
from cognite.neat.v0.core._shared import T_ID
from cognite.neat.v0.core._utils.upload import UploadResult

from ._base import CDFExporter


@dataclass
class ItemCategorized(Generic[T_ID, T_WriteClass]):
    resource_name: str
    as_id: Callable[[T_WriteClass], T_ID]
    to_create: list[T_WriteClass] = field(default_factory=list)
    to_update: list[T_WriteClass] = field(default_factory=list)
    to_delete: list[T_WriteClass] = field(default_factory=list)
    to_skip: list[T_WriteClass] = field(default_factory=list)
    unchanged: list[T_WriteClass] = field(default_factory=list)

    @property
    def to_create_ids(self) -> list[T_ID]:
        return [self.as_id(item) for item in self.to_create]

    @property
    def to_update_ids(self) -> list[T_ID]:
        return [self.as_id(item) for item in self.to_update]

    @property
    def to_skip_ids(self) -> list[T_ID]:
        return [self.as_id(item) for item in self.to_skip]

    @property
    def to_delete_ids(self) -> list[T_ID]:
        return [self.as_id(item) for item in self.to_delete]

    @property
    def unchanged_ids(self) -> list[T_ID]:
        return [self.as_id(item) for item in self.unchanged]

    def item_ids(self) -> Iterable[T_ID]:
        yield from (self.as_id(item) for item in self.to_create + self.to_update + self.to_delete + self.unchanged)


class DMSExporter(CDFExporter[PhysicalDataModel, DMSSchema]):
    """Export data model to Cognite Data Fusion's Data Model Storage (DMS) service.

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

    @property
    def description(self) -> str:
        return "Export verified DMS Model to CDF."

    def export_to_file(self, data_model: PhysicalDataModel, filepath: Path) -> None:
        """Export the data_model to a file(s).

        If the file is a directory, the components will be exported to separate files, otherwise they will be
        exported to a zip file.

        Args:
            filepath: Directory or zip file path to export to.
            data_model:
        """
        if filepath.is_dir():
            self._export_to_directory(filepath, data_model)
        else:
            self._export_to_zip_file(filepath, data_model)

    def _export_to_directory(self, directory: Path, data_model: PhysicalDataModel) -> None:
        schema = self.export(data_model)
        exclude = self._create_exclude_set()
        schema.to_directory(directory, exclude=exclude, new_line=self._new_line, encoding=self._encoding)

    def _export_to_zip_file(self, filepath: Path, data_model: PhysicalDataModel) -> None:
        if filepath.suffix not in {".zip"}:
            warnings.warn("File extension is not .zip, adding it to the file name", stacklevel=2)
            filepath = filepath.with_suffix(".zip")
        schema = self.export(data_model)
        exclude = self._create_exclude_set()
        schema.to_zip(filepath, exclude=exclude)

    def _create_exclude_set(self) -> set:
        if self.export_components is None:
            exclude = set()
        else:
            exclude = {"spaces", "data_models", "views", "containers", "node_types"} - set(self.export_components)
        return exclude

    def export(self, data_model: PhysicalDataModel) -> DMSSchema:
        # We do not want to include CogniteCore/CogniteProcess Industries in the schema
        return data_model.as_schema(instance_space=self.instance_space, remove_cdf_spaces=self.remove_cdf_spaces)

    def delete_from_cdf(
        self,
        data_model: PhysicalDataModel,
        client: NeatClient,
        dry_run: bool = False,
        skip_space: bool = False,
    ) -> Iterable[UploadResult]:
        schema = self.export(data_model)

        # we need to reverse order in which we are picking up the items to delete
        # as they are sorted in the order of creation and we need to delete them in reverse order
        for loader in reversed(client.loaders.by_dependency_order(self.export_components)):
            items = loader.items_from_schema(schema)
            item_ids = loader.get_ids(items)
            existing_items = loader.retrieve(item_ids)
            existing_ids = set(loader.get_ids(existing_items))
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

            result = UploadResult(loader.resource_name)  # type: ignore[var-annotated]
            if dry_run:
                result.deleted.update(to_delete)
                yield result
                continue

            if to_delete:
                try:
                    deleted = loader.delete(to_delete)
                except MultiCogniteAPIError as e:
                    result.deleted.update([loader.get_id(item) for item in e.success])
                    result.failed_deleted.update([loader.get_id(item) for item in e.failed])
                    for error in e.errors:
                        result.error_messages.append(f"Failed to delete {loader.resource_name}: {error!s}")
                else:
                    result.deleted.update(deleted)
            yield result

    def export_to_cdf_iterable(
        self, data_model: PhysicalDataModel, client: NeatClient, dry_run: bool = False
    ) -> Iterable[UploadResult]:
        schema = self.export(data_model)

        # The CDF UI does not deal well with a child view overwriting a parent property with the same name
        # This is a workaround to remove the duplicated properties
        self._remove_duplicated_properties(schema.views, client)

        categorized_items_by_loader = self._categorize_by_loader(client, schema)

        is_failing = self.existing == "fail" and any(
            loader.resource_name for loader, categorized in categorized_items_by_loader.items() if categorized.to_update
        )

        deleted_by_name: dict[str, UploadResult] = {}
        if not is_failing:
            # Deletion is done in reverse order to take care of dependencies
            for loader, items in reversed(categorized_items_by_loader.items()):
                issue_list = IssueList()

                if items.resource_name == client.loaders.data_models.resource_name:
                    warning_list = self._validate(list(items.item_ids()), client)
                    issue_list.extend(warning_list)

                results = UploadResult(loader.resource_name, issues=issue_list)  # type: ignore[var-annotated]
                if dry_run:
                    results.deleted.update(items.to_delete_ids)
                else:
                    if items.to_delete_ids:
                        try:
                            deleted = loader.delete(items.to_delete_ids)
                        except MultiCogniteAPIError as e:
                            results.deleted.update([loader.get_id(item) for item in e.success])
                            results.failed_deleted.update([loader.get_id(item) for item in e.failed])
                            for error in e.errors:
                                results.error_messages.append(f"Failed to delete {loader.resource_name}: {error!s}")
                        else:
                            results.deleted.update(deleted)
                deleted_by_name[loader.resource_name] = results

        for loader, items in categorized_items_by_loader.items():
            issue_list = IssueList()

            if items.resource_name == client.loaders.data_models.resource_name:
                warning_list = self._validate(list(items.item_ids()), client)
                issue_list.extend(warning_list)

            results = UploadResult(loader.resource_name, issues=issue_list)  # type: ignore[var-annotated]
            if is_failing:
                # If any component already exists, the export will fail.
                # This is the same if we run dry_run or not.
                results.failed_upserted.update(items.to_update_ids)
                results.failed_created.update(items.to_create_ids)
                results.failed_deleted.update(items.to_delete_ids)
                results.unchanged.update(items.unchanged_ids)
                results.error_messages.append("Existing components found and existing_handling is 'fail'")
                yield results
                continue

            results.unchanged.update(items.unchanged_ids)
            results.skipped.update(items.to_skip_ids)
            if delete_results := deleted_by_name.get(loader.resource_name):
                results.deleted.update(delete_results.deleted)
                results.failed_deleted.update(delete_results.failed_deleted)
                results.error_messages.extend(delete_results.error_messages)

            if dry_run:
                if self.existing in ["update", "force"]:
                    # Assume all changed are successful
                    results.changed.update(items.to_update_ids)
                elif self.existing == "skip":
                    results.skipped.update(items.to_update_ids)
                results.created.update(items.to_create_ids)
                yield results
                continue

            if items.to_create:
                try:
                    created = loader.create(items.to_create)
                except MultiCogniteAPIError as e:
                    results.created.update([loader.get_id(item) for item in e.success])
                    results.failed_created.update([loader.get_id(item) for item in e.failed])
                    for error in e.errors:
                        results.error_messages.append(f"Failed to create {loader.resource_name}: {error!s}")
                else:
                    results.created.update(loader.get_ids(created))

            if items.to_update and self.existing == "skip":
                results.skipped.update(items.to_update_ids)
            elif items.to_update:
                try:
                    updated = loader.update(items.to_update, force=self.existing == "force", drop_data=self.drop_data)
                except MultiCogniteAPIError as e:
                    results.changed.update([loader.get_id(item) for item in e.success])
                    results.failed_changed.update([loader.get_id(item) for item in e.failed])
                    for error in e.errors:
                        results.error_messages.append(f"Failed to update {loader.resource_name}: {error!s}")
                else:
                    results.changed.update(loader.get_ids(updated))

            yield results

    def _categorize_by_loader(self, client: NeatClient, schema: DMSSchema) -> dict[DataModelingLoader, ItemCategorized]:
        categorized_items_by_loader: dict[DataModelingLoader, ItemCategorized] = {}
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
        return categorized_items_by_loader

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
        categorized = ItemCategorized[T_ID, T_WriteClass](loader.resource_name, loader.get_id)
        for item in items:
            if (
                isinstance(items, DataModelApplyList)
                and self.include_space is not None
                and not loader.in_space(item, self.include_space)
            ):
                continue
            item_id = loader.get_id(item)
            cdf_item = cdf_item_by_id.get(item_id)
            if cdf_item is None:
                categorized.to_create.append(item)
            elif (is_redeploying or self.existing == "recreate") and not isinstance(item, SpaceApply):
                # Spaces are not deleted, instead they are updated. Deleting a space is an expensive operation
                # and are seldom needed. If you need to delete the space, it should be done in a different operation.
                if not self.drop_data and loader.has_data(item_id):
                    categorized.to_skip.append(cdf_item)
                else:
                    categorized.to_delete.append(cdf_item.as_write())
                    if isinstance(item, dm.DataModelApply) and self.existing != "recreate":
                        # Mypy failing to understand the output of merge is T_WriteClass.
                        categorized.to_create.append(loader.merge(item, cdf_item))  # type: ignore[arg-type]
                    else:
                        categorized.to_create.append(item)
            elif loader.are_equal(item, cdf_item):
                categorized.unchanged.append(item)
            elif loader.support_merge:
                categorized.to_update.append(loader.merge(item, cdf_item))
            else:
                categorized.to_update.append(item)
        return categorized

    def _validate(self, items: list[DataModelId], client: NeatClient) -> IssueList:
        issue_list = IssueList()
        if other_models := self._exist_other_data_models(client, items):
            warning = PrincipleOneModelOneSpaceWarning(
                f"There are multiple data models in the same space {items[0].space}. "
                f"Other data models in the space are {other_models}.",
            )
            if not self.suppress_warnings:
                warnings.warn(warning, stacklevel=2)
            issue_list.append(warning)

        return issue_list

    @classmethod
    def _exist_other_data_models(cls, client: NeatClient, model_ids: list[DataModelId]) -> list[DataModelId]:
        if not model_ids:
            return []
        space = model_ids[0].space
        external_id = model_ids[0].external_id
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

    @staticmethod
    def _remove_duplicated_properties(views: ViewApplyDict, client: NeatClient) -> None:
        parent_view_ids = {parent for view in views.values() for parent in view.implements}
        parent_view_list = client.data_modeling.views.retrieve(
            list(parent_view_ids), include_inherited_properties=False
        )
        parent_view_by_id = {view.as_id(): view.as_write() for view in parent_view_list}
        for view in views.values():
            if view.implements is None:
                continue
            for parent_id in view.implements:
                if not (parent_view := parent_view_by_id.get(parent_id)):
                    continue
                for shared_prop_id in set(view.properties or {}) & set(parent_view.properties or {}):
                    if view.properties is None or parent_view.properties is None:
                        continue
                    prop = view.properties[shared_prop_id]
                    parent_prop = parent_view.properties[shared_prop_id]
                    if (
                        isinstance(prop, dm.MappedPropertyApply)
                        and isinstance(parent_prop, dm.MappedPropertyApply)
                        and (
                            prop.container_property_identifier == parent_prop.container_property_identifier
                            and prop.container == parent_prop.container
                            and prop.source == parent_prop.source
                        )
                    ):
                        view.properties.pop(shared_prop_id)
