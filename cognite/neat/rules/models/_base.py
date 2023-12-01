import re
import sys
from typing import ClassVar

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
    object_property = "object_property"
    data_property = "data_property"
    data_value_type = "data_value_type"
    object_value_type = "object_value_type"
    annotation_property = "annotation_property"
    view = "view"
    container = "container"


# REGEX expressions
PREFIX_REGEX = r"[a-zA-Z]+[a-zA-Z0-9]*[-_.]*[a-zA-Z0-9]+"
SUFFIX_REGEX = r"[a-zA-Z0-9-_.]+[a-zA-Z0-9]|[-_.]*[a-zA-Z0-9]+"


ENTITY_ID_REGEX = rf"{PREFIX_REGEX}:({SUFFIX_REGEX})"
ENTITY_ID_REGEX_COMPILED = re.compile(rf"^(?P<prefix>{PREFIX_REGEX}):(?P<suffix>{SUFFIX_REGEX})$")

CLASS_ID_REGEX = rf"(?P<{EntityTypes.class_}>{ENTITY_ID_REGEX})"
CLASS_ID_REGEX_COMPILED = re.compile(rf"^{CLASS_ID_REGEX}$")

PROPERTY_ID_REGEX = rf"\((?P<{EntityTypes.property_}>{ENTITY_ID_REGEX})\)"


class Entity(BaseModel):
    """Entity is a class or property in OWL/RDF sense."""

    prefix: str
    suffix: str
    name: str | None = None
    description: str | None = None
    type_: EntityTypes | None = None
    version: str | None = None

    @property
    def id(self) -> str:
        return f"{self.prefix}:{self.suffix}"

    def __repr__(self):
        return self.id

    @classmethod
    def from_string(cls, entity_string: str, base_prefix: str | None = None, **kwargs) -> Self:
        if result := ENTITY_ID_REGEX_COMPILED.match(entity_string):
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
