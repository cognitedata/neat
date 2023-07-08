"""
"""
import re
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Optional, Self

from pydantic import BaseModel, validator


@dataclass
class Triple:
    subject: str
    predicate: str
    object: str = None


class OWL(StrEnum):
    class_ = "class"
    property_ = "property"
    object_property = "object_property"
    data_property = "data_property"
    annotation_property = "annotation_property"


class RuleType(StrEnum):
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


StepDirection = Literal["source", "target"]
_direction_by_symbol = {"->": "target", "<-": "source"}


class Step(BaseModel):
    class_: Entity
    property: Optional[Entity] = None  # only terminal step has property
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
    pass


class SingleProperty(Traversal):
    class_: Entity
    property: Entity

    @validator("*", pre=True)
    def process_if_string(cls, value):
        return Entity.from_string(value) if isinstance(value, str) else value


class AllReferences(Traversal):
    class_: Entity

    @validator("class_", pre=True)
    def process_if_string(cls, value):
        return Entity.from_string(value) if isinstance(value, str) else value


class AllProperties(Traversal):
    class_: Entity

    @validator("class_", pre=True)
    def process_if_string(cls, value):
        return Entity.from_string(value) if isinstance(value, str) else value


class Origin(BaseModel):
    class_: Entity

    @validator("class_", pre=True)
    def process_if_string(cls, value):
        return Entity.from_string(value) if isinstance(value, str) else value


class Hop(Traversal):
    """Multi or single hop traversal through graph"""

    origin: Origin
    traversal: list[Step]

    @validator("origin", pre=True)
    def process_origin_if_string(cls, value):
        return Origin(class_=value) if isinstance(value, str) else value

    @validator("traversal", pre=True)
    def process_path_if_string(cls, value):
        if isinstance(value, str):
            return [Step.from_string(result[0]) for result in _steps.findall(value)]
        return value


class TableLookup(BaseModel):
    name: str
    key: str
    value: str


class Rule(BaseModel):
    pass


class RDFPath(Rule):
    traversal: Traversal


class RawLookup(RDFPath):
    table: TableLookup


class Query(BaseModel):
    query: str


class SPARQLQuery(Rule):
    traversal: Query


def parse_traversal(raw: str) -> AllReferences | AllProperties | SingleProperty | Hop:
    if result := _class_only.match(raw):
        return AllReferences(class_=result.group(OWL.class_))
    elif result := _all_properties.match(raw):
        return AllProperties(class_=result.group(OWL.class_))
    elif result := _single_property.match(raw):
        return SingleProperty(class_=result.group(OWL.class_), property=result.group(OWL.property_))
    elif result := _hop.match(raw):
        return Hop(origin=result.group("origin"), traversal=result.group(_traversal))
    else:
        raise ValueError(f"{raw} is not a valid rdfpath!")


def parse_table_lookup(raw: str) -> TableLookup:
    if result := _table.match(raw):
        return TableLookup(
            name=result.group(Lookup.table), key=result.group(Lookup.key), value=result.group(Lookup.value)
        )
    ValueError(f"{raw} is not a valid table lookup")


def parse_rule(rule_raw: str, rule_type: RuleType) -> RDFPath:
    match rule_type:
        case RuleType.rdfpath:
            rule_raw = rule_raw.replace(" ", "")
            return RDFPath(traversal=parse_traversal(rule_raw))
        case RuleType.rawlookup:
            rule_raw = rule_raw.replace(" ", "")
            if Counter(rule_raw).get("|") != 1:
                raise ValueError(f"Invalid {RuleType.rawlookup} expected traversal | table lookup, got {rule_raw}")
            traversal, table_lookup = rule_raw.split("|")
            return RawLookup(traversal=parse_traversal(traversal), table=parse_table_lookup(table_lookup))
        case RuleType.sparql:
            return SPARQLQuery(traversal=Query(query=rule_raw))


def is_valid_rule(rule_type: RuleType, rule_raw: str) -> bool:
    is_valid_rule = {RuleType.rdfpath: is_rdfpath, RuleType.rawlookup: is_rawlookup}[rule_type]
    return is_valid_rule(rule_raw)


def is_rdfpath(raw: str) -> bool:
    try:
        parse_traversal(raw)
    except ValueError:
        return False
    return True


def is_rawlookup(raw: str) -> bool:
    try:
        parse_rule(raw, RuleType.rawlookup)
    except ValueError:
        return False
    return True
