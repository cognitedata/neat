import inspect
import sys
from abc import ABC, abstractmethod
from functools import total_ordering
from types import UnionType
from typing import Any, ClassVar, Generic, Literal, TypeVar, Union, cast, get_args, get_origin

from cognite.client.data_classes.data_modeling import DirectRelationReference
from cognite.client.data_classes.data_modeling.data_types import UnitReference
from cognite.client.data_classes.data_modeling.ids import (
    ContainerId,
    DataModelId,
    NodeId,
    PropertyId,
    ViewId,
)
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

from cognite.neat._utils.text import replace_non_alphanumeric_with_underscore

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import Self
else:
    from backports.strenum import StrEnum
    from typing_extensions import Self

from cognite.neat._rules._constants import (
    ENTITY_PATTERN,
    SPLIT_ON_COMMA_PATTERN,
    SPLIT_ON_EQUAL_PATTERN,
    EntityTypes,
)

from ._constants import (
    _PARSE,
    Undefined,
    Unknown,
    _UndefinedType,
    _UnknownType,
)


@total_ordering
class Entity(BaseModel, extra="ignore"):
    """Entity is a class or property in OWL/RDF sense."""

    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: str | _UndefinedType = Undefined
    suffix: str

    @classmethod
    def load(cls: "type[T_Entity]", data: Any, **defaults) -> "T_Entity | UnknownEntity":
        if isinstance(data, cls):
            return data
        elif isinstance(data, str) and data == str(Unknown):
            return UnknownEntity(prefix=Undefined, suffix=Unknown)
        if defaults and isinstance(defaults, dict):
            # This is a trick to pass in default values
            return cls.model_validate({_PARSE: data, "defaults": defaults})
        else:
            return cls.model_validate(data)

    @model_validator(mode="before")
    def _load(cls, data: Any) -> "dict | Entity":
        defaults = {}
        if isinstance(data, dict) and _PARSE in data:
            defaults = data.get("defaults", {})
            data = data[_PARSE]
        if isinstance(data, dict):
            data.update(defaults)
            return data
        elif hasattr(data, "versioned_id"):
            # Todo: Remove. Is here for backwards compatibility
            data = data.versioned_id
        elif not isinstance(data, str):
            raise ValueError(f"Cannot load {cls.__name__} from {data}")
        elif data == str(Unknown) and cls.type_ == EntityTypes.undefined:
            return dict(prefix=Undefined, suffix=Unknown)  # type: ignore[arg-type]
        elif data == str(Unknown):
            raise ValueError(f"Unknown is not allowed for {cls.type_} entity")

        result = cls._parse(data, defaults)
        output = defaults.copy()
        # Populate by alias
        for field_name, field_ in cls.model_fields.items():
            name = field_.alias or field_name
            if (field_value := result.get(field_name)) and not (field_value in [Unknown, Undefined] and name in output):
                output[name] = result.pop(field_name)
            elif name not in output and name in result:
                output[name] = result.pop(name)
        return output

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)

    @field_validator("*", mode="before")
    def strip_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        elif isinstance(value, list):
            return [entry.strip() if isinstance(entry, str) else entry for entry in value]
        return value

    @classmethod
    def _parse(cls, raw: str, defaults: dict) -> dict:
        if not (result := ENTITY_PATTERN.match(raw)):
            return dict(prefix=Undefined, suffix=Unknown)
        prefix = result.group("prefix") or Undefined
        suffix = result.group("suffix")
        content = result.group("content")
        if content is None:
            return dict(prefix=prefix, suffix=suffix)
        extra_args = dict(SPLIT_ON_EQUAL_PATTERN.split(pair.strip()) for pair in SPLIT_ON_COMMA_PATTERN.split(content))
        expected_args = {
            field_.alias or field_name: field_.annotation for field_name, field_ in cls.model_fields.items()
        }
        for key in list(extra_args):
            if key not in expected_args:
                # Todo Warning about unknown key
                del extra_args[key]
                continue
            annotation = expected_args[key]
            if isinstance(annotation, UnionType) or get_origin(annotation) is Union:
                annotation = get_args(annotation)[0]

            if inspect.isclass(annotation) and issubclass(annotation, Entity):  # type: ignore[arg-type]
                extra_args[key] = annotation.load(extra_args[key], **defaults)  # type: ignore[union-attr, assignment]
        return dict(prefix=prefix, suffix=suffix, **extra_args)

    def dump(self, **defaults: Any) -> str:
        return self._as_str(**defaults)

    def as_tuple(self) -> tuple[str, ...]:
        # We haver overwritten the serialization to str, so we need to do it manually
        extra: tuple[str, ...] = tuple(
            [
                str(v or "")
                for field_name in self.model_fields
                if isinstance(v := getattr(self, field_name), str | None) and field_name not in {"prefix", "suffix"}
            ]
        )
        if isinstance(self.prefix, _UndefinedType):
            return str(self.suffix), *extra
        else:
            return self.prefix, str(self.suffix), *extra

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.as_tuple() < other.as_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __hash__(self) -> int:
        return hash(str(self))

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        # We have overwritten the serialization to str, so we need to do it manually
        model_dump = ((k, v) for k in self.model_fields if (v := getattr(self, k)) is not None)
        args = ",".join([f"{k}={v}" for k, v in model_dump])
        return f"{self.type_.value}({args})"

    @property
    def id(self) -> str:
        return self._as_str()

    def _as_str(self, **defaults: Any) -> str:
        # We have overwritten the serialization to str, so we need to do it manually
        model_dump = {
            field.alias or field_name: v.dump(**defaults) if isinstance(v, Entity) else v
            for field_name, field in self.model_fields.items()
            if (v := getattr(self, field_name)) is not None and field_name not in {"prefix", "suffix"}
        }
        if isinstance(defaults, dict):
            for key, value in defaults.items():
                if key in model_dump and value == defaults.get(key):
                    del model_dump[key]

        args = ",".join(f"{k}={v}" for k, v in model_dump.items())
        if self.prefix == Undefined or (isinstance(defaults, dict) and self.prefix == defaults.get("prefix")):
            base_id = str(self.suffix)
        else:
            base_id = f"{self.prefix}:{self.suffix!s}"
        if args:
            return f"{base_id}({args})"
        else:
            return base_id

    @property
    def versioned_id(self) -> str:
        # Todo: Remove. Is here for backwards compatibility
        return self.id

    def as_non_versioned_entity(self) -> str:
        # Todo: Remove. Is here for backwards compatibility
        if self.prefix is Undefined:
            return f"{self.suffix!s}"
        return f"{self.prefix}:{self.suffix!s}"

    def as_dms_compliant_entity(self) -> "Self":
        new_entity = self.model_copy(deep=True)
        new_entity.suffix = replace_non_alphanumeric_with_underscore(new_entity.suffix)
        return new_entity


