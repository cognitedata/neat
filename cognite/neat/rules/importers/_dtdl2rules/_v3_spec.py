import re
from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeAlias

from pydantic import BaseModel, Field, field_validator, model_serializer, model_validator

if TYPE_CHECKING:
    from pydantic.type_adapter import IncEx

# Regex is from the spec: https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTMI/README.md#validation-regular-expressions
_DTMI_REGEX = (
    r"^dtmi:(?:_+[A-Za-z0-9]|[A-Za-z])(?:[A-Za-z0-9_]*[A-Za-z0-9])?(?::(?:_+[A-Za-z0-9]|[A-Za-z])"
    r"(?:[A-Za-z0-9_]*[A-Za-z0-9])?)*(?:;[1-9][0-9]{0,8}(?:\.[1-9][0-9]{0,5})?)?$"
)

_DTMI_COMPILED = re.compile(_DTMI_REGEX)


class DTMI(BaseModel):
    scheme: ClassVar[str] = "dtmi"
    path: list[str]
    version: str

    @model_validator(mode="before")
    def from_string(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if not _DTMI_COMPILED.match(value):
            raise ValueError(f"Invalid DTMI {value}")
        value = value.removeprefix(cls.scheme + ":")
        path_str, version = value.split(";", 1)
        return dict(path=path_str.split(":"), version=version)

    @model_serializer
    def to_string(self) -> str:
        return f"{self.scheme}:{':'.join(self.path)};{self.version}"

    if TYPE_CHECKING:
        # Ensure type checkers works correctly, ref
        # https://docs.pydantic.dev/latest/concepts/serialization/#overriding-the-return-type-when-dumping-a-model
        def model_dump(  # type: ignore[override]
            self,
            *,
            mode: Literal["json", "python"] | str = "python",
            include: IncEx | None = None,
            exclude: IncEx | None = None,
            by_alias: bool = False,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
            round_trip: bool = False,
            warnings: bool = True,
        ) -> str:
            ...


IRI: TypeAlias = str


class DTDLBase(BaseModel, ABC):
    type: ClassVar[str]
    id_: DTMI | None = Field(None, alias="@id")
    comment: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    description: str | None = None


PrimitiveSchema: TypeAlias = Literal[
    "boolean", "date", "dateTime", "double", "duration", "float", "integer", "long", "string", "time"
]


class DTDLBaseWithName(DTDLBase, ABC):
    name: str


class DTDLBaseWithSchema(DTDLBaseWithName, ABC):
    schema_: "Schema | IRI | None" = Field(None, alias="schema")  # type: ignore[assignment]

    @field_validator("schema_", mode="before")
    def select_schema_type(cls, value: Any) -> Any:
        if isinstance(value, dict) and (type_ := value.get("@type")) and (cls_ := DTDL_CLS_BY_TYPE.get(type_)):
            return cls_.model_validate(value)
        return value


class DTDLField(DTDLBaseWithSchema):
    type = "Field"


class Object(DTDLBase):
    type = "Object"
    fields: list[DTDLField] | None = None


class MapKey(DTDLBaseWithName):
    type = "MapKey"
    schema: str  # type: ignore[assignment]


class MapValue(DTDLBaseWithSchema):
    type = "MapValue"


class Map(DTDLBase):
    type = "Map"
    map_key: MapKey = Field(alias="mapKey")
    map_value: MapValue = Field(alias="mapValue")


class EnumValue(DTDLBaseWithName):
    type = "EnumValue"
    enum_value: str = Field(alias="enumValue")


class Enum(DTDLBase):
    type = "Enum"
    enum_values: list[EnumValue] = Field(alias="enumValues")
    value_schema: PrimitiveSchema = Field(alias="valueSchema")


class Array(DTDLBaseWithName):
    type = "Array"
    element_schema: "Schema" = Field(alias="elementSchema")


ComplexSchema: TypeAlias = Array | Enum | Map | Object

Schema: TypeAlias = PrimitiveSchema | ComplexSchema


class Component(DTDLBaseWithSchema):
    type = "Component"
    schema_: "Interface" = Field(alias="schema")  # type: ignore[assignment]


class Property(DTDLBaseWithSchema):
    type = "Property"
    writable: bool | None = None


class Relationship(DTDLBaseWithName):
    type = "Relationship"
    minMultiplicity: int | None = None
    maxMultiplicity: int | None = None
    properties: list[Property] | None = None
    target: DTMI | None = None
    writable: bool | None = None


class CommandRequest(DTDLBaseWithSchema):
    type = "CommandRequest"


class CommandResponse(DTDLBaseWithSchema):
    type = "CommandResponse"


class Command(DTDLBaseWithSchema):
    type = "Command"
    request: CommandRequest | None = None
    response: CommandResponse | None = None


class Telemetry(DTDLBaseWithSchema):
    type = "Telemetry"
    ...


class Interface(DTDLBase):
    type = "Interface"
    id_: IRI = Field(alias="@id")  # type: ignore[assignment]
    context: IRI | None = Field(alias="@context")
    extends: list[DTMI] | None = None
    contents: list[Command | Component | Property | Relationship | Telemetry | IRI] | None = None
    schemas: list[Array | Enum | Map | Object] | None = None

    @field_validator("contents", "schemas", mode="before")
    def select_content_type(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        output: list[DTDLBase] = []
        for item in value:
            if isinstance(item, dict) and (type_ := item.get("@type")) and (cls_ := DTDL_CLS_BY_TYPE.get(type_)):
                item = cls_.model_validate(item)
            output.append(item)
        return output


DTDL_CLS_BY_TYPE: dict[str, type[DTDLBase]] = {}
to_check = list(DTDLBase.__subclasses__())
while to_check:
    cls = to_check.pop()
    to_check.extend(cls.__subclasses__())
    if ABC in cls.__bases__:
        continue
    DTDL_CLS_BY_TYPE[cls.type] = cls
del cls, to_check
