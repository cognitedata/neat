import re
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, overload

import pandas as pd
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import ContainerId, ViewId
from rdflib import Namespace, URIRef

from cognite.neat.v0.core._constants import (
    DEFAULT_NAMESPACE,
    DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT,
)
from cognite.neat.v0.core._data_model._constants import SPLIT_ON_COMMA_PATTERN
from cognite.neat.v0.core._data_model.models._base_unverified import (
    UnverifiedComponent,
    UnverifiedDataModel,
)
from cognite.neat.v0.core._data_model.models.data_types import DataType
from cognite.neat.v0.core._data_model.models.entities import (
    ContainerConstraintEntity,
    ContainerEntity,
    ContainerIndexEntity,
    DMSNodeEntity,
    EdgeEntity,
    PhysicalUnknownEntity,
    ReverseConnectionEntity,
    ViewEntity,
    load_connection,
    load_dms_value_type,
)
from cognite.neat.v0.core._data_model.models.entities._wrapped import DMSFilter
from cognite.neat.v0.core._issues.warnings import DeprecatedWarning
from cognite.neat.v0.core._utils.rdf_ import uri_display_name

from ._verified import (
    _DEFAULT_VERSION,
    PhysicalContainer,
    PhysicalDataModel,
    PhysicalEnum,
    PhysicalMetadata,
    PhysicalNodeType,
    PhysicalProperty,
    PhysicalView,
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@dataclass
class UnverifiedPhysicalMetadata(UnverifiedComponent[PhysicalMetadata]):
    space: str
    external_id: str
    creator: str
    version: str
    name: str | None = None
    description: str | None = None
    created: datetime | str | None = None
    updated: datetime | str | None = None
    conceptual: str | URIRef | None = None
    source_id: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[PhysicalMetadata]:
        return PhysicalMetadata

    def dump(self) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        if self.created is None:
            output["created"] = datetime.now()
        if self.updated is None:
            output["updated"] = datetime.now()
        return output

    @classmethod
    def from_data_model(cls, data_model: dm.DataModelApply) -> "UnverifiedPhysicalMetadata":
        description, creator = cls._get_description_and_creator(data_model.description)
        return cls(
            space=data_model.space,
            name=data_model.name or None,
            description=description,
            external_id=data_model.external_id,
            version=data_model.version,
            creator=",".join(creator),
            created=datetime.now(),
            updated=datetime.now(),
        )

    @classmethod
    def _get_description_and_creator(cls, description_raw: str | None) -> tuple[str | None, list[str]]:
        if description_raw and (description_match := re.search(r"Creator: (.+)", description_raw)):
            creator = description_match.group(1).split(", ")
            description = description_raw.replace(description_match[0], "").strip() or None
        elif description_raw:
            creator = ["MISSING"]
            description = description_raw
        else:
            creator = ["MISSING"]
            description = None
        return description, creator

    def as_data_model_id(self) -> dm.DataModelId:
        return dm.DataModelId(space=self.space, external_id=self.external_id, version=self.version)

    @property
    def identifier(self) -> URIRef:
        """Globally unique identifier for the data model.

        !!! note
            Unlike namespace, the identifier does not end with "/" or "#".

        """
        return DEFAULT_NAMESPACE[f"data-model/unverified/physical/{self.space}/{self.external_id}/{self.version}"]

    @property
    def namespace(self) -> Namespace:
        """Namespace for the data model used for the entities in the data model."""
        return Namespace(f"{self.identifier}/")


@dataclass
class UnverifiedPhysicalProperty(UnverifiedComponent[PhysicalProperty]):
    view: str
    view_property: str | None
    value_type: str | DataType | ViewEntity | PhysicalUnknownEntity
    name: str | None = None
    description: str | None = None
    connection: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | str | None = None
    min_count: int | None = None
    max_count: int | float | None = None
    immutable: bool | None = None
    default: str | int | float | bool | dict | None = None
    container: str | None = None
    container_property: str | None = None
    index: str | list[str | ContainerIndexEntity] | ContainerIndexEntity | None = None
    constraint: str | list[str] | list[ContainerConstraintEntity] | ContainerConstraintEntity | None = None
    neatId: str | URIRef | None = None
    conceptual: str | URIRef | None = None

    @property
    def nullable(self) -> bool | None:
        """Used to indicate whether the property is required or not. Only applies to primitive type."""
        return self.min_count in {0, None}

    @property
    def is_list(self) -> bool | None:
        """Used to indicate whether the property holds single or multiple values (list). "
        "Only applies to primitive types."""
        return self.max_count in {float("inf"), None} or (
            isinstance(self.max_count, int | float) and self.max_count > 1
        )

    @classmethod
    def _get_verified_cls(cls) -> type[PhysicalProperty]:
        return PhysicalProperty

    def dump(self, default_space: str, default_version: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["View"] = ViewEntity.load(
            self.view, space=default_space, version=default_version, return_on_failure=True
        )
        output["Value Type"] = load_dms_value_type(
            self.value_type, default_space, default_version, return_on_failure=True
        )
        output["Connection"] = load_connection(self.connection, default_space, default_version, return_on_failure=True)
        output["Container"] = (
            ContainerEntity.load(self.container, space=default_space, version=default_version, return_on_failure=True)
            if self.container
            else None
        )
        if isinstance(self.index, ContainerIndexEntity) or (isinstance(self.index, str) and "," not in self.index):
            output["Index"] = [ContainerIndexEntity.load(self.index, return_on_failure=True)]
        elif isinstance(self.index, str):
            output["Index"] = [
                ContainerIndexEntity.load(index.strip(), return_on_failure=True)
                for index in SPLIT_ON_COMMA_PATTERN.split(self.index)
                if index.strip()
            ]
        elif isinstance(self.index, list):
            index_list: list[ContainerIndexEntity | PhysicalUnknownEntity] = []
            for index in self.index:
                if isinstance(index, ContainerIndexEntity):
                    index_list.append(index)
                elif isinstance(index, str):
                    index_list.extend(
                        [
                            ContainerIndexEntity.load(idx.strip(), return_on_failure=True)
                            for idx in SPLIT_ON_COMMA_PATTERN.split(index)
                            if idx.strip()
                        ]
                    )
                else:
                    raise TypeError(f"Unexpected type for index: {type(index)}")
            output["Index"] = index_list

            output["Constraint"] = _parse_constraints(self.constraint, default_space)
        return output

    def referenced_view(self, default_space: str, default_version: str) -> ViewEntity:
        return ViewEntity.load(self.view, strict=True, space=default_space, version=default_version)

    def referenced_container(self, default_space: str) -> ContainerEntity | None:
        return ContainerEntity.load(self.container, strict=True, space=default_space) if self.container else None

    @classmethod
    def _load(cls, data: dict[str, Any]) -> Self:
        # For backwards compatability, we need to convert nullable and Is List to min and max count
        for min_count_key, nullable_key in [("Min Count", "Nullable"), ("min_count", "nullable")]:
            if nullable_key in data and min_count_key not in data:
                if isinstance(data[nullable_key], bool | float):
                    data[min_count_key] = 0 if data[nullable_key] else 1
                else:
                    data[min_count_key] = None
                warnings.warn(
                    DeprecatedWarning(f"{nullable_key} column", replacement=f"{min_count_key} column"), stacklevel=2
                )
                data.pop(nullable_key)
                break
        for max_count_key, is_list_key, connection_key in [
            ("Max Count", "Is List", "Connection"),
            ("max_count", "is_list", "connection"),
        ]:
            if is_list_key in data and max_count_key not in data:
                if isinstance(data[is_list_key], bool | float):
                    if not data[is_list_key]:
                        data[max_count_key] = 1
                    elif "direct" in (data.get(connection_key, "") or "") and "edge" not in (
                        data.get(connection_key, "") or ""
                    ):
                        data[max_count_key] = DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT
                    else:
                        # Reverse or edge connection
                        data[max_count_key] = float("inf")
                else:
                    data[max_count_key] = 1
                warnings.warn(
                    DeprecatedWarning(f"{is_list_key} column", replacement=f"{max_count_key} column"), stacklevel=2
                )
                data.pop(is_list_key)
                break
        return super()._load(data)


@dataclass
class UnverifiedPhysicalContainer(UnverifiedComponent[PhysicalContainer]):
    container: str
    name: str | None = None
    description: str | None = None
    constraint: str | list[str] | list[ContainerConstraintEntity] | ContainerConstraintEntity | None = None
    neatId: str | URIRef | None = None
    used_for: Literal["node", "edge", "all"] | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[PhysicalContainer]:
        return PhysicalContainer

    def dump(self, default_space: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["Container"] = self.as_entity_id(default_space, return_on_failure=True)
        output["Constraint"] = _parse_constraints(self.constraint, default_space)
        return output

    @overload
    def as_entity_id(self, default_space: str, return_on_failure: Literal[False] = False) -> ContainerEntity: ...

    @overload
    def as_entity_id(self, default_space: str, return_on_failure: Literal[True]) -> ContainerEntity | str: ...

    def as_entity_id(
        self, default_space: str, return_on_failure: Literal[True, False] = False
    ) -> ContainerEntity | str:
        return ContainerEntity.load(
            self.container, strict=True, space=default_space, return_on_failure=return_on_failure
        )

    @classmethod
    def from_container(cls, container: dm.ContainerApply) -> "UnverifiedPhysicalContainer":
        constraints: list[str] = []
        for constraint_name, constraint_obj in (container.constraints or {}).items():
            if isinstance(constraint_obj, dm.RequiresConstraint):
                constraint = ContainerConstraintEntity(
                    prefix="requires", suffix=constraint_name, require=ContainerEntity.from_id(constraint_obj.require)
                )
                constraints.append(str(constraint))

            # UniquenessConstraint it handled in the properties
        container_entity = ContainerEntity.from_id(container.as_id())
        return cls(
            container=str(container_entity),
            name=container.name or None,
            description=container.description,
            constraint=", ".join(constraints) or None,
            used_for=container.used_for,
        )


@dataclass
class UnverifiedPhysicalView(UnverifiedComponent[PhysicalView]):
    view: str
    name: str | None = None
    description: str | None = None
    implements: str | None = None
    filter_: Literal["hasData", "nodeType", "rawFilter"] | str | None = None
    in_model: bool = True
    neatId: str | URIRef | None = None
    conceptual: str | URIRef | None = None

    def __post_init__(self) -> None:
        if self.in_model is None:
            self.in_model = True

    @classmethod
    def _get_verified_cls(cls) -> type[PhysicalView]:
        return PhysicalView

    def dump(self, default_space: str, default_version: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["View"] = self.as_entity_id(default_space, default_version, return_on_failure=True)
        output["Implements"] = self._load_implements(default_space, default_version, return_on_failure=True)
        return output

    @overload
    def as_entity_id(
        self, default_space: str, default_version: str, return_on_failure: Literal[False] = False
    ) -> ViewEntity: ...

    @overload
    def as_entity_id(
        self, default_space: str, default_version: str, return_on_failure: Literal[True]
    ) -> ViewEntity | str: ...

    def as_entity_id(
        self, default_space: str, default_version: str, return_on_failure: Literal[True, False] = False
    ) -> ViewEntity | str:
        return ViewEntity.load(
            self.view, strict=True, space=default_space, version=default_version, return_on_failure=return_on_failure
        )

    @overload
    def _load_implements(
        self, default_space: str, default_version: str, return_on_failure: Literal[False] = False
    ) -> list[ViewEntity] | None: ...

    @overload
    def _load_implements(
        self, default_space: str, default_version: str, return_on_failure: Literal[True]
    ) -> list[ViewEntity | str] | None: ...

    def _load_implements(
        self, default_space: str, default_version: str, return_on_failure: Literal[True, False] = False
    ) -> list[ViewEntity] | list[ViewEntity | str] | None:
        self.implements = self.implements.strip() if self.implements else None

        return (
            [
                ViewEntity.load(
                    implement,
                    strict=True,
                    space=default_space,
                    version=default_version,
                    return_on_failure=return_on_failure,
                )
                for implement in self.implements.split(",")
            ]
            if self.implements
            else None
        )

    def referenced_views(self, default_space: str, default_version: str) -> list[ViewEntity]:
        return self._load_implements(default_space, default_version) or []

    @classmethod
    def from_view(cls, view: dm.ViewApply, in_model: bool) -> "UnverifiedPhysicalView":
        view_entity = ViewEntity.from_id(view.as_id())

        return cls(
            view=str(view_entity),
            description=view.description,
            name=view.name,
            implements=", ".join([str(ViewEntity.from_id(parent, _DEFAULT_VERSION)) for parent in view.implements])
            or None,
            in_model=in_model,
            filter_=(str(DMSFilter.from_dms_filter(view.filter)) if view.filter else None),
        )


@dataclass
class UnverifiedPhysicalNodeType(UnverifiedComponent[PhysicalNodeType]):
    node: str
    usage: Literal["type", "collocation"]
    name: str | None = None
    description: str | None = None
    neatId: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[PhysicalNodeType]:
        return PhysicalNodeType

    @classmethod
    def from_node_type(cls, node_type: dm.NodeApply) -> "UnverifiedPhysicalNodeType":
        return cls(node=f"{node_type.space}:{node_type.external_id}", usage="type")

    def dump(self, default_space: str, **_) -> dict[str, Any]:  # type: ignore
        output = super().dump()
        output["Node"] = DMSNodeEntity.load(self.node, space=default_space, return_on_failure=True)
        return output


@dataclass
class UnverifiedPhysicalEnum(UnverifiedComponent[PhysicalEnum]):
    collection: str
    value: str
    name: str | None = None
    description: str | None = None
    neatId: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[PhysicalEnum]:
        return PhysicalEnum


@dataclass
class UnverifiedPhysicalDataModel(UnverifiedDataModel[PhysicalDataModel]):
    metadata: UnverifiedPhysicalMetadata
    properties: list[UnverifiedPhysicalProperty]
    views: list[UnverifiedPhysicalView]
    containers: list[UnverifiedPhysicalContainer] | None = None
    enum: list[UnverifiedPhysicalEnum] | None = None
    nodes: list[UnverifiedPhysicalNodeType] | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[PhysicalDataModel]:
        return PhysicalDataModel

    def dump(self) -> dict[str, Any]:
        default_space = self.metadata.space
        default_version = str(self.metadata.version)

        return {
            "Metadata": self.metadata.dump(),
            "Properties": [prop.dump(default_space, default_version) for prop in self.properties],
            "Views": [view.dump(default_space, default_version) for view in self.views],
            "Containers": [container.dump(default_space) for container in self.containers or []] or None,
            "Enum": [enum.dump() for enum in self.enum or []] or None,
            "Nodes": [node_type.dump(default_space) for node_type in self.nodes or []] or None,
        }

    @classmethod
    def display_type_name(cls) -> str:
        return "UnverifiedPhysicalModel"

    @property
    def display_name(self) -> str:
        return uri_display_name(self.metadata.identifier)

    def _repr_html_(self) -> str:
        summary = {
            "type": "Physical Data Model",
            "intended for": "Data Engineer",
            "name": self.metadata.name,
            "space": self.metadata.space,
            "external_id": self.metadata.external_id,
            "version": self.metadata.version,
            "views": len(self.views),
            "containers": len(self.containers) if self.containers else 0,
            "properties": len(self.properties),
        }

        return pd.DataFrame([summary]).T.rename(columns={0: ""})._repr_html_()  # type: ignore

    @property
    def id_(self) -> URIRef:
        return DEFAULT_NAMESPACE[
            f"data-model/unverified/dms/{self.metadata.space}/{self.metadata.external_id}/{self.metadata.version}"
        ]

    def referenced_views_and_containers(self) -> tuple[set[ViewEntity], set[ContainerEntity]]:
        default_space = self.metadata.space
        default_version = self.metadata.version

        containers: set[ContainerEntity] = set()
        views = {parent for view in self.views for parent in view.referenced_views(default_space, default_version)}
        for prop in self.properties:
            views.add(prop.referenced_view(default_space, default_version))
            if ref_container := prop.referenced_container(default_space):
                containers.add(ref_container)

        return views, containers

    def as_view_entities(self) -> list[ViewEntity]:
        return [view.as_entity_id(self.metadata.space, self.metadata.version) for view in self.views]

    def as_container_entities(self) -> list[ContainerEntity]:
        return [container.as_entity_id(self.metadata.space) for container in self.containers or []]

    def imported_views_and_containers(self) -> tuple[set[ViewEntity], set[ContainerEntity]]:
        views, containers = self.referenced_views_and_containers()
        return views - set(self.as_view_entities()), containers - set(self.as_container_entities())

    def imported_views_and_containers_ids(self) -> tuple[set[ViewId], set[ContainerId]]:
        views, containers = self.imported_views_and_containers()
        return {view.as_id() for view in views}, {container.as_id() for container in containers}


def _parse_constraints(
    constraint: str | list[str] | list[ContainerConstraintEntity] | ContainerConstraintEntity | None,
    default_space: str | None = None,
) -> list[ContainerConstraintEntity | PhysicalUnknownEntity] | None:
    """Parse constraint input into a standardized list of ContainerConstraintEntity objects.

    Args:
        constraint: The constraint input in various formats
        default_space: Default space to use when loading constraint entities

    Returns:
        List of parsed constraint entities, or None if no constraints
    """
    if constraint is None:
        return None

    if isinstance(constraint, ContainerConstraintEntity):
        return [constraint]

    if isinstance(constraint, str) and "," not in constraint:
        return [ContainerConstraintEntity.load(constraint, return_on_failure=True, space=default_space)]

    if isinstance(constraint, str):
        return [
            ContainerConstraintEntity.load(constraint_item.strip(), return_on_failure=True, space=default_space)
            for constraint_item in SPLIT_ON_COMMA_PATTERN.split(constraint)
            if constraint_item.strip()
        ]

    if isinstance(constraint, list):
        constraint_list: list[ContainerConstraintEntity | PhysicalUnknownEntity] = []
        for constraint_item in constraint:
            if isinstance(constraint_item, ContainerConstraintEntity):
                constraint_list.append(constraint_item)
            elif isinstance(constraint_item, str):
                constraint_list.extend(
                    [
                        ContainerConstraintEntity.load(idx.strip(), return_on_failure=True, space=default_space)
                        for idx in SPLIT_ON_COMMA_PATTERN.split(constraint_item)
                        if idx.strip()
                    ]
                )
            else:
                raise TypeError(f"Unexpected type for constraint: {type(constraint_item)}")
        return constraint_list

    raise TypeError(f"Unexpected type for constraint: {type(constraint)}")
