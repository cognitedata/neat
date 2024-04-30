from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, Literal, Any

from pydantic import BaseModel

from ._dms_architect_rules import DMSRules, DMSView, DMSMetadata, DMSProperty, DMSContainer
from ._base import ExtensionCategory, SchemaCompleteness, SheetList
from cognite.neat.rules.models.entities import ViewEntity, ViewPropertyEntity, ClassEntity, ReferenceEntity, ContainerEntity
from cognite.neat.rules.models.data_types import DataType


@dataclass
class DMSMetadataWrite:
    schema_: Literal["complete", "partial", "extended"]
    space: str
    external_id: str
    creator: str
    version: str
    extension: Literal["addition", "reshape", "rebuild"] = 'addition'
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
            schema_=data.get("schema_"),
            space=data.get("space"),
            external_id=data.get("external_id"),
            creator=data.get("creator"),
            version=data.get("version"),
            extension=data.get("extension", "addition"),
            name=data.get("name"),
            description=data.get("description"),
            created=data.get("created"),
            updated=data.get("updated"),
            default_view_version=data.get("default_view_version")
        )

    def as_read(self) -> DMSMetadata:
        return DMSMetadata(
            schema_=SchemaCompleteness(self.schema_),
            extension=ExtensionCategory(self.extension),
            space=self.space,
            external_id=self.external_id,
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
    def load(cls, data: dict[str, Any] | list[dict[str, Any]] | None) -> "DMSPropertyWrite | list[DMSPropertyWrite] | None":
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = data.get("data") if isinstance(data, dict) else data
            return [loaded for item in items if (loaded := cls.load(item)) is not None]

        _add_alias(data, DMSProperty)
        return cls(
            view=data.get("view"),
            view_property=data.get("view_property"),
            value_type=data.get("value_type"),
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
            constraint=data.get("constraint")
        )

    def as_read(self, default_space, default_version) -> DMSProperty:
        value_type: DataType | ViewPropertyEntity | ViewEntity
        if DataType.is_data_type(self.value_type):
            value_type = DataType.load(self.value_type)
        else:
            try:
                value_type = ViewPropertyEntity.load(self.value_type, space=default_space, version=default_version)
            except ValueError:
                value_type = ViewEntity.load(self.value_type, space=default_space, version=default_version)

        return DMSProperty(
            view=ViewEntity.load(self.view, space=default_space, version=default_version),
            view_property=self.view_property,
            value_type=value_type,
            property_=self.property_ or self.view_property,
            class_=ClassEntity.load(self.class_, prefix=default_space, version=default_version) if self.class_ else None,
            name=self.name,
            description=self.description,
            relation=self.relation,
            nullable=self.nullable,
            is_list=self.is_list,
            default=self.default,
            reference=self.reference,
            container=ContainerEntity.load(self.container, space=default_space, version=default_version) if self.container else None,
            container_property=self.container_property,
            index=self.index,
            constraint=self.constraint,
        )


@dataclass
class DMSContainerWrite:
    container: str
    class_: str | None = None
    name: str | None = None
    description: str | None = None
    reference: str | None = None
    constraint: str | None = None

    @classmethod
    def load(cls, data: dict[str, Any] | list[dict[str, Any]] | None) -> "DMSContainerWrite | None":
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = data.get("data") if isinstance(data, dict) else data
            return [loaded for item in items if (loaded := cls.load(item)) is not None]

        _add_alias(data, DMSContainer)
        return cls(
            container=data.get("container"),
            class_=data.get("class_"),
            name=data.get("name"),
            description=data.get("description"),
            reference=data.get("reference"),
            constraint=data.get("constraint")
        )

    def as_read(self, default_space: str) -> DMSContainer:
        container = ContainerEntity.load(self.container, space=default_space)
        return DMSContainer(
            container=container,
            class_=ClassEntity.load(self.class_, prefix=default_space) if self.class_ else container.as_class(),
            name=self.name,
            description=self.description,
            reference=self.reference,
            constraint=[ContainerEntity.load(constraint.strip(), space=default_space) for constraint in self.constraint.split(",")] if self.constraint else None
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
    def load(cls, data: dict[str, Any] | list[dict[str, Any]] | None) -> "DMSViewWrite | list[DMSViewWrite] | None":
        if data is None:
            return None
        if isinstance(data, list) or (isinstance(data, dict) and isinstance(data.get("data"), list)):
            items = data.get("data") if isinstance(data, dict) else data
            return [loaded for item in items if (loaded := cls.load(item)) is not None]
        _add_alias(data, DMSView)

        return cls(
            view=data.get("view"),
            class_=data.get("class"),
            name=data.get("name"),
            description=data.get("description"),
            implements=data.get("implements"),
            reference=data.get("reference"),
            filter_=data.get("filter_"),
            in_model=data.get("in_model", True)
        )

    def as_read(self, default_space: str, default_version: str) -> DMSView:
        view = ViewEntity.load(self.view, space=default_space, version=default_version)
        return DMSView(
            view=view,
            class_=ClassEntity.load(self.class_, prefix=default_space, version=default_version) if self.class_ else view.as_class(),
            name=self.name,
            description=self.description,
            implements=[ViewEntity.load(implement, space=default_space, version=default_version) for implement in self.implements.split(",")] if self.implements else None,
            reference=self.reference,
            filter_=self.filter_,
            in_model=self.in_model
        )


@dataclass
class DMSRulesWrite:
    metadata: DMSMetadataWrite
    properties: Sequence[DMSPropertyWrite]
    views: Sequence[DMSViewWrite]
    containers: Sequence[DMSContainerWrite] | None = None
    reference: "DMSRulesWrite | DMSRules | None" = None

    @classmethod
    def load(cls, data: dict | None) -> "DMSRulesWrite | None":
        if data is None:
            return None
        _add_alias(data, DMSRules)
        return cls(
            metadata=DMSMetadataWrite.load(data.get("metadata")),
            properties=DMSPropertyWrite.load(data.get("properties")),
            views=DMSViewWrite.load(data.get("views")),
            containers=DMSContainerWrite.load(data.get("containers")),
            reference=DMSRulesWrite.load(data.get("reference"))
        )

    def as_read(self) -> DMSRules:
        default_space = self.metadata.space
        default_version = self.metadata.version
        return DMSRules(
            metadata=self.metadata.as_read(),
            properties=SheetList[DMSProperty](data=[prop.as_read(default_space, default_version) for prop in self.properties]),
            views=SheetList[DMSView](data=[view.as_read(default_space, default_version) for view in self.views]),
            containers=SheetList[DMSContainer](data=[container.as_read(default_space) for container in self.containers or []] or []),
            reference=self.reference.as_read() if isinstance(self.reference, DMSRulesWrite) else self.reference if self.reference else None
        )


def _add_alias(data: dict[str, Any], base_model: type[BaseModel]) -> None:
    for field_name, field_ in base_model.model_fields.items():
        if field_name not in data and field_.alias in data:
            data[field_name] = data[field_.alias]
