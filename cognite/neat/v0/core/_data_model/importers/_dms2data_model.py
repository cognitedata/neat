import warnings
from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier
from cognite.client.data_classes.data_modeling.containers import BTreeIndex, InvertedIndex
from cognite.client.data_classes.data_modeling.data_types import (
    DirectRelation,
    ListablePropertyType,
    PropertyTypeWithUnit,
)
from cognite.client.data_classes.data_modeling.data_types import Enum as DMSEnum
from cognite.client.data_classes.data_modeling.views import (
    MultiEdgeConnectionApply,
    MultiReverseDirectRelationApply,
    ReverseDirectRelation,
    SingleEdgeConnection,
    SingleEdgeConnectionApply,
    SingleReverseDirectRelation,
    SingleReverseDirectRelationApply,
    View,
    ViewProperty,
    ViewPropertyApply,
)
from cognite.client.utils import ms_to_datetime

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._constants import (
    DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT,
    DMS_PRIMITIVE_LIST_DEFAULT_LIMIT,
)
from cognite.neat.v0.core._data_model._shared import ImportedDataModel
from cognite.neat.v0.core._data_model.importers._base import BaseImporter
from cognite.neat.v0.core._data_model.models import (
    DMSSchema,
    UnverifiedPhysicalDataModel,
)
from cognite.neat.v0.core._data_model.models.conceptual import (
    UnverifiedConcept,
    UnverifiedConceptualProperty,
)
from cognite.neat.v0.core._data_model.models.data_types import DataType, Enum, String
from cognite.neat.v0.core._data_model.models.entities import (
    ConceptEntity,
    ContainerEntity,
    ContainerIndexEntity,
    DMSNodeEntity,
    EdgeEntity,
    PhysicalUnknownEntity,
    ReverseConnectionEntity,
    ViewEntity,
)
from cognite.neat.v0.core._data_model.models.entities._single_value import ContainerConstraintEntity
from cognite.neat.v0.core._data_model.models.physical import (
    UnverifiedPhysicalContainer,
    UnverifiedPhysicalEnum,
    UnverifiedPhysicalMetadata,
    UnverifiedPhysicalNodeType,
    UnverifiedPhysicalProperty,
    UnverifiedPhysicalView,
)
from cognite.neat.v0.core._issues import (
    IssueList,
    MultiValueError,
    NeatIssue,
    catch_issues,
)
from cognite.neat.v0.core._issues.errors import (
    FileNotFoundNeatError,
    FileTypeUnexpectedError,
    NeatValueError,
    PropertyTypeNotSupportedError,
    ResourceMissingIdentifierError,
    ResourceRetrievalError,
)
from cognite.neat.v0.core._issues.warnings import (
    MissingCogniteClientWarning,
    NeatValueWarning,
    PropertyNotFoundWarning,
    PropertyTypeNotSupportedWarning,
    ResourceNotFoundWarning,
    ResourcesDuplicatedWarning,
    ResourceUnknownWarning,
)


