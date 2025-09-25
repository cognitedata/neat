import re
import sys
from abc import ABC
from typing import Any, ClassVar, Final, Literal, TypeVar, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rdflib import Literal as RDFLiteral
from rdflib import URIRef

from cognite.neat.v0.core._data_model._constants import EntityTypes
from cognite.neat.v0.core._data_model.models.data_types import _XSD_TYPES, DataType
from cognite.neat.v0.core._data_model.models.entities._constants import _PARSE
from cognite.neat.v0.core._data_model.models.entities._single_value import ConceptEntity, ConceptualEntity
from cognite.neat.v0.core._issues.errors._general import NeatValueError
from cognite.neat.v0.core._utils.rdf_ import remove_namespace_from_uri

if sys.version_info <= (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


ValueConstraints = Literal["allValuesFrom", "someValuesFrom", "hasValue"]
CardinalityConstraints = Literal["minCardinality", "maxCardinality", "cardinality", "qualifiedCardinality"]


# Constants for regex patterns - more maintainable
PROPERTY_PATTERN: Final[str] = r"[a-zA-Z0-9._~?@!$&'*+,;=%-]+"
VALUE_PATTERN: Final[str] = r".+"
CARDINALITY_VALUE_PATTERN: Final[str] = r"\d+"
ON_PATTERN: Final[str] = r"[^(]*"

VALUE_CONSTRAINT_REGEX = re.compile(
    rf"^{EntityTypes.value_constraint}:(?P<property>{PROPERTY_PATTERN})\((?P<constraint>{'|'.join(get_args(ValueConstraints))}),(?P<value>{VALUE_PATTERN})\)$"
)

CARDINALITY_CONSTRAINT_REGEX = re.compile(
    rf"^{EntityTypes.cardinality_constraint}:(?P<property>{PROPERTY_PATTERN})\((?P<constraint>{'|'.join(get_args(CardinalityConstraints))}),(?P<value>{CARDINALITY_VALUE_PATTERN})(?:,(?P<on>{ON_PATTERN}))?\)$"
)


class NamedIndividualEntity(ConceptualEntity):
    type_: ClassVar[EntityTypes] = EntityTypes.named_individual

    @model_validator(mode="after")
    def reset_prefix(self) -> Self:
        self.prefix = "ni"
        return self


class ConceptPropertyRestriction(ABC, BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
        strict=False,
        extra="ignore",
    )
    type_: ClassVar[EntityTypes] = EntityTypes.concept_restriction
    property_: str

    @classmethod
    def load(cls: "type[T_ConceptPropertyRestriction]", data: Any, **defaults: Any) -> "T_ConceptPropertyRestriction":
        if isinstance(data, cls):
            return data
        elif not isinstance(data, str):
            raise ValueError(f"Cannot load {cls.__name__} from {data}")

        return cls.model_validate({_PARSE: data, "defaults": defaults})

    @model_validator(mode="before")
    def _load(cls, data: Any) -> dict:
        defaults = {}
        if isinstance(data, dict) and _PARSE in data:
            defaults = data.get("defaults", {})
            data = data[_PARSE]
        if isinstance(data, dict):
            data.update(defaults)
            return data

        if not isinstance(data, str):
            raise ValueError(f"Cannot load {cls.__name__} from {data}")

        return cls._parse(data, defaults)

    @classmethod
    def _parse(cls, data: str, defaults: dict) -> dict:
        raise NotImplementedError(f"{cls.__name__} must implement _parse method")

    def dump(self) -> str:
        return self.__str__()

    def as_tuple(self) -> tuple[str, ...]:
        # We haver overwritten the serialization to str, so we need to do it manually
        extra: tuple[str, ...] = tuple(
            [
                str(v or "")
                for field_name in self.model_fields.keys()
                if (v := getattr(self, field_name)) and field_name not in {"property_"}
            ]
        )

        return self.property_, *extra

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, ConceptPropertyRestriction):
            return NotImplemented
        return self.as_tuple() < other.as_tuple()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConceptPropertyRestriction):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __hash__(self) -> int:
        return hash(str(self))


T_ConceptPropertyRestriction = TypeVar("T_ConceptPropertyRestriction", bound="ConceptPropertyRestriction")


