from collections import Counter
from collections.abc import Collection, Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier
from cognite.client.data_classes.data_modeling.containers import BTreeIndex, InvertedIndex
from cognite.client.data_classes.data_modeling.data_types import Enum as DMSEnum
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType, PropertyTypeWithUnit
from cognite.client.data_classes.data_modeling.views import (
    MultiEdgeConnectionApply,
    MultiReverseDirectRelationApply,
    SingleEdgeConnectionApply,
    SingleReverseDirectRelationApply,
    ViewPropertyApply,
)
from cognite.client.utils import ms_to_datetime

from cognite.neat._issues import IssueList, NeatIssue
from cognite.neat._issues.errors import FileTypeUnexpectedError, ResourceMissingIdentifierError, ResourceRetrievalError
from cognite.neat._issues.warnings import (
    PropertyNotFoundWarning,
    PropertyTypeNotSupportedWarning,
    ResourceNotFoundWarning,
    ResourcesDuplicatedWarning,
)
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.importers._base import BaseImporter, _handle_issues
from cognite.neat._rules.models import (
    DataModelType,
    DMSInputRules,
    DMSSchema,
    SchemaCompleteness,
)
from cognite.neat._rules.models.data_types import DataType, Enum
from cognite.neat._rules.models.dms import (
    DMSInputContainer,
    DMSInputEnum,
    DMSInputMetadata,
    DMSInputNode,
    DMSInputProperty,
    DMSInputView,
)
from cognite.neat._rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSNodeEntity,
    DMSUnknownEntity,
    EdgeEntity,
    ReverseConnectionEntity,
    ViewEntity,
)


