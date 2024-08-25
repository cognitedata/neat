import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from cognite.client import data_modeling as dm

from cognite.neat.rules.models._base import DataModelType, ExtensionCategory, SchemaCompleteness, _add_alias
from cognite.neat.rules.models._base_input import InputComponent, InputRules
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    ViewEntity,
    ViewPropertyEntity,
    load_dms_value_type,
)

from ._rules import _DEFAULT_VERSION, DMSContainer, DMSMetadata, DMSProperty, DMSRules, DMSView


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

    def dump(self) -> dict[str, Any]:
        return dict(
            schema=SchemaCompleteness(self.schema_),
            extension=ExtensionCategory(self.extension),
            space=self.space,
            externalId=self.external_id,
            dataModelType=DataModelType(self.data_model_type),
            creator=self.creator,
            version=self.version,
            name=self.name,
            description=self.description,
            created=self.created or datetime.now(),
            updated=self.updated or datetime.now(),
        )

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
class DMSInputProperty(InputComponent[DMSView]):
    view: str
    view_property: str | None
    value_type: str | DataType | ViewPropertyEntity | ViewEntity | DMSUnknownEntity
    property_: str | None
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    connection: Literal["direct", "edge", "reverse"] | None = None
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

    def dump(self, default_space: str, default_version: str) -> dict[str, Any]:
        return {
            "View": ViewEntity.load(self.view, space=default_space, version=default_version),
            "View Property": self.view_property,
            "Value Type": load_dms_value_type(self.value_type, default_space, default_version),
            "Property (linage)": self.property_ or self.view_property,
            "Class (linage)": (
                ClassEntity.load(self.class_ or self.view, prefix=default_space, version=default_version)
                if self.class_ or self.view
                else None
            ),
            "Name": self.name,
            "Description": self.description,
            "Connection": self.connection,
            "Nullable": self.nullable,
            "Immutable": self.immutable,
            "Is List": self.is_list,
            "Default": self.default,
            "Reference": self.reference,
            "Container": (
                ContainerEntity.load(self.container, space=default_space, version=default_version)
                if self.container
                else None
            ),
            "Container Property": self.container_property,
            "Index": self.index,
            "Constraint": self.constraint,
        }


@dataclass
class DMSInputContainer(InputComponent[DMSContainer]):
    container: str
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    reference: str | None = None
    constraint: str | None = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSContainer]:
        return DMSContainer

    def dump(self, default_space: str) -> dict[str, Any]:
        container = ContainerEntity.load(self.container, space=default_space)
        return {
            "Container": container,
            "Class (linage)": (
                ClassEntity.load(self.class_, prefix=default_space) if self.class_ else container.as_class()
            ),
            "Name": self.name,
            "Description": self.description,
            "Reference": self.reference,
            "Constraint": (
                [
                    ContainerEntity.load(constraint.strip(), space=default_space)
                    for constraint in self.constraint.split(",")
                ]
                if self.constraint
                else None
            ),
        }

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

    def dump(self, default_space: str, default_version: str) -> dict[str, Any]:
        view = ViewEntity.load(self.view, space=default_space, version=default_version)
        return {
            "View": view,
            "Class (linage)": (
                ClassEntity.load(self.class_, prefix=default_space, version=default_version)
                if self.class_
                else view.as_class()
            ),
            "Name": self.name,
            "Description": self.description,
            "Implements": (
                [
                    ViewEntity.load(implement, space=default_space, version=default_version)
                    for implement in self.implements.split(",")
                ]
                if self.implements
                else None
            ),
            "Reference": self.reference,
            "Filter": self.filter_,
            "In Model": self.in_model,
        }

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
class DMSInputRules(InputRules[DMSRules]):
    metadata: DMSInputMetadata
    properties: list[DMSInputProperty]
    views: list[DMSInputView]
    containers: list[DMSInputContainer] | None = None
    last: "DMSInputRules | None" = None
    reference: "DMSInputRules | None" = None

    @classmethod
    def _get_verified_cls(cls) -> type[DMSRules]:
        return DMSRules

    def dump(self) -> dict[str, Any]:
        default_space = self.metadata.space
        default_version = self.metadata.version
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

        return dict(
            Metadata=self.metadata.dump(),
            Properties=[prop.dump(default_space, default_version) for prop in self.properties],
            Views=[view.dump(default_space, default_version) for view in self.views],
            Containers=[container.dump(default_space) for container in self.containers or []] or None,
            Last=last,
            Reference=reference,
        )
