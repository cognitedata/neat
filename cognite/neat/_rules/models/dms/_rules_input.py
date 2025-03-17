import re
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import pandas as pd
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import ContainerId, ViewId
from rdflib import Namespace, URIRef

from cognite.neat._constants import DEFAULT_NAMESPACE, DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT
from cognite.neat._issues.warnings import DeprecatedWarning
from cognite.neat._rules.models._base_input import InputComponent, InputRules
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import (
    ContainerEntity,
    DMSNodeEntity,
    DMSUnknownEntity,
    EdgeEntity,
    ReverseConnectionEntity,
    ViewEntity,
    load_connection,
    load_dms_value_type,
)
from cognite.neat._rules.models.entities._wrapped import DMSFilter
from cognite.neat._utils.rdf_ import uri_display_name

from ._rules import _DEFAULT_VERSION, DMSContainer, DMSEnum, DMSMetadata, DMSNode, DMSProperty, DMSRules, DMSView

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@dataclass
class DMSInputMetadata(InputComponent[DMSMetadata]):
    space: str
    external_id: str
    creator: str
    version: str
    name: str | None = None
    description: str | None = None
    created: datetime | str | None = None
    updated: datetime | str | None = None
    logical: str | URIRef | None = None
    source_id: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSMetadata]:
        return DMSMetadata

    def dump(self) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        if self.created is None:
            output["created"] = datetime.now()
        if self.updated is None:
            output["updated"] = datetime.now()
        return output

    @classmethod
    def from_data_model(cls, data_model: dm.DataModelApply) -> "DMSInputMetadata":
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
class DMSInputProperty(InputComponent[DMSProperty]):
    view: str
    view_property: str | None
    value_type: str | DataType | ViewEntity | DMSUnknownEntity
    name: str | None = None
    description: str | None = None
    connection: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | str | None = None
    min_count: int | None = None
    max_count: int | float | None = None
    immutable: bool | None = None
    default: str | int | float | bool | dict | None = None
    container: str | None = None
    container_property: str | None = None
    index: str | list[str] | None = None
    constraint: str | list[str] | None = None
    neatId: str | URIRef | None = None
    logical: str | URIRef | None = None

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
    def _get_verified_cls(cls) -> type[DMSProperty]:
        return DMSProperty

    def dump(self, default_space: str, default_version: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["View"] = ViewEntity.load(self.view, space=default_space, version=default_version)
        output["Value Type"] = load_dms_value_type(self.value_type, default_space, default_version)
        output["Connection"] = load_connection(self.connection, default_space, default_version)
        output["Container"] = (
            ContainerEntity.load(self.container, space=default_space, version=default_version)
            if self.container
            else None
        )
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
class DMSInputContainer(InputComponent[DMSContainer]):
    container: str
    name: str | None = None
    description: str | None = None
    constraint: str | None = None
    neatId: str | URIRef | None = None
    used_for: Literal["node", "edge", "all"] | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSContainer]:
        return DMSContainer

    def dump(self, default_space: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["Container"] = self.as_entity_id(default_space)
        output["Constraint"] = (
            [ContainerEntity.load(constraint.strip(), space=default_space) for constraint in self.constraint.split(",")]
            if self.constraint
            else None
        )
        return output

    def as_entity_id(self, default_space: str) -> ContainerEntity:
        return ContainerEntity.load(self.container, strict=True, space=default_space)

    @classmethod
    def from_container(cls, container: dm.ContainerApply) -> "DMSInputContainer":
        constraints: list[str] = []
        for _, constraint_obj in (container.constraints or {}).items():
            if isinstance(constraint_obj, dm.RequiresConstraint):
                constraints.append(str(ContainerEntity.from_id(constraint_obj.require)))
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
class DMSInputView(InputComponent[DMSView]):
    view: str
    name: str | None = None
    description: str | None = None
    implements: str | None = None
    filter_: Literal["hasData", "nodeType", "rawFilter"] | str | None = None
    in_model: bool = True
    neatId: str | URIRef | None = None
    logical: str | URIRef | None = None

    def __post_init__(self):
        if self.in_model is None:
            self.in_model = True

    @classmethod
    def _get_verified_cls(cls) -> type[DMSView]:
        return DMSView

    def dump(self, default_space: str, default_version: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["View"] = self.as_entity_id(default_space, default_version)
        output["Implements"] = self._load_implements(default_space, default_version)
        return output

    def as_entity_id(self, default_space: str, default_version: str) -> ViewEntity:
        return ViewEntity.load(self.view, strict=True, space=default_space, version=default_version)

    def _load_implements(self, default_space: str, default_version: str) -> list[ViewEntity] | None:
        self.implements = self.implements.strip() if self.implements else None

        return (
            [
                ViewEntity.load(implement, strict=True, space=default_space, version=default_version)
                for implement in self.implements.split(",")
            ]
            if self.implements
            else None
        )

    def referenced_views(self, default_space: str, default_version: str) -> list[ViewEntity]:
        return self._load_implements(default_space, default_version) or []

    @classmethod
    def from_view(cls, view: dm.ViewApply, in_model: bool) -> "DMSInputView":
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
class DMSInputNode(InputComponent[DMSNode]):
    node: str
    usage: Literal["type", "collocation"]
    name: str | None = None
    description: str | None = None
    neatId: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSNode]:
        return DMSNode

    @classmethod
    def from_node_type(cls, node_type: dm.NodeApply) -> "DMSInputNode":
        return cls(node=f"{node_type.space}:{node_type.external_id}", usage="type")

    def dump(self, default_space: str, **_) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["Node"] = DMSNodeEntity.load(self.node, space=default_space)
        return output


@dataclass
class DMSInputEnum(InputComponent[DMSEnum]):
    collection: str
    value: str
    name: str | None = None
    description: str | None = None
    neatId: str | URIRef | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSEnum]:
        return DMSEnum


@dataclass
class DMSInputRules(InputRules[DMSRules]):
    metadata: DMSInputMetadata
    properties: list[DMSInputProperty]
    views: list[DMSInputView]
    containers: list[DMSInputContainer] | None = None
    enum: list[DMSInputEnum] | None = None
    nodes: list[DMSInputNode] | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSRules]:
        return DMSRules

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
        return "UnverifiedDMSModel"

    @property
    def display_name(self):
        return uri_display_name(self.metadata.identifier)

    def _repr_html_(self) -> str:
        summary = {
            "type": "Physical Data Model",
            "intended for": "DMS Architect",
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
