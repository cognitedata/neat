"""
"""
import re
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, field_validator

from cognite.neat.rules import exceptions

if sys.version_info >= (3, 11):
    from enum import StrEnum
    from typing import Self
else:
    from backports.strenum import StrEnum
    from typing_extensions import Self


@dataclass
class Triple:
    subject: str
    predicate: str
    object: str | None = None
    optional: bool = False


class OWL(StrEnum):
    class_ = "class"
    property_ = "property"
    object_property = "object_property"
    data_property = "data_property"
    annotation_property = "annotation_property"


class TransformationRuleType(StrEnum):
    rdfpath = "rdfpath"
    rawlookup = "rawlookup"
    sparql = "sparql"


class Lookup(StrEnum):
    table = "table"
    key = "key"
    value = "value"  # type: ignore


# here word can be any alphanumeric character, dash, underscore or dot
# which are used to define prefixes and entity names
# this causes super long processing time for some reason

_prefix = r"[a-zA-Z]+[a-zA-Z0-9]*[-_.]*[a-zA-Z0-9]+"
_name = r"[a-zA-Z0-9-_.]+[a-zA-Z0-9]+"


# entity can be either anything except literal value!
_entity = rf"{_prefix}:{_name}"

entity = re.compile(rf"^(?P<prefix>{_prefix}):(?P<name>{_name})$")

# traversal direction
_direction = r"(?P<direction>(->|<-))"

# we are defining classes and their properties
# though we have implicit way of defining object properties and that is using -> or <- operators
_class = rf"(?P<{OWL.class_}>{_entity})"
_property = rf"\((?P<{OWL.property_}>{_entity})\)"


_class_only = re.compile(rf"^{_class}$")

_step = rf"((->|<-){_class}({_property})?)"
_steps = re.compile(_step)
_step_class_only = re.compile(rf"(^{_direction}{_class})$")
_step_class_and_property = re.compile(rf"(^{_direction}{_class}{_property}$)")


_traversal = "traversal"
_origin = rf"(?P<origin>{_entity})"

_hop = re.compile(rf"^{_origin}(?P<{_traversal}>{_step}+)$")

# grabbing specific property for a class, property can be either object, annotation or data property
_single_property = re.compile(rf"^{_class}{_property}$")

# grabbing all properties for a class
_all_properties = re.compile(rf"^{_class}\(\*\)$")

_all_traversal = rf"({_class}\(\*\)|{_class}{_property}|{_origin}(?P<{_traversal}>{_step}+))"

_table = re.compile(rf"^(?P<{Lookup.table}>{_name})\((?P<{Lookup.key}>{_name}),\s*(?P<{Lookup.value}>{_name})\)$")


class Entity(BaseModel):
    """Entity is a class or property in OWL/RDF sense."""

    prefix: str
    name: str

    @property
    def id(self) -> str:
        return f"{self.prefix}:{self.name}"

    def __repr__(self):
        return self.id

    @classmethod
    def from_string(cls, raw: str, **kwargs) -> Self:
        if result := entity.match(raw):
            return cls(prefix=result.group("prefix"), name=result.group("name"), **kwargs)
        else:
            raise ValueError(f"{cls.__name__} is expected to be prefix:name, got {raw}")

    @classmethod
    def from_list(cls, prefix, names: list[str]) -> list[Self]:
        # TODO: Prefixes should be a list of prefixes as you might instances of classes
        # from different namespaces. This is a case when a given data model reuses classes
        # from different ontologies/data models, which is in case of Statnett.
        return [cls(prefix=prefix, name=name) for name in names]


StepDirection = Literal["source", "target", "origin"]
_direction_by_symbol: dict[str, StepDirection] = {"->": "target", "<-": "source"}


class Step(BaseModel):
    class_: Entity
    property: Entity | None = None  # only terminal step has property
    direction: StepDirection

    @classmethod
    def from_string(cls, raw: str, **kwargs) -> Self:
        if result := _step_class_and_property.match(raw):
            return cls(
                class_=Entity.from_string(result.group(OWL.class_)),
                property=Entity.from_string(result.group(OWL.property_)),
                direction=_direction_by_symbol[result.group("direction")],
                **kwargs,
            )
        elif result := _step_class_only.match(raw):
            return cls(
                class_=Entity.from_string(result.group(OWL.class_)),
                direction=_direction_by_symbol[result.group("direction")],
            )  # type: ignore
        msg = f"Invalid step {raw}, expected in one of the following forms:"
        msg += " ->prefix:name, <-prefix:name, ->prefix:name(prefix:name) or <-prefix:name(prefix:name)"
        raise ValueError(msg)


class Traversal(BaseModel):
    class_: Entity


class SingleProperty(Traversal):
    property: Entity

    @classmethod
    def from_string(cls, class_: str, property_: str) -> Self:
        return cls(class_=Entity.from_string(class_), property=Entity.from_string(property_))


class AllReferences(Traversal):
    @classmethod
    def from_string(cls, class_: str) -> Self:
        return cls(class_=Entity.from_string(class_))


class AllProperties(Traversal):
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
            traversal=[Step.from_string(result[0]) for result in _steps.findall(traversal)]
            if isinstance(traversal, str)
            else traversal,
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
    if result := _class_only.match(raw):
        return AllReferences.from_string(class_=result.group(OWL.class_))
    elif result := _all_properties.match(raw):
        return AllProperties.from_string(class_=result.group(OWL.class_))
    elif result := _single_property.match(raw):
        return SingleProperty.from_string(class_=result.group(OWL.class_), property_=result.group(OWL.property_))
    elif result := _hop.match(raw):
        return Hop.from_string(class_=result.group("origin"), traversal=result.group(_traversal))
    else:
        raise exceptions.NotValidRDFPath(raw).to_pydantic_custom_error()


def parse_table_lookup(raw: str) -> TableLookup:
    if result := _table.match(raw):
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
