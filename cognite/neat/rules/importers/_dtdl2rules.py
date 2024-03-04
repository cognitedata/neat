from pathlib import Path
from typing import Literal, TypeAlias, overload

from pydantic import BaseModel, Field

from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.validation import IssueList

from ._base import BaseImporter


class DTDLImporter(BaseImporter):
    def __init__(
        self,
    ):
        ...

    @classmethod
    def from_directory(cls, directory: Path) -> "DTDLImporter":
        raise NotImplementedError()

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> InformationRules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[InformationRules | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[InformationRules | None, IssueList] | InformationRules:
        raise NotImplementedError()


# Todo Annotated
DTMI: TypeAlias = str

IRI: TypeAlias = str


PrimitiveSchema: TypeAlias = Literal[
    "boolean", "date", "dateTime", "double", "duration", "float", "integer", "long", "string", "time"
]


class DTDLBase(BaseModel):
    type: IRI = Field(alias="@type")
    id_: DTMI | None = Field(None, alias="@id")
    comment: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    description: str | None = None


class DTDLBaseWithName(DTDLBase):
    name: str


class DTDLBaseWithSchema(DTDLBaseWithName):
    schema_: "Schema" = Field(alias="schema")


class DTDLField(DTDLBaseWithName):
    type: IRI | None = Field(None, alias="@type")  # type: ignore[assignment]


class Object(DTDLBase):
    fields: list[DTDLField] | None = None


class MapKey(DTDLBaseWithName):
    schema: str  # type: ignore[assignment]


class MapValue(DTDLBaseWithSchema):
    ...


class Map(DTDLBaseWithName):
    map_key: MapKey = Field(alias="mapKey")
    map_value: MapValue = Field(alias="mapValue")


class EnumValue(DTDLBaseWithName):
    enum_values: str = Field(alias="enumValues")


class Enum(DTDLBaseWithName):
    enum_values: list[EnumValue] = Field(alias="enumValues")
    values_schema: PrimitiveSchema = Field(alias="valuesSchema")


class Array(DTDLBaseWithName):
    element_schema: "Schema" = Field(alias="elementSchema")


ComplexSchema: TypeAlias = Array | Enum | Map | Object

Schema: TypeAlias = PrimitiveSchema | ComplexSchema


class Component(DTDLBaseWithSchema):
    ...


class Property(DTDLBaseWithSchema):
    writable: bool | None = None


class Relationship(DTDLBaseWithSchema):
    minMultiplicity: int | None = None
    maxMultiplicity: int | None = None
    properties: list[Property] | None = None
    target: DTMI | None = None
    writable: bool | None = None


class CommandRequest(DTDLBaseWithSchema):
    ...


class CommandResponse(DTDLBaseWithSchema):
    ...


class Command(DTDLBaseWithSchema):
    request: CommandRequest | None = None
    response: CommandResponse | None = None


class Telemetry(DTDLBaseWithSchema):
    ...


class Interface(DTDLBase):
    type: IRI = Field(alias="@type")
    context: IRI | None = Field(alias="@context")
    extends: list[DTMI] | None = None
    contents: list[Command | Component | Property | Relationship | Telemetry] | None = None
    schemas: list[Array | Enum | Map | Object]