class DMSImporter(BaseImporter[UnverifiedPhysicalDataModel]):
    """Imports a Data Model from Cognite Data Fusion.

    Args:
        schema: The schema containing the data model.
        read_issues: A list of issues that occurred during the import.
        metadata: Metadata for the data model.

    """

    def __init__(
        self,
        schema: DMSSchema,
        read_issues: Sequence[NeatIssue] | None = None,
        metadata: UnverifiedPhysicalMetadata | None = None,
        referenced_containers: Iterable[dm.ContainerApply] | None = None,
    ):
        self.schema = schema
        self.metadata = metadata
        self.issue_list = IssueList(read_issues)
        self._all_containers_by_id = schema.containers.copy()
        self._all_views_by_id = schema.views.copy()
        if referenced_containers is not None:
            for container in referenced_containers:
                if container.as_id() in self._all_containers_by_id:
                    continue
                self._all_containers_by_id[container.as_id()] = container

    @property
    def description(self) -> str:
        if self.schema.data_model is not None:
            identifier = f"{self.schema.data_model.as_id().as_tuple()!s}"
        else:
            identifier = "Unknown"
        return f"DMS Data model {identifier} read as unverified data model"

    @classmethod
    def from_data_model_id(
        cls,
        client: NeatClient,
        data_model_id: DataModelIdentifier,
    ) -> "DMSImporter":
        """Create a DMSImporter ready to convert the given DMS data model to neat representation.

        Args:
            client: Instantiated CogniteClient to retrieve data model.
            data_model_id: Data Model to retrieve.

        Returns:
            DMSImporter: DMSImporter instance
        """

        data_model_ids = [data_model_id]
        data_models = client.data_modeling.data_models.retrieve(data_model_ids, inline_views=True)

        retrieved_models = cls._find_model_in_list(data_models, data_model_id)
        if len(retrieved_models) == 0:
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
        return cls.from_data_model(client, retrieved_models.latest_version())

    @classmethod
    def from_data_model(cls, client: NeatClient, model: dm.DataModel[dm.View]) -> "DMSImporter":
        with catch_issues() as issue_list:
            schema = client.schema.retrieve_data_model(model)

        if issue_list.has_errors:
            return cls(DMSSchema(), issue_list)

        metadata = cls._create_metadata_from_model(model)

        return cls(
            schema,
            issue_list,
            metadata,
            referenced_containers=cls._lookup_referenced_containers(schema, issue_list, client),
        )

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
    ) -> UnverifiedPhysicalMetadata:
        description, creator = UnverifiedPhysicalMetadata._get_description_and_creator(model.description)

        if isinstance(model, dm.DataModel):
            created = ms_to_datetime(model.created_time)
            updated = ms_to_datetime(model.last_updated_time)
        else:
            now = datetime.now().replace(microsecond=0)
            created = now
            updated = now

        return UnverifiedPhysicalMetadata(
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
    def from_directory(cls, directory: str | Path, client: NeatClient | None = None) -> "DMSImporter":
        with catch_issues() as issue_list:
            schema = DMSSchema.from_directory(directory)
        # If there were errors during the import, the to_data_model will raise them.
        return cls(
            schema, issue_list, referenced_containers=cls._lookup_referenced_containers(schema, issue_list, client)
        )

    @classmethod
    def from_zip_file(cls, zip_file: str | Path, client: NeatClient | None = None) -> "DMSImporter":
        if Path(zip_file).suffix != ".zip":
            return cls(
                DMSSchema(),
                [FileTypeUnexpectedError(Path(zip_file), frozenset([".zip"]))],
            )
        with catch_issues() as issue_list:
            schema = DMSSchema.from_zip(zip_file)
        return cls(
            schema, issue_list, referenced_containers=cls._lookup_referenced_containers(schema, issue_list, client)
        )

    @classmethod
    def _lookup_referenced_containers(
        cls, schema: DMSSchema, issue_list: IssueList, client: NeatClient | None = None
    ) -> Iterable[dm.ContainerApply]:
        ref_containers = schema.externally_referenced_containers()
        if not ref_containers:
            return []
        elif client is None:
            id_ = ""
            if schema.data_model:
                id_ = f" {schema.data_model.as_id()!r}"
            issue_list.append(MissingCogniteClientWarning(f"importing full DMS model{id_}"))
            return []
        return client.loaders.containers.retrieve(list(ref_containers), format="write")

    @classmethod
    def from_path(cls, path: Path, client: NeatClient | None = None) -> "DMSImporter":
        if path.is_file():
            return cls.from_zip_file(path, client)
        elif path.is_dir():
            return cls.from_directory(path, client)
        else:
            raise FileNotFoundNeatError(path)

    def to_data_model(self) -> ImportedDataModel[UnverifiedPhysicalDataModel]:
        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_data_model method will return None
            self.issue_list.trigger_warnings()
            raise MultiValueError(self.issue_list.errors)

        if not self.schema.data_model:
            self.issue_list.append(ResourceMissingIdentifierError("data model", type(self.schema).__name__))
            self.issue_list.trigger_warnings()
            raise MultiValueError(self.issue_list.errors)

        model = self.schema.data_model

        user_data_model = self._create_data_model_components(model, self.schema, self.metadata)

        self.issue_list.trigger_warnings()
        if self.issue_list.has_errors:
            raise MultiValueError(self.issue_list.errors)
        return ImportedDataModel(user_data_model, None)

    def _create_data_model_components(
        self,
        data_model: dm.DataModelApply,
        schema: DMSSchema,
        metadata: UnverifiedPhysicalMetadata | None = None,
    ) -> UnverifiedPhysicalDataModel:
        enum_by_container_property = self._create_enum_collections(self._all_containers_by_id.values())
        enum_collection_by_container_property = {
            key: enum_list[0].collection for key, enum_list in enum_by_container_property.items() if enum_list
        }

        properties: list[UnverifiedPhysicalProperty] = []
        for view_id, view in schema.views.items():
            view_entity = ViewEntity.from_id(view_id)
            for prop_id, prop in (view.properties or {}).items():
                dms_property = self._create_dms_property(
                    prop_id, prop, view_entity, enum_collection_by_container_property
                )
                if dms_property is not None:
                    properties.append(dms_property)

        data_model_view_ids: set[dm.ViewId] = {
            view.as_id() if isinstance(view, dm.View | dm.ViewApply) else view for view in data_model.views or []
        }

        metadata = metadata or UnverifiedPhysicalMetadata.from_data_model(data_model)

        return UnverifiedPhysicalDataModel(
            metadata=metadata,
            properties=properties,
            containers=[
                UnverifiedPhysicalContainer.from_container(container) for container in schema.containers.values()
            ],
            views=[
                UnverifiedPhysicalView.from_view(view, in_model=view_id in data_model_view_ids)
                for view_id, view in schema.views.items()
            ],
            nodes=[UnverifiedPhysicalNodeType.from_node_type(node_type) for node_type in schema.node_types.values()],
            enum=[enum for enum_list in enum_by_container_property.values() for enum in enum_list] or None,
        )

    def _create_dms_property(
        self,
        prop_id: str,
        prop: ViewPropertyApply,
        view_entity: ViewEntity,
        enum_collection_by_container_property: dict[tuple[dm.ContainerId, str], str],
    ) -> UnverifiedPhysicalProperty | None:
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

        container_property = (
            self._get_container_property_definition(prop) if isinstance(prop, dm.MappedPropertyApply) else None
        )
        value_type = self._get_value_type(prop, container_property, enum_collection_by_container_property)
        if value_type is None:
            self.issue_list.append(
                PropertyTypeNotSupportedWarning(view_entity.as_id(), "view", prop_id, type(prop).__name__)
            )
            return None
        if isinstance(value_type, ViewEntity) and value_type.as_id() not in self._all_views_by_id:
            self.issue_list.append(ResourceUnknownWarning(prop.source, "view", view_entity.as_id(), "view"))

        return UnverifiedPhysicalProperty(
            description=prop.description,
            name=prop.name,
            connection=self._get_connection_type(prop),
            value_type=str(value_type),
            min_count=self._get_min_count(prop, container_property),
            max_count=self._get_max_count(prop, container_property),
            immutable=self._get_immutable(prop),
            default=self._get_default(prop, container_property),
            container=(
                str(ContainerEntity.from_id(prop.container)) if isinstance(prop, dm.MappedPropertyApply) else None
            ),
            container_property=(
                prop.container_property_identifier if isinstance(prop, dm.MappedPropertyApply) else None
            ),
            view=str(view_entity),
            view_property=prop_id,
            # MyPy fails to understand that list[ContainerIndexEntity] | None is valid even though
            # the index expects str | list[ContainerIndexEntity | str] | None.
            index=self._get_index(prop, prop_id),  # type: ignore[arg-type]
            constraint=self._get_constraint(prop, prop_id),
        )

    def _get_container_property_definition(self, prop: dm.MappedPropertyApply) -> dm.ContainerProperty:
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
            self._get_container_property_definition(prop).type, dm.DirectRelation
        ):
            return "direct"
        else:
            return None

    @classmethod
    def _get_value_type(
        cls,
        prop: ViewPropertyApply | ViewProperty,
        container_property: dm.ContainerProperty | None = None,
        enum_collection_by_container_property: (dict[tuple[dm.ContainerId, str], str] | None) = None,
    ) -> DataType | ViewEntity | PhysicalUnknownEntity | None:
        if isinstance(
            prop,
            SingleEdgeConnectionApply
            | MultiEdgeConnectionApply
            | SingleReverseDirectRelationApply
            | MultiReverseDirectRelationApply
            | SingleEdgeConnection
            | dm.MultiEdgeConnection
            | SingleReverseDirectRelation
            | dm.MultiReverseDirectRelation,
        ):
            return ViewEntity.from_id(prop.source)
        elif isinstance(prop, dm.MappedPropertyApply | dm.MappedProperty):
            if isinstance(prop, dm.MappedPropertyApply):
                if container_property is None:
                    raise ValueError("container property must be provided when prop is a MappedProperty")
                prop_type = container_property.type
            else:
                prop_type = prop.type
            if isinstance(prop_type, dm.DirectRelation):
                if prop.source is None:
                    return PhysicalUnknownEntity()
                else:
                    return ViewEntity.from_id(prop.source)
            elif isinstance(prop_type, PropertyTypeWithUnit) and prop_type.unit:
                return DataType.load(f"{prop_type._type}(unit={prop_type.unit.external_id})")
            elif isinstance(prop_type, dm.Text) and prop_type.max_text_size is not None:
                return DataType.load(f"{prop_type._type}(maxTextSize={prop_type.max_text_size})")
            elif isinstance(prop_type, DMSEnum):
                if enum_collection_by_container_property is None:
                    return String()
                collection = enum_collection_by_container_property.get(
                    (prop.container, prop.container_property_identifier)
                )
                if collection is None:
                    # This should never happen
                    raise ValueError(
                        f"BUG in Neat: Enum for {prop.container}.{prop.container_property_identifier} not found."
                    )

                return Enum(
                    collection=ConceptEntity(suffix=collection),
                    unknownValue=prop_type.unknown_value,
                )
            else:
                return DataType.load(prop_type._type)
        else:
            return None

    @classmethod
    def _get_min_count(
        cls,
        prop: ViewPropertyApply | ViewProperty,
        container_property: dm.ContainerProperty | None = None,
    ) -> int | None:
        if isinstance(prop, dm.MappedPropertyApply):
            if container_property is None:
                raise ValueError("container_property must be provided when prop is a MappedPropertyApply")
            return int(not container_property.nullable)
        elif isinstance(prop, dm.MappedProperty):
            return int(not prop.nullable)
        else:
            return None

    def _get_immutable(self, prop: ViewPropertyApply) -> bool | None:
        if isinstance(prop, dm.MappedPropertyApply):
            return self._get_container_property_definition(prop).immutable
        else:
            return None

    @classmethod
    def _get_max_count(
        cls,
        prop: ViewPropertyApply | ViewProperty,
        container_property: dm.ContainerProperty | None = None,
    ) -> int | float | None:
        if isinstance(prop, dm.MappedPropertyApply | dm.MappedProperty):
            if isinstance(prop, dm.MappedPropertyApply):
                if container_property is None:
                    raise ValueError("get_container must be provided when prop is a MappedPropertyApply")
                prop_type = container_property.type
            else:
                prop_type = prop.type
            if isinstance(prop_type, ListablePropertyType):
                if prop_type.is_list is False:
                    return 1
                elif isinstance(prop_type.max_list_size, int):
                    return prop_type.max_list_size
                elif isinstance(prop_type, DirectRelation):
                    return DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT
                else:
                    return DMS_PRIMITIVE_LIST_DEFAULT_LIMIT
            else:
                return 1
        elif isinstance(
            prop,
            MultiEdgeConnectionApply
            | MultiReverseDirectRelationApply
            | dm.MultiEdgeConnection
            | dm.MultiReverseDirectRelation,
        ):
            return float("inf")
        elif isinstance(
            prop,
            SingleEdgeConnectionApply
            | SingleReverseDirectRelationApply
            | SingleEdgeConnection
            | SingleReverseDirectRelation,
        ):
            return 1
        else:
            warnings.warn(
                NeatValueWarning(f"Unknown property type {type(prop)}. Assuming max count is inf"), stacklevel=2
            )
            return None

    @classmethod
    def _get_default(
        cls,
        prop: ViewPropertyApply | ViewProperty,
        container_property: dm.ContainerProperty | None = None,
    ) -> str | None:
        if isinstance(prop, dm.MappedPropertyApply | dm.MappedProperty):
            if isinstance(prop, dm.MappedPropertyApply):
                if container_property is None:
                    raise ValueError("container_property must be provided when prop is a MappedPropertyApply")
                default = container_property.default_value
            else:
                default = prop.default_value
            if default is not None:
                return str(default)
        return None

    def _get_index(self, prop: ViewPropertyApply, prop_id: str) -> list[ContainerIndexEntity] | None:
        if not isinstance(prop, dm.MappedPropertyApply):
            return None
        container = self._all_containers_by_id[prop.container]
        index: list[ContainerIndexEntity] = []
        for index_name, index_obj in (container.indexes or {}).items():
            if isinstance(index_obj, BTreeIndex) and prop_id in index_obj.properties:
                order = None if len(index_obj.properties) == 1 else index_obj.properties.index(prop_id)
                index.append(
                    ContainerIndexEntity(
                        prefix="btree", suffix=index_name, cursorable=index_obj.cursorable, order=order
                    )
                )
            elif isinstance(index_obj, InvertedIndex) and prop_id in index_obj.properties:
                order = None if len(index_obj.properties) == 1 else index_obj.properties.index(prop_id)
                index.append(ContainerIndexEntity(prefix="inverted", suffix=index_name, order=order))
        return index or None

    def _get_constraint(self, prop: ViewPropertyApply, prop_id: str) -> list[ContainerConstraintEntity] | None:
        if not isinstance(prop, dm.MappedPropertyApply):
            return None
        container = self._all_containers_by_id[prop.container]
        unique_constraints: list[ContainerConstraintEntity] = []
        for constraint_name, constraint_obj in (container.constraints or {}).items():
            if isinstance(constraint_obj, dm.RequiresConstraint):
                # This is handled in the .from_container method of DMSContainer
                continue
            elif isinstance(constraint_obj, dm.UniquenessConstraint) and prop_id in constraint_obj.properties:
                unique_constraints.append(ContainerConstraintEntity(prefix="uniqueness", suffix=constraint_name))
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
    def _create_enum_collections(
        containers: Collection[dm.ContainerApply],
    ) -> dict[tuple[dm.ContainerId, str], list[UnverifiedPhysicalEnum]]:
        enum_by_container_property: dict[tuple[dm.ContainerId, str], list[UnverifiedPhysicalEnum]] = defaultdict(list)

        is_external_id_unique = len({container.external_id for container in containers}) == len(containers)

        for container in containers:
            container_id = container.as_id()
            for prop_id, prop in container.properties.items():
                if not isinstance(prop.type, DMSEnum):
                    continue
                if is_external_id_unique:
                    collection = f"{container.external_id}.{prop_id}"
                else:
                    collection = f"{container.space}:{container.external_id}.{prop_id}"
                for identifier, value in prop.type.values.items():
                    enum_by_container_property[(container_id, prop_id)].append(
                        UnverifiedPhysicalEnum(
                            collection=collection,
                            value=identifier,
                            name=value.name,
                            description=value.description,
                        )
                    )
        return enum_by_container_property

    @classmethod
    def as_unverified_conceptual_property(
        cls, entity: ConceptEntity, prop_id: str, view_property: ViewProperty
    ) -> UnverifiedConceptualProperty:
        if not isinstance(view_property, dm.MappedProperty | dm.EdgeConnection | ReverseDirectRelation):
            raise PropertyTypeNotSupportedError(
                dm.ViewId(str(entity.prefix), str(entity.suffix), entity.version),
                "view",
                prop_id,
                type(view_property).__name__,
            )

        value_type = cls._get_value_type(view_property)
        if value_type is None:
            raise NeatValueError(f"Failed to get value type for {entity} property {prop_id}")

        return UnverifiedConceptualProperty(
            concept=entity,
            property_=prop_id,
            value_type=str(value_type),
            name=view_property.name,
            description=view_property.description,
            min_count=cls._get_min_count(view_property),
            max_count=cls._get_max_count(view_property),
            default=cls._get_default(view_property),
        )

    @classmethod
    def as_unverified_concept(cls, view: View) -> UnverifiedConcept:
        return UnverifiedConcept(
            concept=ConceptEntity(prefix=view.space, suffix=view.external_id, version=view.version),
            name=view.name,
            description=view.description,
            implements=[
                ConceptEntity(
                    prefix=parent.space,
                    suffix=parent.external_id,
                    version=parent.version,
                )
                for parent in view.implements or []
            ]
            or None,
        )
