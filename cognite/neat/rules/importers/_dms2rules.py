from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast, overload

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier
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
from cognite.neat.rules.models import (
    DataModelType,
    DMSRules,
    DMSSchema,
    ExtensionCategory,
    RoleTypes,
    SchemaCompleteness,
    SheetList,
)
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.dms import (
    DMSContainer,
    DMSMetadata,
    DMSProperty,
    DMSView,
)
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    ViewEntity,
    ViewPropertyEntity,
)


class DMSImporter(BaseImporter):
    """Imports a Data Model from Cognite Data Fusion.

    Args:
        schema: The schema containing the data model.
        read_issues: A list of issues that occurred during the import.
        metadata: Metadata for the data model.
        ref_metadata: Metadata for the reference data model.

    """

    def __init__(
        self,
        schema: DMSSchema,
        read_issues: Sequence[ValidationIssue] | None = None,
        metadata: DMSMetadata | None = None,
        ref_metadata: DMSMetadata | None = None,
    ):
        # Calling this root schema to distinguish it from
        # * User Schema
        # * Reference Schema
        self.root_schema = schema
        self.metadata = metadata
        self.ref_metadata = ref_metadata
        self.issue_list = IssueList(read_issues)
        self._all_containers_by_id = schema.containers.copy()
        self._all_view_ids = set(self.root_schema.views.keys())
        if self.root_schema.reference:
            self._all_containers_by_id.update(self.root_schema.reference.containers)
            self._all_view_ids.update(self.root_schema.reference.views.keys())

    @classmethod
    def from_data_model_id(
        cls,
        client: CogniteClient,
        data_model_id: DataModelIdentifier,
        reference_model_id: DataModelIdentifier | None = None,
    ) -> "DMSImporter":
        """Create a DMSImporter ready to convert the given data model to rules.

        Args:
            client: Instantiated CogniteClient to retrieve data model.
            reference_model_id: The reference data model to retrieve. This is the data model that
                the given data model is built on top of, typically, an enterprise data model.
            data_model_id: Data Model to retrieve.

        Returns:
            DMSImporter: DMSImporter instance
        """
        data_model_ids = [data_model_id, reference_model_id] if reference_model_id else [data_model_id]
        data_models = client.data_modeling.data_models.retrieve(data_model_ids, inline_views=True)

        user_models = cls._find_model_in_list(data_models, data_model_id)
        if len(user_models) == 0:
            return cls(DMSSchema(), [issues.importing.NoDataModelError(f"Data model {data_model_id} not found")])
        user_model = user_models.latest_version()

        if reference_model_id:
            ref_models = cls._find_model_in_list(data_models, reference_model_id)
            if len(ref_models) == 0:
                return cls(
                    DMSSchema(), [issues.importing.NoDataModelError(f"Data model {reference_model_id} not found")]
                )
            ref_model: dm.DataModel[dm.View] | None = ref_models.latest_version()
        else:
            ref_model = None

        issue_list = IssueList()
        with _handle_issues(issue_list) as result:
            schema = DMSSchema.from_data_model(client, user_model, ref_model)

        if result.result == "failure" or issue_list.has_errors:
            return cls(DMSSchema(), issue_list)

        metadata = cls._create_metadata_from_model(user_model, has_reference=ref_model is not None)
        ref_metadata = cls._create_metadata_from_model(ref_model) if ref_model else None

        return cls(schema, issue_list, metadata, ref_metadata)

    @classmethod
    def _find_model_in_list(
        cls, data_models: dm.DataModelList[dm.View], model_id: DataModelIdentifier
    ) -> dm.DataModelList[dm.View]:
        identifier = DataModelId.load(model_id)
        return dm.DataModelList[dm.View](
            [
                model
                for model in data_models
                if (model.space, model.external_id) == (identifier.space, identifier.external_id)
            ]
        )

    @classmethod
    def _create_metadata_from_model(
        cls,
        model: dm.DataModel[dm.View] | dm.DataModelApply,
        has_reference: bool = False,
    ) -> DMSMetadata:
        description, creator = DMSMetadata._get_description_and_creator(model.description)

        if isinstance(model, dm.DataModel):
            created = ms_to_datetime(model.created_time)
            updated = ms_to_datetime(model.last_updated_time)
        else:
            now = datetime.now().replace(microsecond=0)
            created = now
            updated = now
        return DMSMetadata(
            schema_=SchemaCompleteness.complete,
            data_model_type=DataModelType.solution if has_reference else DataModelType.enterprise,
            extension=ExtensionCategory.addition,
            space=model.space,
            external_id=model.external_id,
            name=model.name or model.external_id,
            version=model.version or "0.1.0",
            updated=updated,
            created=created,
            creator=creator,
            description=description,
        )

    @classmethod
    def from_directory(cls, directory: str | Path) -> "DMSImporter":
        issue_list = IssueList()
        with _handle_issues(issue_list) as _:
            schema = DMSSchema.from_directory(directory)
        # If there were errors during the import, the to_rules
        return cls(schema, issue_list)

    @classmethod
    def from_zip_file(cls, zip_file: str | Path) -> "DMSImporter":
        if Path(zip_file).suffix != ".zip":
            return cls(DMSSchema(), [issues.fileread.InvalidFileFormatError(Path(zip_file), [".zip"])])
        issue_list = IssueList()
        with _handle_issues(issue_list) as _:
            schema = DMSSchema.from_zip(zip_file)
        return cls(schema, issue_list)

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules: ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]: ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_rules method will return None
            return self._return_or_raise(self.issue_list, errors)

        if not self.root_schema.data_model:
            self.issue_list.append(issues.importing.NoDataModelError("No data model found."))
            return self._return_or_raise(self.issue_list, errors)
        model = self.root_schema.data_model
        with _handle_issues(
            self.issue_list,
        ) as future:
            schema_completeness = SchemaCompleteness.complete
            data_model_type = DataModelType.enterprise
            reference: DMSRules | None = None
            if (ref_schema := self.root_schema.reference) and (ref_model := ref_schema.data_model):
                # Reference should always be an enterprise model.
                reference = DMSRules(
                    **self._create_rule_components(
                        ref_model,
                        ref_schema,
                        self.ref_metadata
                        or self._create_default_metadata(list(ref_schema.views.values()), is_ref=True),
                        DataModelType.enterprise,
                    )
                )
                data_model_type = DataModelType.solution

            user_rules = DMSRules(
                **self._create_rule_components(
                    model,
                    self.root_schema,
                    self.metadata,
                    data_model_type,
                    schema_completeness,
                    has_reference=reference is not None,
                ),
                reference=reference,
            )

        if future.result == "failure" or self.issue_list.has_errors:
            return self._return_or_raise(self.issue_list, errors)

        return self._to_output(user_rules, self.issue_list, errors, role)

    def _create_rule_components(
        self,
        data_model: dm.DataModelApply,
        schema: DMSSchema,
        metadata: DMSMetadata | None = None,
        data_model_type: DataModelType | None = None,
        schema_completeness: SchemaCompleteness | None = None,
        has_reference: bool = False,
    ) -> dict[str, Any]:
        properties = SheetList[DMSProperty]()
        for view_id, view in schema.views.items():
            view_entity = ViewEntity.from_id(view_id)
            class_entity = view_entity.as_class()
            for prop_id, prop in (view.properties or {}).items():
                dms_property = self._create_dms_property(prop_id, prop, view_entity, class_entity)
                if dms_property is not None:
                    properties.append(dms_property)

        data_model_view_ids: set[dm.ViewId] = {
            view.as_id() if isinstance(view, dm.View | dm.ViewApply) else view for view in data_model.views or []
        }

        metadata = metadata or DMSMetadata.from_data_model(data_model, has_reference)
        if data_model_type is not None:
            metadata.data_model_type = data_model_type
        if schema_completeness is not None:
            metadata.schema_ = schema_completeness
        return dict(
            metadata=metadata,
            properties=properties,
            containers=SheetList[DMSContainer](
                data=[DMSContainer.from_container(container) for container in schema.containers.values()]
            ),
            views=SheetList[DMSView](
                data=[
                    DMSView.from_view(view, in_model=view_id in data_model_view_ids)
                    for view_id, view in schema.views.items()
                ]
            ),
        )

    @classmethod
    def _create_default_metadata(cls, views: Sequence[dm.View | dm.ViewApply], is_ref: bool = False) -> DMSMetadata:
        now = datetime.now().replace(microsecond=0)
        space = Counter(view.space for view in views).most_common(1)[0][0]
        return DMSMetadata(
            schema_=SchemaCompleteness.complete,
            extension=ExtensionCategory.addition,
            data_model_type=DataModelType.enterprise if is_ref else DataModelType.solution,
            space=space,
            external_id="Unknown",
            version="0.1.0",
            creator=["Unknown"],
            created=now,
            updated=now,
        )

    def _create_dms_property(
        self, prop_id: str, prop: ViewPropertyApply, view_entity: ViewEntity, class_entity: ClassEntity
    ) -> DMSProperty | None:
        if isinstance(prop, dm.MappedPropertyApply) and prop.container not in self._all_containers_by_id:
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
            and prop.container_property_identifier not in self._all_containers_by_id[prop.container].properties
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
            connection=self._get_relation_type(prop),
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
        return self._all_containers_by_id[prop.container].properties[prop.container_property_identifier]

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
                if prop.source is None or prop.source not in self._all_view_ids:
                    # The warning is issued when the DMS Rules are created.
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
        container = self._all_containers_by_id[prop.container]
        index: list[str] = []
        for index_name, index_obj in (container.indexes or {}).items():
            if isinstance(index_obj, BTreeIndex | InvertedIndex) and prop_id in index_obj.properties:
                index.append(index_name)
        return index or None

    def _get_constraint(self, prop: ViewPropertyApply, prop_id: str) -> list[str] | None:
        if not isinstance(prop, dm.MappedPropertyApply):
            return None
        container = self._all_containers_by_id[prop.container]
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
