""" """

import re
import sys
from collections import Counter
from functools import total_ordering
from typing import ClassVar, Literal

from pydantic import BaseModel, field_validator, model_serializer

from cognite.neat._issues.errors import NeatValueError

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import Self
else:
    from backports.strenum import StrEnum
    from typing_extensions import Self


class TransformationRuleType(StrEnum):
    rdfpath = "rdfpath"
    rawlookup = "rawlookup"
    sparql = "sparql"


class Lookup(StrEnum):
    table = "table"
    key = "key"
    value = "value"  # type: ignore


class EntityTypes(StrEnum):
    class_ = "class"
    property_ = "property"
    undefined = "undefined"


# FOR PARSING STRINGS:
PREFIX_REGEX = r"[a-zA-Z]+[a-zA-Z0-9-_.]*[a-zA-Z0-9]+"
SUFFIX_REGEX = r"[a-zA-Z0-9-_.]+[a-zA-Z0-9]|[-_.]*[a-zA-Z0-9]+"
VERSION_REGEX = r"[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?"

ENTITY_ID_REGEX = rf"{PREFIX_REGEX}:({SUFFIX_REGEX})"
ENTITY_ID_REGEX_COMPILED = re.compile(rf"^(?P<prefix>{PREFIX_REGEX}):(?P<suffix>{SUFFIX_REGEX})$")
VERSIONED_ENTITY_REGEX_COMPILED = re.compile(
    rf"^(?P<prefix>{PREFIX_REGEX}):(?P<suffix>{SUFFIX_REGEX})\(version=(?P<version>{VERSION_REGEX})\)$"
)
CLASS_ID_REGEX = rf"(?P<{EntityTypes.class_}>{ENTITY_ID_REGEX})"
CLASS_ID_REGEX_COMPILED = re.compile(rf"^{CLASS_ID_REGEX}$")
PROPERTY_ID_REGEX = rf"\((?P<{EntityTypes.property_}>{ENTITY_ID_REGEX})\)"

# traversal direction
DIRECTION_REGEX = r"(?P<direction>(->|<-))"

# steps
STEP_REGEX = rf"((->|<-){CLASS_ID_REGEX}({PROPERTY_ID_REGEX})?)"
STEP_REGEX_COMPILED = re.compile(STEP_REGEX)
STEP_CLASS_REGEX_COMPILED = re.compile(rf"(^{DIRECTION_REGEX}{CLASS_ID_REGEX})$")
STEP_CLASS_AND_PROPERTY_REGEX_COMPILED = re.compile(rf"(^{DIRECTION_REGEX}{CLASS_ID_REGEX}{PROPERTY_ID_REGEX}$)")


_traversal = "traversal"
ORIGIN_REGEX = rf"(?P<origin>{ENTITY_ID_REGEX})"

HOP_REGEX_COMPILED = re.compile(rf"^{ORIGIN_REGEX}(?P<{_traversal}>{STEP_REGEX}+)$")

# grabbing specific property for a class, property can be either object, annotation or data property
SINGLE_PROPERTY_REGEX_COMPILED = re.compile(rf"^{CLASS_ID_REGEX}{PROPERTY_ID_REGEX}$")

# grabbing all properties for a class
ALL_PROPERTIES_REGEX_COMPILED = re.compile(rf"^{CLASS_ID_REGEX}\(\*\)$")

ALL_TRAVERSAL_REGEX_COMPILED = (
    rf"({CLASS_ID_REGEX}\(\*\)|{CLASS_ID_REGEX}{PROPERTY_ID_REGEX}|{ORIGIN_REGEX}(?P<{_traversal}>{STEP_REGEX}+))"
)

TABLE_REGEX_COMPILED = re.compile(
    rf"^(?P<{Lookup.table}>{SUFFIX_REGEX})\((?P<{Lookup.key}>{SUFFIX_REGEX}),\s*(?P<{Lookup.value}>{SUFFIX_REGEX})\)$"
)


StepDirection = Literal["source", "target", "origin"]
_direction_by_symbol: dict[str, StepDirection] = {"->": "target", "<-": "source"}
_symbol_by_direction: dict[StepDirection, str] = {"source": "<-", "target": "->"}

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


class Step(BaseModel):
    class_: Entity
    property: Entity | None = None  # only terminal step has property
    direction: StepDirection

    @classmethod
    def from_string(cls, raw: str, **kwargs) -> Self:
        if result := STEP_CLASS_AND_PROPERTY_REGEX_COMPILED.match(raw):
            return cls(
                class_=Entity.from_string(result.group(EntityTypes.class_)),
                property=Entity.from_string(result.group(EntityTypes.property_)),
                direction=_direction_by_symbol[result.group("direction")],
                **kwargs,
            )
        elif result := STEP_CLASS_REGEX_COMPILED.match(raw):
            return cls(
                class_=Entity.from_string(result.group(EntityTypes.class_)),
                direction=_direction_by_symbol[result.group("direction")],
            )  # type: ignore
        msg = f"Invalid step {raw}, expected in one of the following forms:"
        msg += " ->prefix:suffix, <-prefix:suffix, ->prefix:suffix(prefix:suffix) or <-prefix:suffix(prefix:suffix)"
        raise ValueError(msg)

    def __str__(self) -> str:
        if self.property:
            return f"{self.class_}({self.property})"
        else:
            return f"{_symbol_by_direction[self.direction]}{self.class_}"

    def __repr__(self) -> str:
        return self.__str__()


