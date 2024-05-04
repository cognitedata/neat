import re
import sys
from typing import ClassVar

from cognite.client.data_classes.data_modeling import ViewId
from pydantic import BaseModel, ConfigDict, Field
from rdflib import Literal, URIRef

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
    property_ = "property"
    object_property = "ObjectProperty"
    data_property = "DatatypeProperty"
    annotation_property = "AnnotationProperty"
    data_value_type = "data_value_type"
    object_value_type = "object_value_type"
    view = "view"
    container = "container"
    undefined = "undefined"


# ALLOWED
ALLOWED_PATTERN = r"[^a-zA-Z0-9-_.]"

# REGEX expressions
PREFIX_REGEX = r"[a-zA-Z]+[a-zA-Z0-9-_.]*[a-zA-Z0-9]+"
SUFFIX_REGEX = r"[a-zA-Z0-9-_.]+[a-zA-Z0-9]|[-_.]*[a-zA-Z0-9]+"
VERSION_REGEX = r"[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])"

ENTITY_ID_REGEX = rf"{PREFIX_REGEX}:({SUFFIX_REGEX})"
ENTITY_ID_REGEX_COMPILED = re.compile(rf"^(?P<prefix>{PREFIX_REGEX}):(?P<suffix>{SUFFIX_REGEX})$")
VERSIONED_ENTITY_REGEX_COMPILED = re.compile(
    rf"^(?P<prefix>{PREFIX_REGEX}):(?P<suffix>{SUFFIX_REGEX})\(version=(?P<version>{VERSION_REGEX})\)$"
)

CLASS_ID_REGEX = rf"(?P<{EntityTypes.class_}>{ENTITY_ID_REGEX})"
CLASS_ID_REGEX_COMPILED = re.compile(rf"^{CLASS_ID_REGEX}$")

PROPERTY_ID_REGEX = rf"\((?P<{EntityTypes.property_}>{ENTITY_ID_REGEX})\)"
VERSION_ID_REGEX = rf"\(version=(?P<version>{VERSION_REGEX})\)"


class Entity(BaseModel):
    """Entity is a class or property in OWL/RDF sense."""

    model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=True)
    prefix: str
    suffix: str
    type_: EntityTypes = Field(default=EntityTypes.undefined)
    name: str | None = None
    description: str | None = None
    version: str | None = None

    @property
    def id(self) -> str:
        return f"{self.prefix}:{self.suffix}"

    @property
    def versioned_id(self) -> str:
        if self.version:
            return f"{self.prefix}:{self.suffix}(version={self.version})"
        else:
            return self.id

    @property
    def space(self) -> str:
        """Returns entity space in CDF."""
        return self.prefix

    @property
    def external_id(self) -> str:
        """Returns entity external id in CDF."""
        return self.suffix

    def __repr__(self):
        return self.id

    @classmethod
    def from_string(cls, entity_string: str, base_prefix: str | None = None, **kwargs) -> Self:
        if result := VERSIONED_ENTITY_REGEX_COMPILED.match(entity_string):
            return cls(
                prefix=result.group("prefix"),
                suffix=result.group("suffix"),
                name=result.group("suffix"),
                version=result.group("version"),
                **kwargs,
            )
        elif result := ENTITY_ID_REGEX_COMPILED.match(entity_string):
            return cls(
                prefix=result.group("prefix"), suffix=result.group("suffix"), name=result.group("suffix"), **kwargs
            )
        elif base_prefix and re.match(SUFFIX_REGEX, entity_string) and re.match(PREFIX_REGEX, base_prefix):
            return cls(prefix=base_prefix, suffix=entity_string, name=entity_string, **kwargs)
        else:
            raise ValueError(f"{cls.__name__} is expected to be prefix:suffix, got {entity_string}")

    @classmethod
    def from_list(cls, entity_strings: list[str], base_prefix: str | None = None, **kwargs) -> list[Self]:
        return [
            cls.from_string(entity_string=entity_string, base_prefix=base_prefix, **kwargs)
            for entity_string in entity_strings
        ]


class ParentClass(Entity):
    type_: EntityTypes = EntityTypes.class_

    @property
    def view_id(self) -> ViewId:
        return ViewId(space=self.space, external_id=self.external_id, version=self.version)

    @classmethod
    def from_view_id(cls, view_id: ViewId) -> Self:
        return cls(prefix=view_id.space, suffix=view_id.external_id, version=view_id.version)


class ContainerEntity(Entity):
    type_: EntityTypes = EntityTypes.container


class ViewEntity(Entity):
    type_: EntityTypes = EntityTypes.view


class Triple(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, arbitrary_types_allowed=True, strict=False, extra="allow"
    )

    subject: str | URIRef | Entity
    predicate: str | URIRef | Entity
    object: str | URIRef | Literal | Entity | None = None
    optional: bool = Field(
        description="Indicates whether a triple is optional, used when building SPARQL query",
        default=False,
    )

    @classmethod
    def from_rdflib_triple(cls, triple: tuple[URIRef, URIRef, URIRef | Literal]) -> Self:
        return cls(subject=triple[0], predicate=triple[1], object=triple[2])