class DMSImporter(BaseImporter[DMSInputRules]):
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
        read_issues: Sequence[NeatIssue] | None = None,
        metadata: DMSInputMetadata | None = None,
        ref_metadata: DMSInputMetadata | None = None,
    ):
        # Calling this root schema to distinguish it from
        # * User Schema
        # * Reference Schema
        self.root_schema = schema
        self.metadata = metadata
        self.ref_metadata = ref_metadata
        self.issue_list = IssueList(read_issues)
        self._all_containers_by_id = schema.containers.copy()
        self._all_views_by_id = schema.views.copy()
        if schema.reference:
            self._all_containers_by_id.update(schema.reference.containers.items())
            self._all_views_by_id.update(schema.reference.views.items())

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
            return cls(
                DMSSchema(),
                [
                    ResourceRetrievalError(
                        dm.DataModelId.load(data_model_id),  # type: ignore[arg-type]
                        "data model",
                        "Data Model is missing in CDF",
                    )
                ],
            )
        user_model = user_models.latest_version()

        if reference_model_id:
            ref_models = cls._find_model_in_list(data_models, reference_model_id)
            if len(ref_models) == 0:
                return cls(
                    DMSSchema(),
                    [
                        ResourceRetrievalError(
                            dm.DataModelId.load(reference_model_id), "data model", "Data Model is missing in CDF"
                        )
                    ],
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
    ) -> DMSInputMetadata:
        description, creator = DMSInputMetadata._get_description_and_creator(model.description)

        if isinstance(model, dm.DataModel):
            created = ms_to_datetime(model.created_time)
            updated = ms_to_datetime(model.last_updated_time)
        else:
            now = datetime.now().replace(microsecond=0)
            created = now
            updated = now
        return DMSInputMetadata(
            schema_="complete",
            data_model_type="solution" if has_reference else "enterprise",
            extension="addition",
            space=model.space,
            external_id=model.external_id,
            name=model.name or model.external_id,
            version=model.version or "0.1.0",
            updated=updated,
            created=created,
            creator=",".join(creator),
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
            return cls(DMSSchema(), [FileTypeUnexpectedError(Path(zip_file), frozenset([".zip"]))])
        issue_list = IssueList()
        with _handle_issues(issue_list) as _:
            schema = DMSSchema.from_zip(zip_file)
        return cls(schema, issue_list)

    def to_rules(self) -> ReadRules[DMSInputRules]:
        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_rules method will return None
            return ReadRules(None, self.issue_list, {})

        if not self.root_schema.data_model:
            self.issue_list.append(ResourceMissingIdentifierError("data model", type(self.root_schema).__name__))
            return ReadRules(None, self.issue_list, {})

        model = self.root_schema.data_model

        schema_completeness = SchemaCompleteness.complete
        data_model_type = DataModelType.enterprise
        reference: DMSInputRules | None = None
        if (ref_schema := self.root_schema.reference) and (ref_model := ref_schema.data_model):
            # Reference should always be an enterprise model.
            reference = self._create_rule_components(
                ref_model,
                ref_schema,
                self.ref_metadata or self._create_default_metadata(list(ref_schema.views.values()), is_ref=True),
                DataModelType.enterprise,
            )
            data_model_type = DataModelType.solution

        user_rules = self._create_rule_components(
            model,
            self.root_schema,
            self.metadata,
            data_model_type,
            schema_completeness,
            has_reference=reference is not None,
        )
        user_rules.reference = reference

        return ReadRules(user_rules, self.issue_list, {})

    def _create_rule_components(
        self,
        data_model: dm.DataModelApply,
        schema: DMSSchema,
        metadata: DMSInputMetadata | None = None,
        data_model_type: DataModelType | None = None,
        schema_completeness: SchemaCompleteness | None = None,
        has_reference: bool = False,
    ) -> DMSInputRules:
        properties: list[DMSInputProperty] = []
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

        metadata = metadata or DMSInputMetadata.from_data_model(data_model, has_reference)
        if data_model_type is not None:
            metadata.data_model_type = str(data_model_type)  # type: ignore[assignment]
        if schema_completeness is not None:
            metadata.schema_ = str(schema_completeness)  # type: ignore[assignment]

        enum = self._create_enum_collections(schema.containers.values())

        return DMSInputRules(
            metadata=metadata,
            properties=properties,
            containers=[DMSInputContainer.from_container(container) for container in schema.containers.values()],
            views=[
                DMSInputView.from_view(view, in_model=view_id in data_model_view_ids)
                for view_id, view in schema.views.items()
            ],
            nodes=[DMSInputNode.from_node_type(node_type) for node_type in schema.node_types.values()],
            enum=enum,
        )

    @classmethod
    def _create_default_metadata(
        cls, views: Sequence[dm.View | dm.ViewApply], is_ref: bool = False
    ) -> DMSInputMetadata:
        now = datetime.now().replace(microsecond=0)
        space = Counter(view.space for view in views).most_common(1)[0][0]
        return DMSInputMetadata(
            schema_="complete",
            extension="addition",
            data_model_type="enterprise" if is_ref else "solution",
            space=space,
            external_id="Unknown",
            version="0.1.0",
            creator="Unknown",
            created=now,
            updated=now,
        )

    def _create_dms_property(
        self, prop_id: str, prop: ViewPropertyApply, view_entity: ViewEntity, class_entity: ClassEntity
    ) -> DMSInputProperty | None:
        if isinstance(prop, dm.MappedPropertyApply) and prop.container not in self._all_containers_by_id:
            self.issue_list.append(
                ResourceNotFoundWarning[dm.ContainerId, dm.PropertyId](
                    dm.ContainerId.load(prop.container),
                    "container",
                    view_entity.to_property_id(prop_id),
                    "view property",
                )
            )
            return None
        if (
            isinstance(prop, dm.MappedPropertyApply)
            and prop.container_property_identifier not in self._all_containers_by_id[prop.container].properties
        ):
            self.issue_list.append(
                PropertyNotFoundWarning(prop.container, "container", prop_id, view_entity.as_id(), "view"),
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
                PropertyTypeNotSupportedWarning[dm.ViewId](view_entity.as_id(), "view", prop_id, type(prop).__name__)
            )
            return None

        value_type = self._get_value_type(prop, view_entity, prop_id)
        if value_type is None:
            return None

        return DMSInputProperty(
            class_=str(class_entity),
            property_=prop_id,
            description=prop.description,
            name=prop.name,
            connection=self._get_connection_type(prop),
            value_type=str(value_type),
            is_list=self._get_is_list(prop),
            nullable=self._get_nullable(prop),
            immutable=self._get_immutable(prop),
            default=self._get_default(prop),
            container=str(ContainerEntity.from_id(prop.container))
            if isinstance(prop, dm.MappedPropertyApply)
            else None,
            container_property=prop.container_property_identifier if isinstance(prop, dm.MappedPropertyApply) else None,
            view=str(view_entity),
            view_property=prop_id,
            index=self._get_index(prop, prop_id),
            constraint=self._get_constraint(prop, prop_id),
        )

    def _container_prop_unsafe(self, prop: dm.MappedPropertyApply) -> dm.ContainerProperty:
        """This method assumes you have already checked that the container with property exists."""
        return self._all_containers_by_id[prop.container].properties[prop.container_property_identifier]

    def _get_connection_type(
        self, prop: ViewPropertyApply
    ) -> Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None:
        if isinstance(prop, SingleEdgeConnectionApply | MultiEdgeConnectionApply):
            properties = ViewEntity.from_id(prop.edge_source) if prop.edge_source is not None else None
            return EdgeEntity(
                properties=properties, type=DMSNodeEntity.from_reference(prop.type), direction=prop.direction
            )
        elif isinstance(prop, SingleReverseDirectRelationApply | MultiReverseDirectRelationApply):
            return ReverseConnectionEntity(property=prop.through.property)
        elif isinstance(prop, dm.MappedPropertyApply) and isinstance(
            self._container_prop_unsafe(prop).type, dm.DirectRelation
        ):
            return "direct"
        else:
            return None

    def _get_value_type(
        self, prop: ViewPropertyApply, view_entity: ViewEntity, prop_id
    ) -> DataType | ViewEntity | DMSUnknownEntity | None:
        if isinstance(
            prop,
            SingleEdgeConnectionApply
            | MultiEdgeConnectionApply
            | SingleReverseDirectRelationApply
            | MultiReverseDirectRelationApply,
        ):
            return ViewEntity.from_id(prop.source)
        elif isinstance(prop, dm.MappedPropertyApply):
            container_prop = self._container_prop_unsafe(cast(dm.MappedPropertyApply, prop))
            if isinstance(container_prop.type, dm.DirectRelation):
                if prop.source is None or prop.source not in self._all_views_by_id:
                    return DMSUnknownEntity()
                else:
                    return ViewEntity.from_id(prop.source)
            elif isinstance(container_prop.type, PropertyTypeWithUnit) and container_prop.type.unit:
                return DataType.load(f"{container_prop.type._type}(unit={container_prop.type.unit.external_id})")
            elif isinstance(container_prop.type, DMSEnum):
                return Enum(collection=ClassEntity(suffix=prop_id), unknownValue=container_prop.type.unknown_value)
            else:
                return DataType.load(container_prop.type._type)
        else:
            self.issue_list.append(
                PropertyTypeNotSupportedWarning[dm.ViewId](view_entity.as_id(), "view", prop_id, type(prop).__name__)
            )
            return None

    def _get_nullable(self, prop: ViewPropertyApply) -> bool | None:
        if isinstance(prop, dm.MappedPropertyApply):
            return self._container_prop_unsafe(prop).nullable
        else:
            return None

    def _get_immutable(self, prop: ViewPropertyApply) -> bool | None:
        if isinstance(prop, dm.MappedPropertyApply):
            return self._container_prop_unsafe(prop).immutable
        else:
            return None

    def _get_is_list(self, prop: ViewPropertyApply) -> bool | None:
        if isinstance(prop, dm.MappedPropertyApply):
            prop_type = self._container_prop_unsafe(prop).type
            return isinstance(prop_type, ListablePropertyType) and prop_type.is_list
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
                    PropertyTypeNotSupportedWarning[dm.ContainerId](
                        prop.container, "container", prop_id, type(constraint_obj).__name__
                    )
                )
        return unique_constraints or None

    def _find_reverse_edge(
        self, prop_id: str, prop: SingleEdgeConnectionApply | MultiEdgeConnectionApply, view_id: dm.ViewId
    ) -> str | None:
        if prop.source not in self._all_views_by_id:
            return None
        view = self._all_views_by_id[prop.source]
        candidates = []
        for prop_name, reverse_prop in (view.properties or {}).items():
            if isinstance(reverse_prop, SingleEdgeConnectionApply | MultiEdgeConnectionApply):
                if (
                    reverse_prop.type == prop.type
                    and reverse_prop.source == view_id
                    and reverse_prop.direction != prop.direction
                ):
                    candidates.append(prop_name)
        if len(candidates) == 0:
            self.issue_list.append(
                PropertyNotFoundWarning(
                    prop.source,
                    "view property",
                    f"reverse edge of {prop_id}",
                    dm.PropertyId(view_id, prop_id),
                    "view property",
                )
            )
            return None
        if len(candidates) > 1:
            self.issue_list.append(
                ResourcesDuplicatedWarning(
                    frozenset(dm.PropertyId(view.as_id(), candidate) for candidate in candidates),
                    "view property",
                    default_action="Multiple reverse edges found for "
                    f"{dm.PropertyId(view_id, prop_id)!r}. Will use {candidates[0]}",
                )
            )

        return candidates[0]

    @staticmethod
    def _create_enum_collections(containers: Collection[dm.ContainerApply]) -> list[DMSInputEnum] | None:
        enum_collections: list[DMSInputEnum] = []
        for container in containers:
            for prop_id, prop in container.properties.items():
                if isinstance(prop.type, DMSEnum):
                    for identifier, value in prop.type.values.items():
                        enum_collections.append(
                            DMSInputEnum(
                                collection=prop_id, value=identifier, name=value.name, description=value.description
                            )
                        )
        return enum_collections
