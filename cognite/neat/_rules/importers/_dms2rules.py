from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

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
    SingleEdgeConnectionApply,
    SingleReverseDirectRelationApply,
    ViewPropertyApply,
)
from cognite.client.utils import ms_to_datetime

from cognite.neat._client import NeatClient
from cognite.neat._constants import DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT, DMS_PRIMITIVE_LIST_DEFAULT_LIMIT
from cognite.neat._issues import IssueList, MultiValueError, NeatIssue, catch_issues
from cognite.neat._issues.errors import (
    FileTypeUnexpectedError,
    NeatValueError,
    ResourceMissingIdentifierError,
    ResourceRetrievalError,
)
from cognite.neat._issues.warnings import (
    MissingCogniteClientWarning,
    PropertyNotFoundWarning,
    PropertyTypeNotSupportedWarning,
    ResourceNotFoundWarning,
    ResourcesDuplicatedWarning,
    ResourceUnknownWarning,
)
from cognite.neat._rules._shared import ReadRules
from cognite.neat._rules.importers._base import BaseImporter
from cognite.neat._rules.models import (
    DMSInputRules,
    DMSSchema,
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

    """

    def __init__(
        self,
        schema: DMSSchema,
        read_issues: Sequence[NeatIssue] | None = None,
        metadata: DMSInputMetadata | None = None,
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
        """Create a DMSImporter ready to convert the given data model to rules.

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
        # If there were errors during the import, the to_rules will raise them.
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
            raise NeatValueError(f"Unsupported YAML format: {format}")

    def to_rules(self) -> ReadRules[DMSInputRules]:
        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_rules method will return None
            self.issue_list.trigger_warnings()
            raise MultiValueError(self.issue_list.errors)

        if not self.schema.data_model:
            self.issue_list.append(ResourceMissingIdentifierError("data model", type(self.schema).__name__))
            self.issue_list.trigger_warnings()
            raise MultiValueError(self.issue_list.errors)

        model = self.schema.data_model

        user_rules = self._create_rule_components(model, self.schema, self.metadata)

        self.issue_list.trigger_warnings()
        if self.issue_list.has_errors:
            raise MultiValueError(self.issue_list.errors)
        return ReadRules(user_rules, {})

    def _create_rule_components(
        self,
        data_model: dm.DataModelApply,
        schema: DMSSchema,
        metadata: DMSInputMetadata | None = None,
    ) -> DMSInputRules:
        enum_by_container_property = self._create_enum_collections(self._all_containers_by_id.values())
        enum_collection_by_container_property = {
            key: enum_list[0].collection for key, enum_list in enum_by_container_property.items() if enum_list
        }

        properties: list[DMSInputProperty] = []
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

        metadata = metadata or DMSInputMetadata.from_data_model(data_model)

        return DMSInputRules(
            metadata=metadata,
            properties=properties,
            containers=[DMSInputContainer.from_container(container) for container in schema.containers.values()],
            views=[
                DMSInputView.from_view(view, in_model=view_id in data_model_view_ids)
                for view_id, view in schema.views.items()
            ],
            nodes=[DMSInputNode.from_node_type(node_type) for node_type in schema.node_types.values()],
            enum=[enum for enum_list in enum_by_container_property.values() for enum in enum_list] or None,
        )

    def _create_dms_property(
        self,
        prop_id: str,
        prop: ViewPropertyApply,
        view_entity: ViewEntity,
        enum_collection_by_container_property: dict[tuple[dm.ContainerId, str], str],
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

        value_type = self._get_value_type(prop, view_entity, prop_id, enum_collection_by_container_property)
        if value_type is None:
            return None

        return DMSInputProperty(
            description=prop.description,
            name=prop.name,
            connection=self._get_connection_type(prop),
            value_type=str(value_type),
            min_count=self._get_min_count(prop),
            max_count=self._get_max_count(prop),
            immutable=self._get_immutable(prop),
            default=self._get_default(prop),
            container=(
                str(ContainerEntity.from_id(prop.container)) if isinstance(prop, dm.MappedPropertyApply) else None
            ),
            container_property=(
                prop.container_property_identifier if isinstance(prop, dm.MappedPropertyApply) else None
            ),
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
        self,
        prop: ViewPropertyApply,
        view_entity: ViewEntity,
        prop_id: str,
        enum_collection_by_container_property: dict[tuple[dm.ContainerId, str], str],
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
                if prop.source is None:
                    return DMSUnknownEntity()
                elif prop.source not in self._all_views_by_id:
                    self.issue_list.append(ResourceUnknownWarning(prop.source, "view", view_entity.as_id(), "view"))
                    return ViewEntity.from_id(prop.source)
                else:
                    return ViewEntity.from_id(prop.source)
            elif isinstance(container_prop.type, PropertyTypeWithUnit) and container_prop.type.unit:
                return DataType.load(f"{container_prop.type._type}(unit={container_prop.type.unit.external_id})")
            elif isinstance(container_prop.type, DMSEnum):
                collection = enum_collection_by_container_property.get(
                    (prop.container, prop.container_property_identifier)
                )
                if collection is None:
                    # This should never happen
                    raise ValueError(
                        f"BUG in Neat: Enum for {prop.container}.{prop.container_property_identifier} not found."
                    )

                return Enum(collection=ClassEntity(suffix=collection), unknownValue=container_prop.type.unknown_value)
            else:
                return DataType.load(container_prop.type._type)
        else:
            self.issue_list.append(
                PropertyTypeNotSupportedWarning[dm.ViewId](view_entity.as_id(), "view", prop_id, type(prop).__name__)
            )
            return None

    def _get_min_count(self, prop: ViewPropertyApply) -> int | None:
        if isinstance(prop, dm.MappedPropertyApply):
            return int(not self._container_prop_unsafe(prop).nullable)
        else:
            return None

    def _get_immutable(self, prop: ViewPropertyApply) -> bool | None:
        if isinstance(prop, dm.MappedPropertyApply):
            return self._container_prop_unsafe(prop).immutable
        else:
            return None

    def _get_max_count(self, prop: ViewPropertyApply) -> int | float | None:
        if isinstance(prop, dm.MappedPropertyApply):
            prop_type = self._container_prop_unsafe(prop).type
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
        elif isinstance(prop, MultiEdgeConnectionApply | MultiReverseDirectRelationApply):
            return float("inf")
        elif isinstance(prop, SingleEdgeConnectionApply | SingleReverseDirectRelationApply):
            return 1
        else:
            # Unknown type.
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
    def _create_enum_collections(
        containers: Collection[dm.ContainerApply],
    ) -> dict[tuple[dm.ContainerId, str], list[DMSInputEnum]]:
        enum_by_container_property: dict[tuple[dm.ContainerId, str], list[DMSInputEnum]] = defaultdict(list)

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
                        DMSInputEnum(
                            collection=collection, value=identifier, name=value.name, description=value.description
                        )
                    )
        return enum_by_container_property
