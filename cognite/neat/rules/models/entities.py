import re
import sys
from functools import total_ordering
from typing import Any, ClassVar, cast

from cognite.client.data_classes.data_modeling.ids import ContainerId, DataModelId, ViewId
from pydantic import BaseModel

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
    view_prop = "view_prop"
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
        elif not isinstance(data, str):
            raise ValueError(f"Cannot load {cls.__name__} from {data}")

        if result := _ENTITY_ID_REGEX_COMPILED.match(data):
            return cls(prefix=result.group("prefix"), suffix=result.group("suffix"))
        elif data == str(Unknown):
            return cls(prefix=Undefined, suffix=Unknown)
        else:
            return cls(prefix=Undefined, suffix=data)

    def dump(self) -> str:
        return str(self)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return str(self) < str(other)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return f"{self.type_.value}(prefix={self.prefix}, suffix={self.suffix})"

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


class ViewNonVersionedEntity(DMSEntity):
    _type = EntityTypes.view_non_versioned

    def as_id(self) -> ViewId:
        return ViewId(space=self.space, external_id=self.external_id)


class DMSVersionedEntity(DMSEntity):
    version: str | None = None

    def __str__(self) -> str:
        if self.version is None:
            return self.id
        return f"{self.id}(version={self.version})"

    @classmethod
    def load(cls, data: Any) -> Self:
        if isinstance(data, str) and (result := _VERSIONED_ENTITY_REGEX_COMPILED.match(data)):
            return cls(prefix=result.group("prefix"), suffix=result.group("suffix"), version=result.group("version"))
        return super().load(data)


class ViewEntity(DMSVersionedEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.view

    def as_id(
        self,
    ) -> ViewId:
        return ViewId(space=self.space, external_id=self.external_id, version=self.version)


class ViewPropEntity(DMSVersionedEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.view_prop
    property_: str

    @classmethod
    def load(cls, data: Any) -> Self:
        raise NotImplementedError()
        # if isinstance(data, str) and (result := _PROPERTY_ID_REGEX.match(data)):
        #     return cls(


class DataModelEntity(DMSVersionedEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.datamodel

    def as_id(self) -> DataModelId:
        return DataModelId(space=self.space, external_id=self.external_id, version=self.version)


class ReferenceEntity(ViewPropEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.reference_entity