class Traversal(BaseModel):
    class_: Entity

    def __str__(self) -> str:
        return f"{self.class_}"

    def __repr__(self) -> str:
        return self.__str__()

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)


class SingleProperty(Traversal):
    property: Entity

    @classmethod
    def from_string(cls, class_: str, property_: str) -> Self:
        return cls(class_=Entity.from_string(class_), property=Entity.from_string(property_))

    def __str__(self) -> str:
        return f"{self.class_}({self.property})"


class SelfReferenceProperty(Traversal):
    @classmethod
    def from_string(cls, class_: str) -> Self:
        return cls(class_=Entity.from_string(class_))


class Origin(BaseModel):
    class_: Entity

    @field_validator("class_", mode="before")
    def process_if_string(cls, value):
        return Entity.from_string(value) if isinstance(value, str) else value


class Hop(Traversal):
    """Multi or single hop traversal through graph"""

    traversal: list[Step]

    @classmethod
    def from_string(cls, class_: str, traversal: str | list[Step]) -> Self:
        return cls(
            class_=Entity.from_string(class_),
            traversal=(
                [Step.from_string(result[0]) for result in STEP_REGEX_COMPILED.findall(traversal)]
                if isinstance(traversal, str)
                else traversal
            ),
        )

    def __str__(self) -> str:
        return f"{self.class_}{''.join([str(step) for step in self.traversal])}"


class TableLookup(BaseModel):
    name: str
    key: str
    value: str


class Rule(BaseModel):
    pass


class Query(BaseModel):
    query: str


class RDFPath(Rule):
    traversal: SingleProperty | SelfReferenceProperty | Hop

    def __str__(self) -> str:
        return f"{self.traversal}"

    def __repr__(self) -> str:
        return self.__str__()

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)


class RawLookup(RDFPath):
    table: TableLookup


class SPARQLQuery(RDFPath):
    traversal: Query


def parse_traversal(raw: str) -> SelfReferenceProperty | SingleProperty | Hop:
    if result := CLASS_ID_REGEX_COMPILED.match(raw):
        return SelfReferenceProperty.from_string(class_=result.group(EntityTypes.class_))
    elif result := SINGLE_PROPERTY_REGEX_COMPILED.match(raw):
        return SingleProperty.from_string(
            class_=result.group(EntityTypes.class_),
            property_=result.group(EntityTypes.property_),
        )
    elif result := HOP_REGEX_COMPILED.match(raw):
        return Hop.from_string(class_=result.group("origin"), traversal=result.group(_traversal))
    else:
        raise NeatValueError(f"Invalid RDF Path: {raw!r}")


def parse_table_lookup(raw: str) -> TableLookup:
    if result := TABLE_REGEX_COMPILED.match(raw):
        return TableLookup(
            name=result.group(Lookup.table),
            key=result.group(Lookup.key),
            value=result.group(Lookup.value),
        )
    raise NeatValueError(f"Invalid table lookup: {raw!r}")


def parse_rule(rule_raw: str, rule_type: TransformationRuleType | None) -> RDFPath:
    match rule_type:
        case TransformationRuleType.rdfpath:
            rule_raw = rule_raw.replace(" ", "")
            return RDFPath(traversal=parse_traversal(rule_raw))
        case TransformationRuleType.rawlookup:
            rule_raw = rule_raw.replace(" ", "")
            if Counter(rule_raw).get("|") != 1:
                raise NeatValueError(f"Invalid rawlookup rule: {rule_raw!r}")
            traversal, table_lookup = rule_raw.split("|")
            return RawLookup(
                traversal=parse_traversal(traversal),
                table=parse_table_lookup(table_lookup),
            )
        case TransformationRuleType.sparql:
            return SPARQLQuery(traversal=Query(query=rule_raw))
        case None:
            raise ValueError("Rule type must be specified")


def is_valid_rule(rule_type: TransformationRuleType, rule_raw: str) -> bool:
    is_valid_rule = {
        TransformationRuleType.rdfpath: is_rdfpath,
        TransformationRuleType.rawlookup: is_rawlookup,
    }[rule_type]
    return is_valid_rule(rule_raw)


def is_rdfpath(raw: str) -> bool:
    try:
        parse_traversal(raw)
    except ValueError:
        return False
    return True


def is_rawlookup(raw: str) -> bool:
    try:
        parse_rule(raw, TransformationRuleType.rawlookup)
    except ValueError:
        return False
    return True