T_Entity = TypeVar("T_Entity", bound=Entity)


class ClassEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.class_
    version: str | None = None

    def as_view_entity(self, default_space: str, default_version) -> "ViewEntity":
        if self.version is None:
            version = default_version
        else:
            version = self.version
        space = default_space if isinstance(self.prefix, _UndefinedType) else self.prefix
        return ViewEntity(space=space, externalId=str(self.suffix), version=version)

    def as_container_entity(self, default_space: str) -> "ContainerEntity":
        space = default_space if isinstance(self.prefix, _UndefinedType) else self.prefix
        return ContainerEntity(space=space, externalId=str(self.suffix))


class UnknownEntity(ClassEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: _UndefinedType = Undefined
    suffix: _UnknownType = Unknown  # type: ignore[assignment]

    @property
    def id(self) -> str:
        return str(Unknown)


class UnitEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.unit
    prefix: str
    suffix: str

    def as_reference(self) -> UnitReference:
        return UnitReference(external_id=f"{self.prefix}:{self.suffix}")


class AssetFields(StrEnum):
    externalId = "externalId"
    name = "name"
    parentExternalId = "parentExternalId"
    description = "description"
    metadata = "metadata"


class AssetEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.asset
    suffix: str = "Asset"
    prefix: _UndefinedType = Undefined
    property_: AssetFields = Field(alias="property")


class RelationshipEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.relationship
    suffix: str = "Relationship"
    prefix: _UndefinedType = Undefined
    label: str | None = None


T_ID = TypeVar("T_ID", bound=ContainerId | ViewId | DataModelId | PropertyId | NodeId | None)


class DMSEntity(Entity, Generic[T_ID], ABC):
    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: str = Field(alias="space")
    suffix: str = Field(alias="externalId")

    def dump(self, **defaults: Any) -> str:
        if isinstance(defaults, dict) and "space" in defaults:
            defaults["prefix"] = defaults.pop("space")
        return super().dump(**defaults)

    @classmethod
    def load(cls: "type[T_DMSEntity]", data: Any, **defaults) -> "T_DMSEntity | DMSUnknownEntity":  # type: ignore[override]
        if isinstance(data, str) and data == str(Unknown):
            return DMSUnknownEntity.from_id(None)
        return cast(T_DMSEntity, super().load(data, **defaults))

    @property
    def space(self) -> str:
        """Returns entity space in CDF."""
        return self.prefix

    @property
    def external_id(self) -> str:
        """Returns entity external id in CDF."""
        return self.suffix

    @abstractmethod
    def as_id(self) -> T_ID:
        raise NotImplementedError("Method as_id must be implemented in subclasses")

    @classmethod
    @abstractmethod
    def from_id(cls, id: T_ID) -> Self:
        raise NotImplementedError("Method from_id must be implemented in subclasses")

    def as_class(self) -> ClassEntity:
        return ClassEntity(prefix=self.space, suffix=self.external_id)

    def as_dms_compliant_entity(self) -> "Self":
        new_entity = self.model_copy(deep=True)
        new_entity.suffix = replace_non_alphanumeric_with_underscore(new_entity.suffix)
        return new_entity


T_DMSEntity = TypeVar("T_DMSEntity", bound=DMSEntity)


class ContainerEntity(DMSEntity[ContainerId]):
    type_: ClassVar[EntityTypes] = EntityTypes.container

    def as_id(self) -> ContainerId:
        return ContainerId(space=self.space, external_id=self.external_id)

    @classmethod
    def from_id(cls, id: ContainerId) -> "ContainerEntity":
        return cls(space=id.space, externalId=id.external_id)


class DMSVersionedEntity(DMSEntity[T_ID], ABC):
    version: str

    def as_class(self, skip_version: bool = False) -> ClassEntity:
        if skip_version:
            return ClassEntity(prefix=self.space, suffix=self.external_id)
        return ClassEntity(prefix=self.space, suffix=self.external_id, version=self.version)


class ViewEntity(DMSVersionedEntity[ViewId]):
    type_: ClassVar[EntityTypes] = EntityTypes.view

    def as_id(
        self,
    ) -> ViewId:
        return ViewId(space=self.space, external_id=self.external_id, version=self.version)

    def to_property_id(self, property_id: str) -> PropertyId:
        return PropertyId(source=self.as_id(), property=property_id)

    @classmethod
    def from_id(cls, id: ViewId, default_version: str | None = None) -> "ViewEntity":
        if id.version is not None:
            return cls(space=id.space, externalId=id.external_id, version=id.version)
        elif default_version is not None:
            return cls(space=id.space, externalId=id.external_id, version=default_version)
        else:
            raise ValueError("Version must be specified")


class DMSUnknownEntity(DMSEntity[None]):
    """This is a special entity that represents an unknown entity.

    The use case is for direct relations where the source is not known."""

    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: _UndefinedType = Field(Undefined, alias="space")  # type: ignore[assignment]
    suffix: _UnknownType = Field(Unknown, alias="externalId")  # type: ignore[assignment]

    def as_id(self) -> None:
        return None

    @classmethod
    def from_id(cls, id: None) -> "DMSUnknownEntity":
        return cls(space=Undefined, externalId=Unknown)

    @property
    def id(self) -> str:
        return str(Unknown)


class DataModelEntity(DMSVersionedEntity[DataModelId]):
    type_: ClassVar[EntityTypes] = EntityTypes.datamodel

    def as_id(self) -> DataModelId:
        return DataModelId(space=self.space, external_id=self.external_id, version=self.version)

    @classmethod
    def from_id(cls, id: DataModelId) -> "DataModelEntity":
        if id.version is None:
            raise ValueError("Version must be specified")
        return cls(space=id.space, externalId=id.external_id, version=id.version)


class DMSNodeEntity(DMSEntity[NodeId]):
    type_: ClassVar[EntityTypes] = EntityTypes.dms_node

    def as_id(self) -> NodeId:
        return NodeId(space=self.space, external_id=self.external_id)

    def as_reference(self) -> DirectRelationReference:
        return DirectRelationReference(space=self.space, external_id=self.external_id)

    @classmethod
    def from_id(cls, id: NodeId) -> "DMSNodeEntity":
        return cls(space=id.space, externalId=id.external_id)

    @classmethod
    def from_reference(cls, ref: DirectRelationReference) -> "DMSNodeEntity":
        return cls(space=ref.space, externalId=ref.external_id)


class EdgeEntity(DMSEntity[None]):
    type_: ClassVar[EntityTypes] = EntityTypes.edge
    prefix: _UndefinedType = Undefined  # type: ignore[assignment]
    suffix: Literal["edge"] = "edge"
    edge_type: DMSNodeEntity | None = Field(None, alias="type")
    properties: ViewEntity | None = None
    direction: Literal["outwards", "inwards"] = "outwards"

    def dump(self, **defaults: Any) -> str:
        # Add default direction
        return super().dump(**defaults, direction="outwards")

    def as_id(self) -> None:
        return None

    @classmethod
    def from_id(cls, id: None) -> Self:
        return cls()


class ReverseConnectionEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.reverse
    prefix: _UndefinedType = Undefined
    suffix: Literal["reverse"] = "reverse"
    property_: str = Field(alias="property")


class ReferenceEntity(ClassEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.reference_entity
    prefix: str
    property_: str | None = Field(None, alias="property")

    @classmethod
    def from_entity(cls, entity: Entity, property_: str) -> "ReferenceEntity":
        if isinstance(entity, ClassEntity):
            return cls(
                prefix=str(entity.prefix),
                suffix=entity.suffix,
                version=entity.version,
                property=property_,
            )
        else:
            return cls(prefix=str(entity.prefix), suffix=entity.suffix, property=property_)

    def as_view_id(self) -> ViewId:
        if isinstance(self.prefix, _UndefinedType) or isinstance(self.suffix, _UnknownType):
            raise ValueError("Prefix is not defined or suffix is unknown")
        return ViewId(space=self.prefix, external_id=self.suffix, version=self.version)

    def as_view_property_id(self) -> PropertyId:
        if self.property_ is None or self.prefix is Undefined or self.suffix is Unknown:
            raise ValueError("Property is not defined or prefix is not defined or suffix is unknown")
        return PropertyId(source=self.as_view_id(), property=self.property_)

    def as_node_id(self) -> NodeId:
        return NodeId(space=self.prefix, external_id=self.suffix)

    def as_node_entity(self) -> DMSNodeEntity:
        return DMSNodeEntity(space=self.prefix, externalId=self.suffix)

    def as_class_entity(self) -> ClassEntity:
        return ClassEntity(prefix=self.prefix, suffix=self.suffix, version=self.version)
