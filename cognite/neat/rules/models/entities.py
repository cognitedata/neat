import re
import sys
import threading
from abc import ABC, abstractmethod
from functools import total_ordering
from typing import Any, ClassVar, Generic, TypeVar

from cognite.client.data_classes.data_modeling.ids import ContainerId, DataModelId, PropertyId, ViewId
from pydantic import BaseModel, Field, model_serializer, model_validator

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


class _Undefined(BaseModel):
    ...


class _Unknown(BaseModel):
    def __str__(self) -> str:
        return "#N/A"


# This is a trick to make Undefined and Unknown singletons
Undefined = _Undefined()
Unknown = _Unknown()


@total_ordering
class Entity(BaseModel):
    """Entity is a class or property in OWL/RDF sense."""

    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: str | _Undefined = Undefined
    suffix: str | _Unknown

    @classmethod
    def load(cls, data: Any) -> Self:
        return cls.model_validate(data)

    @model_validator(mode="before")
    def _load(cls, data: Any) -> dict:
        if isinstance(data, cls):
            return data.model_dump()
        elif isinstance(data, dict):
            return data
        elif hasattr(data, "versioned_id"):
            # Todo: Remove. Is here for backwards compatibility
            data = data.versioned_id
        elif not isinstance(data, str):
            raise ValueError(f"Cannot load {cls.__name__} from {data}")

        return cls._parse(data)

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
        if isinstance(self.prefix, _Undefined):
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


class ClassEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.class_
    version: str | None = None


class ParentClassEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.parent_class


T_ID = TypeVar("T_ID", bound=ContainerId | ViewId | DataModelId | PropertyId)


class DMSEntity(Entity, Generic[T_ID], ABC):
    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    default_space_by_thread: ClassVar[dict[threading.Thread, str]] = {}
    suffix: str

    @classmethod
    def set_default_space(cls, space: str) -> None:
        cls.default_space_by_thread[threading.current_thread()] = space

    @property
    def space(self) -> str:
        """Returns entity space in CDF."""
        if isinstance(self.prefix, _Undefined):
            return self.default_space_by_thread.get(threading.current_thread(), "MISSING")
        else:
            return self.prefix

    @property
    def external_id(self) -> str:
        """Returns entity external id in CDF."""
        return self.suffix

    @abstractmethod
    def as_id(self) -> T_ID:
        raise NotImplementedError("Method as_id must be implemented in subclasses")


class ContainerEntity(DMSEntity[ContainerId]):
    type_: ClassVar[EntityTypes] = EntityTypes.container

    def as_id(self) -> ContainerId:
        return ContainerId(space=self.space, external_id=self.external_id)


class DMSVersionedEntity(DMSEntity[T_ID], ABC):
    version: str | None = None
    default_version_by_thread: ClassVar[dict[threading.Thread, str]] = {}

    @property
    def version_with_fallback(self) -> str:
        if self.version is not None:
            return self.version
        return self.default_version_by_thread.get(threading.current_thread(), "MISSING")


class ViewEntity(DMSVersionedEntity[ViewId]):
    type_: ClassVar[EntityTypes] = EntityTypes.view

    def as_id(
        self,
    ) -> ViewId:
        return ViewId(space=self.space, external_id=self.external_id, version=self.version_with_fallback)


class PropertyEntity(DMSVersionedEntity[PropertyId]):
    type_: ClassVar[EntityTypes] = EntityTypes.property_
    property_: str = Field(alias="property")

    def as_id(self) -> PropertyId:
        return PropertyId(
            source=ViewId(self.space, self.external_id, self.version_with_fallback), property=self.property_
        )


class DataModelEntity(DMSVersionedEntity[DataModelId]):
    type_: ClassVar[EntityTypes] = EntityTypes.datamodel

    def as_id(self) -> DataModelId:
        return DataModelId(space=self.space, external_id=self.external_id, version=self.version_with_fallback)


class ReferenceEntity(PropertyEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.reference_entity
