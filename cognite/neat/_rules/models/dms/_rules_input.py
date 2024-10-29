import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import pandas as pd
from cognite.client import data_modeling as dm

from cognite.neat._rules.models._base_input import InputComponent, InputRules
from cognite.neat._rules.models.data_types import DataType
from cognite.neat._rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSNodeEntity,
    DMSUnknownEntity,
    EdgeEntity,
    ReverseConnectionEntity,
    ViewEntity,
    load_connection,
    load_dms_value_type,
)

from ._rules import _DEFAULT_VERSION, DMSContainer, DMSEnum, DMSMetadata, DMSNode, DMSProperty, DMSRules, DMSView


@dataclass
class DMSInputMetadata(InputComponent[DMSMetadata]):
    schema_: Literal["complete", "partial", "extended"]
    space: str
    external_id: str
    creator: str
    version: str
    extension: Literal["addition", "reshape", "rebuild"] = "addition"
    data_model_type: Literal["solution", "enterprise"] = "solution"
    name: str | None = None
    description: str | None = None
    created: datetime | str | None = None
    updated: datetime | str | None = None

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
    def from_data_model(cls, data_model: dm.DataModelApply, has_reference: bool) -> "DMSInputMetadata":
        description, creator = cls._get_description_and_creator(data_model.description)
        return cls(
            schema_="complete",
            data_model_type="solution" if has_reference else "enterprise",
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
            description = description_raw.replace(description_match.string, "").strip() or None
        elif description_raw:
            creator = ["MISSING"]
            description = description_raw
        else:
            creator = ["MISSING"]
            description = None
        return description, creator


@dataclass
class DMSInputProperty(InputComponent[DMSProperty]):
    view: str
    view_property: str | None
    value_type: str | DataType | ViewEntity | DMSUnknownEntity
    property_: str | None = None
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    connection: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | str | None = None
    nullable: bool | None = None
    immutable: bool | None = None
    is_list: bool | None = None
    default: str | int | dict | None = None
    reference: str | None = None
    container: str | None = None
    container_property: str | None = None
    index: str | list[str] | None = None
    constraint: str | list[str] | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSProperty]:
        return DMSProperty

    def dump(self, default_space: str, default_version: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        output["View"] = ViewEntity.load(self.view, space=default_space, version=default_version)
        output["Value Type"] = load_dms_value_type(self.value_type, default_space, default_version)
        output["Connection"] = load_connection(self.connection, default_space, default_version)
        output["Property (linage)"] = self.property_ or self.view_property
        output["Class (linage)"] = (
            ClassEntity.load(self.class_ or self.view, prefix=default_space, version=default_version)
            if self.class_ or self.view
            else None
        )
        output["Container"] = (
            ContainerEntity.load(self.container, space=default_space, version=default_version)
            if self.container
            else None
        )
        return output


@dataclass
class DMSInputContainer(InputComponent[DMSContainer]):
    container: str
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    reference: str | None = None
    constraint: str | None = None
    used_for: Literal["node", "edge", "all"] | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSContainer]:
        return DMSContainer

    def dump(self, default_space: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        container = ContainerEntity.load(self.container, space=default_space)
        output["Container"] = container
        output["Class (linage)"] = (
            ClassEntity.load(self.class_, prefix=default_space) if self.class_ else container.as_class()
        )
        output["Constraint"] = (
            [ContainerEntity.load(constraint.strip(), space=default_space) for constraint in self.constraint.split(",")]
            if self.constraint
            else None
        )
        return output

    @classmethod
    def from_container(cls, container: dm.ContainerApply) -> "DMSInputContainer":
        constraints: list[str] = []
        for _, constraint_obj in (container.constraints or {}).items():
            if isinstance(constraint_obj, dm.RequiresConstraint):
                constraints.append(str(ContainerEntity.from_id(constraint_obj.require)))
            # UniquenessConstraint it handled in the properties
        container_entity = ContainerEntity.from_id(container.as_id())
        return cls(
            class_=str(container_entity.as_class()),
            container=str(container_entity),
            name=container.name or None,
            description=container.description,
            constraint=", ".join(constraints) or None,
            used_for=container.used_for,
        )


@dataclass
class DMSInputView(InputComponent[DMSView]):
    view: str
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    implements: str | None = None
    reference: str | None = None
    filter_: Literal["hasData", "nodeType", "rawFilter"] | None = None
    in_model: bool = True

    @classmethod
    def _get_verified_cls(cls) -> type[DMSView]:
        return DMSView

    def dump(self, default_space: str, default_version: str) -> dict[str, Any]:  # type: ignore[override]
        output = super().dump()
        view = ViewEntity.load(self.view, space=default_space, version=default_version)
        output["View"] = view
        output["Class (linage)"] = (
            ClassEntity.load(self.class_, prefix=default_space, version=default_version)
            if self.class_
            else view.as_class()
        )
        output["Implements"] = (
            [
                ViewEntity.load(implement, space=default_space, version=default_version)
                for implement in self.implements.split(",")
            ]
            if self.implements
            else None
        )
        return output

    @classmethod
    def from_view(cls, view: dm.ViewApply, in_model: bool) -> "DMSInputView":
        view_entity = ViewEntity.from_id(view.as_id())
        class_entity = view_entity.as_class(skip_version=True)

        return cls(
            class_=str(class_entity),
            view=str(view_entity),
            description=view.description,
            name=view.name,
            implements=", ".join([str(ViewEntity.from_id(parent, _DEFAULT_VERSION)) for parent in view.implements])
            or None,
            in_model=in_model,
        )


@dataclass
class DMSInputNode(InputComponent[DMSNode]):
    node: str
    usage: Literal["type", "collocation"]
    name: str | None = None
    description: str | None = None

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
    last: "DMSInputRules | None" = None
    reference: "DMSInputRules | None" = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSRules]:
        return DMSRules

    def dump(self) -> dict[str, Any]:
        default_space = self.metadata.space
        default_version = str(self.metadata.version)
        reference: dict[str, Any] | None = None
        if isinstance(self.reference, DMSInputRules):
            reference = self.reference.dump()
        elif isinstance(self.reference, DMSRules):
            # We need to load through the DMSRulesInput to set the correct default space and version
            reference = DMSInputRules.load(self.reference.model_dump()).dump()
        last: dict[str, Any] | None = None
        if isinstance(self.last, DMSInputRules):
            last = self.last.dump()
        elif isinstance(self.last, DMSRules):
            # We need to load through the DMSRulesInput to set the correct default space and version
            last = DMSInputRules.load(self.last.model_dump()).dump()

        return {
            "Metadata": self.metadata.dump(),
            "Properties": [prop.dump(default_space, default_version) for prop in self.properties],
            "Views": [view.dump(default_space, default_version) for view in self.views],
            "Containers": [container.dump(default_space) for container in self.containers or []] or None,
            "Enum": [enum.dump() for enum in self.enum or []] or None,
            "Nodes": [node_type.dump(default_space) for node_type in self.nodes or []] or None,
            "Last": last,
            "Reference": reference,
        }

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
