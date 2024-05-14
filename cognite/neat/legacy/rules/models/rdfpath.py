""" """

import re
import sys
from collections import Counter
from typing import Literal

from pydantic import BaseModel, field_validator

from cognite.neat.legacy.rules import exceptions

from ._base import (
    CLASS_ID_REGEX,
    CLASS_ID_REGEX_COMPILED,
    ENTITY_ID_REGEX,
    PROPERTY_ID_REGEX,
    SUFFIX_REGEX,
    Entity,
    EntityTypes,
)

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


class Step(BaseModel):
    class_: Entity
    property: Entity | None = None  # only terminal step has property
    direction: StepDirection

    @classmethod
    def from_string(cls, raw: str, **kwargs) -> Self:
        if result := STEP_CLASS_AND_PROPERTY_REGEX_COMPILED.match(raw):
            return cls(
                class_=Entity.from_string(result.group(EntityTypes.class_), type_="class"),
                property=Entity.from_string(result.group(EntityTypes.property_), type_="property"),
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


class Traversal(BaseModel):
    class_: Entity


class SingleProperty(Traversal):
    property: Entity

    @classmethod
    def from_string(cls, class_: str, property_: str) -> Self:
        return cls(
            class_=Entity.from_string(class_, type_="class"), property=Entity.from_string(property_, type_="property")
        )


class AllReferences(Traversal):
    @classmethod
    def from_string(cls, class_: str) -> Self:
        return cls(class_=Entity.from_string(class_, type_="class"))


class AllProperties(Traversal):
    @classmethod
    def from_string(cls, class_: str) -> Self:
        return cls(class_=Entity.from_string(class_, type_="class"))


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


class TableLookup(BaseModel):
    name: str
    key: str
    value: str


class Rule(BaseModel):
    pass


class Query(BaseModel):
    query: str


class RDFPath(Rule):
    traversal: Traversal | Query


class RawLookup(RDFPath):
    table: TableLookup


class SPARQLQuery(RDFPath):
    traversal: Query


def parse_traversal(raw: str) -> AllReferences | AllProperties | SingleProperty | Hop:
    if result := CLASS_ID_REGEX_COMPILED.match(raw):
        return AllReferences.from_string(class_=result.group(EntityTypes.class_))
    elif result := ALL_PROPERTIES_REGEX_COMPILED.match(raw):
        return AllProperties.from_string(class_=result.group(EntityTypes.class_))
    elif result := SINGLE_PROPERTY_REGEX_COMPILED.match(raw):
        return SingleProperty.from_string(
            class_=result.group(EntityTypes.class_), property_=result.group(EntityTypes.property_)
        )
    elif result := HOP_REGEX_COMPILED.match(raw):
        return Hop.from_string(class_=result.group("origin"), traversal=result.group(_traversal))
    else:
        raise exceptions.NotValidRDFPath(raw).to_pydantic_custom_error()


def parse_table_lookup(raw: str) -> TableLookup:
    if result := TABLE_REGEX_COMPILED.match(raw):
        return TableLookup(
            name=result.group(Lookup.table), key=result.group(Lookup.key), value=result.group(Lookup.value)
        )
    raise exceptions.NotValidTableLookUp(raw).to_pydantic_custom_error()


def parse_rule(rule_raw: str, rule_type: TransformationRuleType | None) -> RDFPath:
    match rule_type:
        case TransformationRuleType.rdfpath:
            rule_raw = rule_raw.replace(" ", "")
            return RDFPath(traversal=parse_traversal(rule_raw))
        case TransformationRuleType.rawlookup:
            rule_raw = rule_raw.replace(" ", "")
            if Counter(rule_raw).get("|") != 1:
                raise exceptions.NotValidRAWLookUp(rule_raw).to_pydantic_custom_error()
            traversal, table_lookup = rule_raw.split("|")
            return RawLookup(traversal=parse_traversal(traversal), table=parse_table_lookup(table_lookup))
        case TransformationRuleType.sparql:
            return SPARQLQuery(traversal=Query(query=rule_raw))
        case None:
            raise ValueError("Rule type must be specified")


def is_valid_rule(rule_type: TransformationRuleType, rule_raw: str) -> bool:
    is_valid_rule = {TransformationRuleType.rdfpath: is_rdfpath, TransformationRuleType.rawlookup: is_rawlookup}[
        rule_type
    ]
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
