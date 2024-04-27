import re
import sys
from functools import total_ordering
from typing import Any, ClassVar, cast

from cognite.client.data_classes.data_modeling.ids import ContainerId, DataModelId, ViewId
from pydantic import BaseModel, Field

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
        if isinstance(data, cls):
            return data
        elif isinstance(data, dict):
            return cls.model_validate(data)
        elif not isinstance(data, str):
            raise ValueError(f"Cannot load {cls.__name__} from {data}")

        return cls._parse(data)

    @classmethod
    def _parse(cls, raw: str) -> Self:
        if not (result := _ENTITY_PATTERN.match(raw)):
            return cls(prefix=Undefined, suffix=Unknown)
        prefix = result.group("prefix") or Undefined
        suffix = result.group("suffix")
        content = result.group("content")
        if content is None:
            return cls(prefix=prefix, suffix=suffix)
        extra_args = dict(pair.strip().split("=") for pair in content.split(","))
        expected_args = {field_.alias or field_name for field_name, field_ in cls.model_fields.items()}
        for key in list(extra_args):
            if key not in expected_args:
                # Todo Warning about unknown key
                del extra_args[key]
        return cls(prefix=prefix, suffix=suffix, **extra_args)

    def dump(self) -> str:
        return str(self)

    def as_tuple(self) -> tuple[str, ...]:
        extra: tuple[str, ...] = tuple(
            [v if isinstance(v, str) else str(v or "") for v in self.model_dump().items() if isinstance(v, str | None)]
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
        args = ",".join([f"{k}={v}" for k, v in self.model_dump(exclude_none=True).items()])
        return f"{self.type_.value}({args})"

    @property
    def id(self) -> str:
        if self.prefix is Undefined:
            return str(self.suffix)
        else:
            return f"{self.prefix}:{self.suffix!s}"


class ClassEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.class_


class ParentClassEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.parent_class


class DMSEntity(Entity):
    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    suffix: str

    @property
    def space(self) -> str:
        """Returns entity space in CDF."""
        if self.prefix is Undefined:
            raise NotImplementedError()
            # if default_space is None:
        else:
            return cast(str, self.prefix)

    @property
    def external_id(self) -> str:
        """Returns entity external id in CDF."""
        return self.suffix


class ContainerEntity(DMSEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.container

    def as_id(self) -> ContainerId:
        return ContainerId(space=self.space, external_id=self.external_id)


class DMSVersionedEntity(DMSEntity):
    version: str | None = None


class ViewEntity(DMSVersionedEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.view

    def as_id(
        self,
    ) -> ViewId:
        return ViewId(space=self.space, external_id=self.external_id, version=self.version)


class PropertyEntity(DMSVersionedEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.property_
    property_: str = Field(alias="property")


class DataModelEntity(DMSVersionedEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.datamodel

    def as_id(self) -> DataModelId:
        return DataModelId(space=self.space, external_id=self.external_id, version=self.version)


class ReferenceEntity(PropertyEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.reference_entity
