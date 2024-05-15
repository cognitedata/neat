from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast, overload

from cognite.neat.rules.models._base import DataModelType, ExtensionCategory, SchemaCompleteness, _add_alias
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    Unknown,
    ViewEntity,
    ViewPropertyEntity,
)

from ._rules import DMSContainer, DMSMetadata, DMSProperty, DMSRules, DMSView


@dataclass
class DMSMetadataInput:
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
    def load(cls, data: dict[str, Any] | None) -> "DMSMetadataInput | None":
        if data is None:
            return None
        _add_alias(data, DMSMetadata)
        return cls(
            schema_=data.get("schema_"),  # type: ignore[arg-type]
            space=data.get("space"),  # type: ignore[arg-type]
            external_id=data.get("external_id"),  # type: ignore[arg-type]
            creator=data.get("creator"),  # type: ignore[arg-type]
            version=data.get("version"),  # type: ignore[arg-type]
            # safeguard from empty cell, i.e. if key provided by value None
            extension=data.get("extension", "addition") or "addition",
            data_model_type=data.get("data_model_type", "solution") or "solution",
            name=data.get("name"),
            description=data.get("description"),
            created=data.get("created"),
            updated=data.get("updated"),
        )

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


@dataclass
class DMSPropertyInput:
    view: str
    view_property: str | None
    value_type: str
    property_: str | None
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    connection: Literal["direct", "edge", "reverse"] | None = None
    nullable: bool | None = None
    is_list: bool | None = None
    default: str | int | dict | None = None
    reference: str | None = None
    container: str | None = None
    container_property: str | None = None
    index: str | list[str] | None = None
    constraint: str | list[str] | None = None

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "DMSPropertyInput": ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list["DMSPropertyInput"]: ...

    @classmethod
    def load(
        cls, data: dict[str, Any] | list[dict[str, Any]] | None
    ) -> "DMSPropertyInput | list[DMSPropertyInput] | None":
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = cast(list[dict[str, Any]], data.get("data") if isinstance(data, dict) else data)
            return [loaded for item in items if (loaded := cls.load(item)) is not None]

        _add_alias(data, DMSProperty)
        return cls(
            view=data.get("view"),  # type: ignore[arg-type]
            view_property=data.get("view_property"),  # type: ignore[arg-type]
            value_type=data.get("value_type"),  # type: ignore[arg-type]
            property_=data.get("property_"),
            class_=data.get("class_"),
            name=data.get("name"),
            description=data.get("description"),
            connection=data.get("connection"),
            nullable=data.get("nullable"),
            is_list=data.get("is_list"),
            default=data.get("default"),
            reference=data.get("reference"),
            container=data.get("container"),
            container_property=data.get("container_property"),
            index=data.get("index"),
            constraint=data.get("constraint"),
        )

    def dump(self, default_space: str, default_version: str) -> dict[str, Any]:
        value_type: DataType | ViewPropertyEntity | ViewEntity | DMSUnknownEntity
        if DataType.is_data_type(self.value_type):
            value_type = DataType.load(self.value_type)
        elif self.value_type == str(Unknown):
            value_type = DMSUnknownEntity()
        else:
            try:
                value_type = ViewPropertyEntity.load(self.value_type, space=default_space, version=default_version)
            except ValueError:
                value_type = ViewEntity.load(self.value_type, space=default_space, version=default_version)

        return {
            "View": ViewEntity.load(self.view, space=default_space, version=default_version),
            "View Property": self.view_property,
            "Value Type": value_type,
            "Property (linage)": self.property_ or self.view_property,
            "Class (linage)": (
                ClassEntity.load(self.class_, prefix=default_space, version=default_version) if self.class_ else None
            ),
            "Name": self.name,
            "Description": self.description,
            "Connection": self.connection,
            "Nullable": self.nullable,
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
class DMSContainerInput:
    container: str
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    reference: str | None = None
    constraint: str | None = None

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "DMSContainerInput": ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list["DMSContainerInput"]: ...

    @classmethod
    def load(
        cls, data: dict[str, Any] | list[dict[str, Any]] | None
    ) -> "DMSContainerInput | list[DMSContainerInput] | None":
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = cast(list[dict[str, Any]], data.get("data") if isinstance(data, dict) else data)
            return [loaded for item in items if (loaded := cls.load(item)) is not None]

        _add_alias(data, DMSContainer)
        return cls(
            container=data.get("container"),  # type: ignore[arg-type]
            class_=data.get("class_"),
            name=data.get("name"),
            description=data.get("description"),
            reference=data.get("reference"),
            constraint=data.get("constraint"),
        )

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


@dataclass
class DMSViewInput:
    view: str
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    implements: str | None = None
    reference: str | None = None
    filter_: Literal["hasData", "nodeType", "rawFilter"] | None = None
    in_model: bool = True

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "DMSViewInput": ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list["DMSViewInput"]: ...

    @classmethod
    def load(cls, data: dict[str, Any] | list[dict[str, Any]] | None) -> "DMSViewInput | list[DMSViewInput] | None":
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = cast(list[dict[str, Any]], data.get("data") if isinstance(data, dict) else data)
            return [loaded for item in items if (loaded := cls.load(item)) is not None]
        _add_alias(data, DMSView)

        return cls(
            view=data.get("view"),  # type: ignore[arg-type]
            class_=data.get("class"),
            name=data.get("name"),
            description=data.get("description"),
            implements=data.get("implements"),
            reference=data.get("reference"),
            filter_=data.get("filter_"),
            in_model=data.get("in_model", True),
        )

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


@dataclass
class DMSRulesInput:
    metadata: DMSMetadataInput
    properties: Sequence[DMSPropertyInput]
    views: Sequence[DMSViewInput]
    containers: Sequence[DMSContainerInput] | None = None
    last: "DMSRulesInput | DMSRules | None" = None
    reference: "DMSRulesInput | DMSRules | None" = None

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "DMSRulesInput": ...

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    def load(cls, data: dict | None) -> "DMSRulesInput | None":
        if data is None:
            return None
        _add_alias(data, DMSRules)
        return cls(
            metadata=DMSMetadataInput.load(data.get("metadata")),  # type: ignore[arg-type]
            properties=DMSPropertyInput.load(data.get("properties")),  # type: ignore[arg-type]
            views=DMSViewInput.load(data.get("views")),  # type: ignore[arg-type]
            containers=DMSContainerInput.load(data.get("containers")) or [],
            last=DMSRulesInput.load(data.get("last")),
            reference=DMSRulesInput.load(data.get("reference")),
        )

    def as_rules(self) -> DMSRules:
        return DMSRules.model_validate(self.dump())

    def dump(self) -> dict[str, Any]:
        default_space = self.metadata.space
        default_version = self.metadata.version
        reference: dict[str, Any] | None = None
        if isinstance(self.reference, DMSRulesInput):
            reference = self.reference.dump()
        elif isinstance(self.reference, DMSRules):
            # We need to load through the DMSRulesInput to set the correct default space and version
            reference = DMSRulesInput.load(self.reference.model_dump()).dump()
        last: dict[str, Any] | None = None
        if isinstance(self.last, DMSRulesInput):
            last = self.last.dump()
        elif isinstance(self.last, DMSRules):
            # We need to load through the DMSRulesInput to set the correct default space and version
            last = DMSRulesInput.load(self.last.model_dump()).dump()

        return dict(
            Metadata=self.metadata.dump(),
            Properties=[prop.dump(default_space, default_version) for prop in self.properties],
            Views=[view.dump(default_space, default_version) for view in self.views],
            Containers=[container.dump(default_space) for container in self.containers or []] or None,
            Last=last,
            Reference=reference,
        )
