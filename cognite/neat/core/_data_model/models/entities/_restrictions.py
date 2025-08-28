import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal, TypeAlias, TypeVar, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator
from rdflib import Literal as RDFLiteral

from cognite.neat.core._data_model._constants import EntityTypes
from cognite.neat.core._data_model.models.data_types import _XSD_TYPES, DataType
from cognite.neat.core._data_model.models.entities._constants import _PARSE
from cognite.neat.core._data_model.models.entities._single_value import ConceptEntity, NamedIndividualEntity
from cognite.neat.core._issues.errors._general import NeatValueError
from cognite.neat.core._utils.rdf_ import remove_namespace_from_uri


def get_constraints(
    key: Literal["value", "cardinality"],
) -> list[str]:
    return {
        "value": ["allValuesFrom", "someValuesFrom", "hasValue"],
        "cardinality": [
            "minCardinality",
            "maxCardinality",
            "cardinality",
            "qualifiedCardinality",
        ],
    }[key]


ValueConstraints = Literal["allValuesFrom", "someValuesFrom", "hasValue"]
CardinalityConstraints = Literal["minCardinality", "maxCardinality", "cardinality", "qualifiedCardinality"]


VALUE_CONSTRAINT_REGEX = re.compile(
    rf"^{EntityTypes.value_constraint}:(?P<property>[a-zA-Z0-9._~?@!$&'*+,;=%-]+)\((?P<constraint>{'|'.join(get_args(ValueConstraints))}),(?P<value>.+)\)$"
)

CARDINALITY_CONSTRAINT_REGEX = re.compile(
    rf"^{EntityTypes.cardinality_constraint}:(?P<property>[a-zA-Z0-9._~?@!$&'*+,;=%-]+)\((?P<constraint>{'|'.join(get_args(CardinalityConstraints))}),(?P<value>\d+)(?:,(?P<on>[^(]*))?\)$"
)


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

    @abstractmethod
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

    def __str__(self) -> str:
        value_str = (
            f"{self.value.value}^^{remove_namespace_from_uri(self.value.datatype)}"
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

        # scenarion 1: NamedIndividual as value restriction
        if raw_value.startswith("ni:"):
            value = NamedIndividualEntity.load(raw_value)

        # scenario 2: Datatype as value restriction
        elif "^^" in raw_value:
            value_components = raw_value.split("^^")
            value = RDFLiteral(value_components[0], datatype=DataType.load(value_components[1]).as_xml_uri_ref())

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
        return f"cardinalityConstraint:{self.property_}({self.constraint},{self.value}{on_str})"

    @classmethod
    def _parse(cls, data: str, defaults: dict) -> dict:
        if not (result := CARDINALITY_CONSTRAINT_REGEX.match(data)):
            print(f"Failed to match regex: {result}")
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
    """Parse a string to create either a value or cardinality restriction."""
    try:
        return ConceptPropertyValueConstraint.load(data, **defaults)
    except:
        try:
            return ConceptPropertyCardinalityConstraint.load(data, **defaults)
        except:
            raise NeatValueError(f"Unable to parse restriction: {data}")


ConceptRestriction: TypeAlias = ConceptPropertyValueConstraint | ConceptPropertyCardinalityConstraint
T_ConceptRestriction = TypeVar("T_ConceptRestriction", bound=ConceptRestriction)
