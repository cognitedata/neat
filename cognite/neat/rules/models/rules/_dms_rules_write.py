from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast, overload

from pydantic import BaseModel

from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    Unknown,
    ViewEntity,
    ViewPropertyEntity,
)

from ._base import ExtensionCategory, SchemaCompleteness
from ._dms_architect_rules import DMSContainer, DMSMetadata, DMSProperty, DMSRules, DMSView


@dataclass
class DMSMetadataWrite:
    schema_: Literal["complete", "partial", "extended"]
    space: str
    external_id: str
    creator: str
    version: str
    extension: Literal["addition", "reshape", "rebuild"] = "addition"
    name: str | None = None
    description: str | None = None
    created: datetime | str | None = None
    updated: datetime | str | None = None
    default_view_version: str | None = None

    @classmethod
    def load(cls, data: dict[str, Any] | None) -> "DMSMetadataWrite | None":
        if data is None:
            return None
        _add_alias(data, DMSMetadata)
        return cls(
            schema_=data.get("schema_"),  # type: ignore[arg-type]
            space=data.get("space"),  # type: ignore[arg-type]
            external_id=data.get("external_id"),  # type: ignore[arg-type]
            creator=data.get("creator"),  # type: ignore[arg-type]
            version=data.get("version"),  # type: ignore[arg-type]
            extension=data.get("extension", "addition"),
            name=data.get("name"),
            description=data.get("description"),
            created=data.get("created"),
            updated=data.get("updated"),
            default_view_version=data.get("default_view_version"),
        )

    def dump(self) -> dict[str, Any]:
        return dict(
            schema=SchemaCompleteness(self.schema_),
            extension=ExtensionCategory(self.extension),
            space=self.space,
            externalId=self.external_id,
            creator=self.creator,
            version=self.version,
            name=self.name,
            description=self.description,
            created=self.created or datetime.now(),
            updated=self.updated or datetime.now(),
            default_view_version=self.default_view_version or self.version,
        )


@dataclass
class DMSPropertyWrite:
    view: str
    view_property: str | None
    value_type: str
    property_: str | None
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    relation: Literal["direct", "reversedirect", "multiedge"] | None = None
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
    def load(cls, data: dict[str, Any]) -> "DMSPropertyWrite": ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list["DMSPropertyWrite"]: ...

    @classmethod
    def load(
        cls, data: dict[str, Any] | list[dict[str, Any]] | None
    ) -> "DMSPropertyWrite | list[DMSPropertyWrite] | None":
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
            relation=data.get("relation"),
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
            "ViewProperty": self.view_property,
            "Value Type": value_type,
            "Property": self.property_ or self.view_property,
            "Class": ClassEntity.load(self.class_, prefix=default_space, version=default_version)
            if self.class_
            else None,
            "Name": self.name,
            "Description": self.description,
            "Relation": self.relation,
            "Nullable": self.nullable,
            "IsList": self.is_list,
            "Default": self.default,
            "Reference": self.reference,
            "Container": ContainerEntity.load(self.container, space=default_space, version=default_version)
            if self.container
            else None,
            "ContainerProperty": self.container_property,
            "Index": self.index,
            "Constraint": self.constraint,
        }


@dataclass
class DMSContainerWrite:
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
    def load(cls, data: dict[str, Any]) -> "DMSContainerWrite": ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list["DMSContainerWrite"]: ...

    @classmethod
    def load(
        cls, data: dict[str, Any] | list[dict[str, Any]] | None
    ) -> "DMSContainerWrite | list[DMSContainerWrite] | None":
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
        return dict(
            Container=container,
            Class=ClassEntity.load(self.class_, prefix=default_space) if self.class_ else container.as_class(),
            Name=self.name,
            Description=self.description,
            Reference=self.reference,
            Constraint=[
                ContainerEntity.load(constraint.strip(), space=default_space)
                for constraint in self.constraint.split(",")
            ]
            if self.constraint
            else None,
        )


@dataclass
class DMSViewWrite:
    view: str
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    implements: str | None = None
    reference: str | None = None
    filter_: Literal["hasData", "nodeType"] | None = None
    in_model: bool = True

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "DMSViewWrite": ...

    @classmethod
    @overload
    def load(cls, data: list[dict[str, Any]]) -> list["DMSViewWrite"]: ...

    @classmethod
    def load(cls, data: dict[str, Any] | list[dict[str, Any]] | None) -> "DMSViewWrite | list[DMSViewWrite] | None":
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
        return dict(
            View=view,
            Class=ClassEntity.load(self.class_, prefix=default_space, version=default_version)
            if self.class_
            else view.as_class(),
            Name=self.name,
            Description=self.description,
            Implements=[
                ViewEntity.load(implement, space=default_space, version=default_version)
                for implement in self.implements.split(",")
            ]
            if self.implements
            else None,
            Reference=self.reference,
            Filter=self.filter_,
            InModel=self.in_model,
        )


@dataclass
class DMSRulesWrite:
    metadata: DMSMetadataWrite
    properties: Sequence[DMSPropertyWrite]
    views: Sequence[DMSViewWrite]
    containers: Sequence[DMSContainerWrite] | None = None
    reference: "DMSRulesWrite | DMSRules | None" = None

    @classmethod
    @overload
    def load(cls, data: dict[str, Any]) -> "DMSRulesWrite": ...

    @classmethod
    @overload
    def load(cls, data: None) -> None: ...

    @classmethod
    def load(cls, data: dict | None) -> "DMSRulesWrite | None":
        if data is None:
            return None
        _add_alias(data, DMSRules)
        return cls(
            metadata=DMSMetadataWrite.load(data.get("metadata")),  # type: ignore[arg-type]
            properties=DMSPropertyWrite.load(data.get("properties")),  # type: ignore[arg-type]
            views=DMSViewWrite.load(data.get("views")),  # type: ignore[arg-type]
            containers=DMSContainerWrite.load(data.get("containers")) or [],
            reference=DMSRulesWrite.load(data.get("reference")),
        )

    def as_read(self) -> DMSRules:
        return DMSRules.model_validate(self.dump())

    def dump(self) -> dict[str, Any]:
        default_space = self.metadata.space
        default_version = self.metadata.version
        reference: dict[str, Any] | None = None
        if isinstance(self.reference, DMSRulesWrite):
            reference = self.reference.dump()
        elif isinstance(self.reference, DMSRules):
            # We need to load through the DMSRulesWrite to set the correct default space and version
            reference = DMSRulesWrite.load(self.reference.model_dump()).dump()

        return dict(
            Metadata=self.metadata.dump(),
            Properties=[prop.dump(default_space, default_version) for prop in self.properties],
            Views=[view.dump(default_space, default_version) for view in self.views],
            Containers=[container.dump(default_space) for container in self.containers or []] or None,
            Reference=reference,
        )


def _add_alias(data: dict[str, Any], base_model: type[BaseModel]) -> None:
    for field_name, field_ in base_model.model_fields.items():
        if field_name not in data and field_.alias in data:
            data[field_name] = data[field_.alias]
