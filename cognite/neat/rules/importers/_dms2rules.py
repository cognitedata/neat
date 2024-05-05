from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal, cast, overload

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelIdentifier
from cognite.client.data_classes.data_modeling.containers import BTreeIndex, InvertedIndex
from cognite.client.data_classes.data_modeling.views import (
    MultiEdgeConnectionApply,
    MultiReverseDirectRelationApply,
    SingleEdgeConnectionApply,
    SingleReverseDirectRelationApply,
    ViewPropertyApply,
)
from cognite.client.utils import ms_to_datetime

from cognite.neat.rules import issues
from cognite.neat.rules.importers._base import BaseImporter, Rules, _handle_issues
from cognite.neat.rules.issues import IssueList, ValidationIssue
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DataModelEntity,
    DMSUnknownEntity,
    ViewEntity,
    ViewPropertyEntity,
)
from cognite.neat.rules.models.rules import DMSRules, DMSSchema, RoleTypes
from cognite.neat.rules.models.rules._base import DataModelType, ExtensionCategory, SchemaCompleteness
from cognite.neat.rules.models.rules._dms_architect_rules import (
    DMSContainer,
    DMSMetadata,
    DMSProperty,
    DMSView,
    SheetList,
)


class DMSImporter(BaseImporter):
    def __init__(
        self,
        schema: DMSSchema,
        read_issues: Sequence[ValidationIssue] | None = None,
        metadata: DMSMetadata | None = None,
    ):
        self.schema = schema
        self.metadata = metadata
        self.issue_list = IssueList(read_issues)
        self._container_by_id = {container.as_id(): container for container in schema.containers}

    @classmethod
    def from_data_model_id(cls, client: CogniteClient, data_model_id: DataModelIdentifier) -> "DMSImporter":
        """Create a DMSImporter ready to convert the given data model to rules.

        Args:
            client: Instantiated CogniteClient to retrieve data model.
            data_model_id: Data Model to retrieve.

        Returns:
            DMSImporter: DMSImporter instance
        """
        data_models = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True)
        if len(data_models) == 0:
            raise ValueError(f"Data model {data_model_id} not found")
        data_model = data_models.latest_version()

        schema = DMSSchema.from_data_model(client, data_model)

        created = ms_to_datetime(data_model.created_time)
        updated = ms_to_datetime(data_model.last_updated_time)

        metadata = cls._create_metadata_from_model(data_model, created, updated)

        return cls(schema, [], metadata)

    @classmethod
    def _create_metadata_from_model(
        cls,
        model: dm.DataModel[dm.View] | dm.DataModelApply,
        created: datetime | None = None,
        updated: datetime | None = None,
    ) -> DMSMetadata:
        description, creator = DMSMetadata._get_description_and_creator(model.description)
        now = datetime.now().replace(microsecond=0)
        return DMSMetadata(
            schema_=SchemaCompleteness.complete,
            extension=ExtensionCategory.addition,
            space=model.space,
            external_id=model.external_id,
            name=model.name or model.external_id,
            version=model.version or "0.1.0",
            updated=updated or now,
            created=created or now,
            creator=creator,
            description=description,
            default_view_version=model.version or "0.1.0",
        )

    @classmethod
    def from_directory(cls, directory: str | Path) -> "DMSImporter":
        return cls(DMSSchema.from_directory(directory), [])

    @classmethod
    def from_zip_file(cls, zip_file: str | Path) -> "DMSImporter":
        if Path(zip_file).suffix != ".zip":
            raise ValueError("File extension is not .zip")
        return cls(DMSSchema.from_zip(zip_file), [])

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules: ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]: ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        if len(self.schema.data_models) == 0:
            self.issue_list.append(issues.importing.NoDataModelError("No data model found."))
            return self._return_or_raise(self.issue_list, errors)

        if len(self.schema.data_models) > 2:
            # Creating a DataModelEntity to convert the data model id to a string.
            self.issue_list.append(
                issues.importing.MultipleDataModelsWarning(
                    [str(DataModelEntity.from_id(model.as_id())) for model in self.schema.data_models]
                )
            )

        data_model = self.schema.data_models[0]

        properties = SheetList[DMSProperty]()
        ref_properties = SheetList[DMSProperty]()
        for view in self.schema.views:
            view_id = view.as_id()
            view_entity = ViewEntity.from_id(view_id)
            class_entity = view_entity.as_class()
            for prop_id, prop in (view.properties or {}).items():
                dms_property = self._create_dms_property(prop_id, prop, view_entity, class_entity)
                if dms_property is not None:
                    if view_id in self.schema.frozen_ids:
                        ref_properties.append(dms_property)
                    else:
                        properties.append(dms_property)

        data_model_view_ids: set[dm.ViewId] = {
            view.as_id() if isinstance(view, dm.View | dm.ViewApply) else view for view in data_model.views or []
        }

        metadata = self.metadata or DMSMetadata.from_data_model(data_model)
        metadata.data_model_type = self._infer_data_model_type(metadata.space)
        if ref_properties:
            metadata.schema_ = SchemaCompleteness.extended

        with _handle_issues(
            self.issue_list,
        ) as future:
            user_rules = DMSRules(
                metadata=metadata,
                properties=properties,
                containers=SheetList[DMSContainer](
                    data=[
                        DMSContainer.from_container(container)
                        for container in self.schema.containers
                        if container.as_id() not in self.schema.frozen_ids
                    ]
                ),
                views=SheetList[DMSView](
                    data=[
                        DMSView.from_view(view, in_model=view.as_id() in data_model_view_ids)
                        for view in self.schema.views
                        if view.as_id() not in self.schema.frozen_ids
                    ]
                ),
                reference=self._create_reference_rules(ref_properties),
            )

        if future.result == "failure" or self.issue_list.has_errors:
            return self._return_or_raise(self.issue_list, errors)

        return self._to_output(user_rules, self.issue_list, errors, role)

    def _create_reference_rules(self, properties: SheetList[DMSProperty]) -> DMSRules | None:
        if not properties:
            return None

        if len(self.schema.data_models) == 2:
            data_model = self.schema.data_models[1]
            data_model_view_ids: set[dm.ViewId] = {
                view.as_id() if isinstance(view, dm.View | dm.ViewApply) else view for view in data_model.views or []
            }
            metadata = self._create_metadata_from_model(data_model)
        else:
            data_model_view_ids = set()
            now = datetime.now().replace(microsecond=0)
            space = Counter(prop.view.space for prop in properties).most_common(1)[0][0]
            metadata = DMSMetadata(
                schema_=SchemaCompleteness.complete,
                extension=ExtensionCategory.addition,
                space=space,
                external_id="Unknown",
                version="0.1.0",
                creator=["Unknown"],
                created=now,
                updated=now,
            )

        metadata.data_model_type = DataModelType.enterprise
        return DMSRules(
            metadata=metadata,
            properties=properties,
            views=SheetList[DMSView](
                data=[
                    DMSView.from_view(view, in_model=not data_model_view_ids or (view.as_id() in data_model_view_ids))
                    for view in self.schema.views
                    if view.as_id() in self.schema.frozen_ids
                ]
            ),
            containers=SheetList[DMSContainer](
                data=[
                    DMSContainer.from_container(container)
                    for container in self.schema.containers
                    if container.as_id() in self.schema.frozen_ids
                ]
            ),
            reference=None,
        )

    def _infer_data_model_type(self, space: str) -> DataModelType:
        if self.schema.referenced_spaces() - {space}:
            # If the data model has containers, views, node types in another space
            # we assume it is a solution model.
            return DataModelType.solution
        else:
            # All containers, views, node types are in the same space as the data model
            return DataModelType.enterprise

    def _create_dms_property(
        self, prop_id: str, prop: ViewPropertyApply, view_entity: ViewEntity, class_entity: ClassEntity
    ) -> DMSProperty | None:
        if isinstance(prop, dm.MappedPropertyApply) and prop.container not in self._container_by_id:
            self.issue_list.append(
                issues.importing.MissingContainerWarning(
                    view_id=str(view_entity),
                    property_=prop_id,
                    container_id=str(ContainerEntity.from_id(prop.container)),
                )
            )
            return None
        if (
            isinstance(prop, dm.MappedPropertyApply)
            and prop.container_property_identifier not in self._container_by_id[prop.container].properties
        ):
            self.issue_list.append(
                issues.importing.MissingContainerPropertyWarning(
                    view_id=str(view_entity),
                    property_=prop_id,
                    container_id=str(ContainerEntity.from_id(prop.container)),
                )
            )
            return None
        if not isinstance(
            prop,
            dm.MappedPropertyApply
            | SingleEdgeConnectionApply
            | MultiEdgeConnectionApply
            | SingleReverseDirectRelationApply
            | MultiReverseDirectRelationApply,
        ):
            self.issue_list.append(
                issues.importing.UnknownPropertyTypeWarning(view_entity.versioned_id, prop_id, type(prop).__name__)
            )
            return None

        value_type = self._get_value_type(prop, view_entity, prop_id)
        if value_type is None:
            return None

        return DMSProperty(
            class_=class_entity,
            property_=prop_id,
            description=prop.description,
            name=prop.name,
            relation=self._get_relation_type(prop),
            value_type=value_type,
            is_list=self._get_is_list(prop),
            nullable=self._get_nullable(prop),
            default=self._get_default(prop),
            container=ContainerEntity.from_id(prop.container) if isinstance(prop, dm.MappedPropertyApply) else None,
            container_property=prop.container_property_identifier if isinstance(prop, dm.MappedPropertyApply) else None,
            view=view_entity,
            view_property=prop_id,
            index=self._get_index(prop, prop_id),
            constraint=self._get_constraint(prop, prop_id),
        )

    def _container_prop_unsafe(self, prop: dm.MappedPropertyApply) -> dm.ContainerProperty:
        """This method assumes you have already checked that the container with property exists."""
        return self._container_by_id[prop.container].properties[prop.container_property_identifier]

    def _get_relation_type(self, prop: ViewPropertyApply) -> Literal["edge", "reverse", "direct"] | None:
        if isinstance(prop, SingleEdgeConnectionApply | MultiEdgeConnectionApply) and prop.direction == "outwards":
            return "edge"
        elif isinstance(prop, SingleEdgeConnectionApply | MultiEdgeConnectionApply) and prop.direction == "inwards":
            return "reverse"
        elif isinstance(prop, SingleReverseDirectRelationApply | MultiReverseDirectRelationApply):
            return "reverse"
        elif isinstance(prop, dm.MappedPropertyApply) and isinstance(
            self._container_prop_unsafe(prop).type, dm.DirectRelation
        ):
            return "direct"
        else:
            return None

    def _get_value_type(
        self, prop: ViewPropertyApply, view_entity: ViewEntity, prop_id
    ) -> DataType | ViewEntity | ViewPropertyEntity | DMSUnknownEntity | None:
        if isinstance(prop, SingleEdgeConnectionApply | MultiEdgeConnectionApply) and prop.direction == "outwards":
            return ViewEntity.from_id(prop.source)
        elif isinstance(prop, SingleReverseDirectRelationApply | MultiReverseDirectRelationApply):
            return ViewPropertyEntity.from_id(prop.through)
        elif isinstance(prop, SingleEdgeConnectionApply | MultiEdgeConnectionApply) and prop.direction == "inwards":
            return ViewEntity.from_id(prop.source)
        elif isinstance(prop, dm.MappedPropertyApply):
            container_prop = self._container_prop_unsafe(cast(dm.MappedPropertyApply, prop))
            if isinstance(container_prop.type, dm.DirectRelation):
                if prop.source is None:
                    self.issue_list.append(issues.importing.UnknownValueTypeWarning(str(view_entity), prop_id))
                    return DMSUnknownEntity()
                else:
                    return ViewEntity.from_id(prop.source)
            else:
                return DataType.load(container_prop.type._type)
        else:
            self.issue_list.append(issues.importing.FailedToInferValueTypeWarning(str(view_entity), prop_id))
            return None

    def _get_nullable(self, prop: ViewPropertyApply) -> bool | None:
        if isinstance(prop, dm.MappedPropertyApply):
            return self._container_prop_unsafe(prop).nullable
        else:
            return None

    def _get_is_list(self, prop: ViewPropertyApply) -> bool | None:
        if isinstance(prop, dm.MappedPropertyApply):
            return self._container_prop_unsafe(prop).type.is_list
        elif isinstance(prop, MultiEdgeConnectionApply | MultiReverseDirectRelationApply):
            return True
        elif isinstance(prop, SingleEdgeConnectionApply | SingleReverseDirectRelationApply):
            return False
        else:
            return None

    def _get_default(self, prop: ViewPropertyApply) -> str | None:
        if isinstance(prop, dm.MappedPropertyApply):
            default = self._container_prop_unsafe(prop).default_value
            if default is not None:
                return str(default)
        return None

    def _get_index(self, prop: ViewPropertyApply, prop_id) -> list[str] | None:
        if not isinstance(prop, dm.MappedPropertyApply):
            return None
        container = self._container_by_id[prop.container]
        index: list[str] = []
        for index_name, index_obj in (container.indexes or {}).items():
            if isinstance(index_obj, BTreeIndex | InvertedIndex) and prop_id in index_obj.properties:
                index.append(index_name)
        return index or None

    def _get_constraint(self, prop: ViewPropertyApply, prop_id: str) -> list[str] | None:
        if not isinstance(prop, dm.MappedPropertyApply):
            return None
        container = self._container_by_id[prop.container]
        unique_constraints: list[str] = []
        for constraint_name, constraint_obj in (container.constraints or {}).items():
            if isinstance(constraint_obj, dm.RequiresConstraint):
                # This is handled in the .from_container method of DMSContainer
                continue
            elif isinstance(constraint_obj, dm.UniquenessConstraint) and prop_id in constraint_obj.properties:
                unique_constraints.append(constraint_name)
            elif isinstance(constraint_obj, dm.UniquenessConstraint):
                # This does not apply to this property
                continue
            else:
                self.issue_list.append(
                    issues.importing.UnknownContainerConstraintWarning(
                        str(ContainerEntity.from_id(prop.container)), prop_id, type(constraint_obj).__name__
                    )
                )
        return unique_constraints or None
