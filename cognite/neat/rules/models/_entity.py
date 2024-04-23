import re
import sys
from functools import total_ordering
from typing import ClassVar

from pydantic import BaseModel

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import Self
else:
    from backports.strenum import StrEnum
    from typing_extensions import Self


class EntityTypes(StrEnum):
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
ALLOWED_PATTERN = r"[^a-zA-Z0-9-_.]"

# FOR PARSING STRINGS:
PREFIX_REGEX = r"[a-zA-Z]+[a-zA-Z0-9-_.]*[a-zA-Z0-9]+"
SUFFIX_REGEX = r"[a-zA-Z0-9-_.]+[a-zA-Z0-9]|[-_.]*[a-zA-Z0-9]+"
VERSION_REGEX = r"[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?"
PROPERTY_REGEX = r"[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]?"
ENTITY_ID_REGEX = rf"{PREFIX_REGEX}:({SUFFIX_REGEX})"
ENTITY_ID_REGEX_COMPILED = re.compile(rf"^(?P<prefix>{PREFIX_REGEX}):(?P<suffix>{SUFFIX_REGEX})$")
VERSIONED_ENTITY_REGEX_COMPILED = re.compile(
    rf"^(?P<prefix>{PREFIX_REGEX}):(?P<suffix>{SUFFIX_REGEX})\(version=(?P<version>{VERSION_REGEX})\)$"
)
CLASS_ID_REGEX = rf"(?P<{EntityTypes.class_}>{ENTITY_ID_REGEX})"
CLASS_ID_REGEX_COMPILED = re.compile(rf"^{CLASS_ID_REGEX}$")
PROPERTY_ID_REGEX = rf"\((?P<{EntityTypes.property_}>{ENTITY_ID_REGEX})\)"

Undefined = type(object())
Unknown = type(object())


# mypy does not like the sentinel value, and it is not possible to ignore only the line with it below.
# so we ignore all errors beyond this point.
# mypy: ignore-errors
@total_ordering
class Entity(BaseModel, arbitrary_types_allowed=True):
    """Entity is a class or property in OWL/RDF sense."""

    type_: ClassVar[EntityTypes] = EntityTypes.undefined
    prefix: str | Undefined = Undefined
    suffix: str | Unknown
    version: str | None = None
    name: str | None = None
    description: str | None = None

    def __lt__(self, other: object) -> bool:
        if type(self) is not type(other) or not isinstance(other, Entity):
            return NotImplemented
        return self.versioned_id < other.versioned_id

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other) or not isinstance(other, Entity):
            return NotImplemented
        return self.versioned_id == other.versioned_id

    def __hash__(self) -> int:
        return hash(self.versioned_id)

    def as_non_versioned_entity(self) -> Self:
        return self.from_string(f"{self.prefix}:{self.suffix}")

    @property
    def id(self) -> str:
        if self.suffix is Unknown:
            return "#N/A"
        elif self.prefix is Undefined:
            return self.suffix
        else:
            return f"{self.prefix}:{self.suffix}"

    @property
    def versioned_id(self) -> str:
        if self.version is None:
            return self.id
        else:
            return f"{self.id}(version={self.version})"

    @property
    def space(self) -> str:
        """Returns entity space in CDF."""
        return self.prefix

    @property
    def external_id(self) -> str:
        """Returns entity external id in CDF."""
        return self.suffix

    def __repr__(self):
        return self.versioned_id

    def __str__(self):
        return self.versioned_id

    @classmethod
    def from_string(cls, entity_string: str, base_prefix: str | None = None) -> Self:
        if entity_string == "#N/A":
            return cls(prefix=Undefined, suffix=Unknown)
        elif result := VERSIONED_ENTITY_REGEX_COMPILED.match(entity_string):
            return cls(
                prefix=result.group("prefix"),
                suffix=result.group("suffix"),
                version=result.group("version"),
            )
        elif result := ENTITY_ID_REGEX_COMPILED.match(entity_string):
            return cls(prefix=result.group("prefix"), suffix=result.group("suffix"))
        elif base_prefix and re.match(SUFFIX_REGEX, entity_string) and re.match(PREFIX_REGEX, base_prefix):
            return cls(prefix=base_prefix, suffix=entity_string)
        else:
            raise ValueError(f"{cls.__name__} is expected to be prefix:suffix, got {entity_string}")

    @classmethod
    def from_list(cls, entity_strings: list[str], base_prefix: str | None = None) -> list[Self]:
        return [
            cls.from_string(entity_string=entity_string, base_prefix=base_prefix) for entity_string in entity_strings
        ]