class ConceptPropertyValueConstraint(ConceptPropertyRestriction):
    type_: ClassVar[EntityTypes] = EntityTypes.value_constraint
    constraint: ValueConstraints
    value: RDFLiteral | ConceptEntity | NamedIndividualEntity

    @field_validator("value")
    def validate_value(cls, value: Any) -> Any:
        if isinstance(value, RDFLiteral) and value.datatype is None:
            raise NeatValueError("RDFLiteral must have a datatype set, which must be one of the XSD types.")
        return value

    def __str__(self) -> str:
        value_str = (
            f"{self.value.value}^^{remove_namespace_from_uri(cast(URIRef, self.value.datatype))}"
            if isinstance(self.value, RDFLiteral)
            else str(self.value)
        )
        return f"{self.type_}:{self.property_}({self.constraint},{value_str})"

    @classmethod
    def _parse(cls, data: str, defaults: dict) -> dict:
        if not (result := VALUE_CONSTRAINT_REGEX.match(data)):
            raise NeatValueError(f"Invalid value constraint format: {data}")

        property_ = result.group("property")
        constraint = result.group("constraint")
        raw_value = result.group("value")

        value: NamedIndividualEntity | RDFLiteral | ConceptEntity
        # scenario 1: NamedIndividual as value restriction
        if raw_value.startswith("ni:"):
            value = NamedIndividualEntity.load(raw_value)
        # scenario 2: Datatype as value restriction
        elif "^^" in raw_value:
            if len(value_components := raw_value.split("^^")) == 2 and value_components[1] in _XSD_TYPES:
                value = RDFLiteral(value_components[0], datatype=DataType.load(value_components[1]).as_xml_uri_ref())
            else:
                raise NeatValueError(f"Invalid value format for datatype: {raw_value}")

        # scenario 3: ConceptEntity as value restriction
        else:
            value = ConceptEntity.load(raw_value, **defaults)

        return dict(property_=property_, constraint=constraint, value=value)


class ConceptPropertyCardinalityConstraint(ConceptPropertyRestriction):
    type_: ClassVar[EntityTypes] = EntityTypes.cardinality_constraint
    constraint: CardinalityConstraints
    value: int = Field(ge=0)
    on: DataType | ConceptEntity | None = None

    def __str__(self) -> str:
        on_str = f",{self.on}" if self.on else ""
        return f"{self.type_}:{self.property_}({self.constraint},{self.value}{on_str})"

    @classmethod
    def _parse(cls, data: str, defaults: dict) -> dict:
        if not (result := CARDINALITY_CONSTRAINT_REGEX.match(data)):
            raise NeatValueError(f"Invalid cardinality constraint format: {data}")

        property_ = result.group("property")
        constraint = result.group("constraint")
        value = result.group("value")
        on = result.group("on")
        if on:
            if on in _XSD_TYPES:
                on = DataType.load(on)
            else:
                on = cast(ConceptEntity, ConceptEntity.load(on, **defaults))

        return dict(property_=property_, constraint=constraint, value=value, on=on)


def parse_restriction(data: str, **defaults: Any) -> ConceptPropertyRestriction:
    """Parse a string to create either a value or cardinality restriction.

    Args:
        data: String representation of the restriction
        **defaults: Default values to use when parsing

    Returns:
        Either a ConceptPropertyValueConstraint or ConceptPropertyCardinalityConstraint

    Raises:
        NeatValueError: If the string cannot be parsed as either restriction type
    """
    # Check for value constraint pattern first (more specific)
    if VALUE_CONSTRAINT_REGEX.match(data):
        try:
            return ConceptPropertyValueConstraint.load(data, **defaults)
        except Exception as e:
            raise NeatValueError(f"Failed to parse value constraint: {data}") from e

    # Check for cardinality constraint pattern
    if CARDINALITY_CONSTRAINT_REGEX.match(data):
        try:
            return ConceptPropertyCardinalityConstraint.load(data, **defaults)
        except Exception as e:
            raise NeatValueError(f"Failed to parse cardinality constraint: {data}") from e

    # If neither pattern matches, provide a clear error
    raise NeatValueError(
        f"Invalid restriction format: {data}. "
        f"Expected format: '{EntityTypes.value_constraint}:property(constraint,value)' "
        f"or '{EntityTypes.cardinality_constraint}:property(constraint,value[,on])'"
    )


T_ConceptRestriction = TypeVar("T_ConceptRestriction", bound=ConceptPropertyRestriction)
