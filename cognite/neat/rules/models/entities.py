import re
import sys
from abc import ABC, abstractmethod
from functools import total_ordering
from typing import Annotated, Any, ClassVar, Generic, TypeVar, cast

from cognite.client.data_classes.data_modeling.ids import ContainerId, DataModelId, NodeId, PropertyId, ViewId
from pydantic import AnyHttpUrl, BaseModel, BeforeValidator, Field, PlainSerializer, model_serializer, model_validator

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import Self
else:
    from backports.strenum import StrEnum
    from typing_extensions import Self


class EntityTypes(StrEnum):
    view_non_versioned = "view_non_versioned"
    subject = "subject"
    predicate = "predicate"
    object = "object"
    class_ = "class"
    parent_class = "parent_class"
    property_ = "property"
    object_property = "ObjectProperty"
    data_property = "DatatypeProperty"
    annotation_property = "AnnotationProperty"
    object_value_type = "object_value_type"
    data_value_type = "data_value_type"  # these are strings, floats, ...
    xsd_value_type = "xsd_value_type"
    dms_value_type = "dms_value_type"
    dms_node = "dms_node"
    view = "view"
    reference_entity = "reference_entity"
    container = "container"
    datamodel = "datamodel"
    undefined = "undefined"


# ALLOWED
_ALLOWED_PATTERN = r"[^a-zA-Z0-9-_.]"

# FOR PARSING STRINGS:
_PREFIX_REGEX = r"[a-zA-Z]+[a-zA-Z0-9-_.]*[a-zA-Z0-9]+"
_SUFFIX_REGEX = r"[a-zA-Z0-9-_.]+[a-zA-Z0-9]|[-_.]*[a-zA-Z0-9]+"
_VERSION_REGEX = r"[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?"
_PROPERTY_REGEX = r"[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]?"
_ENTITY_ID_REGEX = rf"{_PREFIX_REGEX}:({_SUFFIX_REGEX})"
_ENTITY_ID_REGEX_COMPILED = re.compile(rf"^(?P<prefix>{_PREFIX_REGEX}):(?P<suffix>{_SUFFIX_REGEX})$")
_VERSIONED_ENTITY_REGEX_COMPILED = re.compile(
    rf"^(?P<prefix>{_PREFIX_REGEX}):(?P<suffix>{_SUFFIX_REGEX})\(version=(?P<version>{_VERSION_REGEX})\)$"
)
_CLASS_ID_REGEX = rf"(?P<{EntityTypes.class_}>{_ENTITY_ID_REGEX})"
_CLASS_ID_REGEX_COMPILED = re.compile(rf"^{_CLASS_ID_REGEX}$")
_PROPERTY_ID_REGEX = rf"\((?P<{EntityTypes.property_}>{_ENTITY_ID_REGEX})\)"

_ENTITY_PATTERN = re.compile(r"^(?P<prefix>.*?):?(?P<suffix>[^(:]*)(\((?P<content>[^)]+)\))?$")


class _UndefinedType(BaseModel): ...


class _UnknownType(BaseModel):
    def __str__(self) -> str:
        return "#N/A"


# This is a trick to make Undefined and Unknown singletons
Undefined = _UndefinedType()
Unknown = _UnknownType()
_PARSE = object()


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
            # This is trick to pass in default values
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

        result = cls._parse(data)
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

    @classmethod
    def _parse(cls, raw: str) -> dict:
        if not (result := _ENTITY_PATTERN.match(raw)):
            return dict(prefix=Undefined, suffix=Unknown)
        prefix = result.group("prefix") or Undefined
        suffix = result.group("suffix")
        content = result.group("content")
        if content is None:
            return dict(prefix=prefix, suffix=suffix)
        extra_args = dict(pair.strip().split("=") for pair in content.split(","))
        expected_args = {field_.alias or field_name for field_name, field_ in cls.model_fields.items()}
        for key in list(extra_args):
            if key not in expected_args:
                # Todo Warning about unknown key
                del extra_args[key]
        return dict(prefix=prefix, suffix=suffix, **extra_args)

    def dump(self) -> str:
        return str(self)

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
        # We have overwritten the serialization to str, so we need to do it manually
        model_dump = (
            (field.alias or field_name, v)
            for field_name, field in self.model_fields.items()
            if (v := getattr(self, field_name)) is not None and field_name not in {"prefix", "suffix"}
        )
        args = ",".join([f"{k}={v}" for k, v in model_dump])
        if self.prefix is Undefined:
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


class ParentClassEntity(ClassEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.parent_class

    def as_class_entity(self) -> ClassEntity:
        return ClassEntity(prefix=self.prefix, suffix=self.suffix, version=self.version)


class UnknownEntity(ClassEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: _UndefinedType = Undefined
    suffix: _UnknownType = Unknown  # type: ignore[assignment]

    @property
    def id(self) -> str:
        return str(Unknown)


T_ID = TypeVar("T_ID", bound=ContainerId | ViewId | DataModelId | PropertyId | NodeId | None)


class DMSEntity(Entity, Generic[T_ID], ABC):
    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: str = Field(alias="space")
    suffix: str = Field(alias="externalId")

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


class ViewPropertyEntity(DMSVersionedEntity[PropertyId]):
    type_: ClassVar[EntityTypes] = EntityTypes.property_
    property_: str = Field(alias="property")

    def as_id(self) -> PropertyId:
        return PropertyId(source=ViewId(self.space, self.external_id, self.version), property=self.property_)

    def as_view_id(self) -> ViewId:
        return ViewId(space=self.space, external_id=self.external_id, version=self.version)

    @classmethod
    def from_id(cls, id: PropertyId) -> "ViewPropertyEntity":
        if isinstance(id.source, ContainerId):
            raise ValueError("Only view source are supported")
        if id.source.version is None:
            raise ValueError("Version must be specified")
        return cls(
            space=id.source.space, externalId=id.source.external_id, version=id.source.version, property=id.property
        )


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

    @classmethod
    def from_id(cls, id: NodeId) -> "DMSNodeEntity":
        return cls(space=id.space, externalId=id.external_id)


class ReferenceEntity(ClassEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.reference_entity
    prefix: str
    property_: str | None = Field(None, alias="property")

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


def _split_str(v: Any) -> list[str]:
    if isinstance(v, str):
        return v.replace(", ", ",").split(",")
    return v


def _join_str(v: list[ClassEntity]) -> str | None:
    return ",".join([entry.id for entry in v]) if v else None


ParentEntityList = Annotated[
    list[ParentClassEntity],
    BeforeValidator(_split_str),
    PlainSerializer(
        _join_str,
        return_type=str,
        when_used="unless-none",
    ),
]

ContainerEntityList = Annotated[
    list[ContainerEntity],
    BeforeValidator(_split_str),
    PlainSerializer(
        _join_str,
        return_type=str,
        when_used="unless-none",
    ),
]

ViewEntityList = Annotated[
    list[ViewEntity],
    BeforeValidator(_split_str),
    PlainSerializer(
        _join_str,
        return_type=str,
        when_used="unless-none",
    ),
]

URLEntity = Annotated[
    AnyHttpUrl,
    PlainSerializer(lambda v: str(v), return_type=str, when_used="unless-none"),
]
