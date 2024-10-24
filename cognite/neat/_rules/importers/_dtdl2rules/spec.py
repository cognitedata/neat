"""
This is a pydantic validation implementation of the DTDL v2 and v3 specifications.

The specs are taken from:

 * Spec v2:  https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v2/DTDL.v2.md
 * Spec v3: https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v3/DTDL.v3.md
"""

import re
import warnings
from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeAlias

from pydantic import BaseModel, Field, field_validator, model_serializer, model_validator
from pydantic.fields import FieldInfo

from cognite.neat._rules.models.entities import ClassEntity

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

    def as_class_id(self) -> ClassEntity:
        return ClassEntity(prefix="_".join(self.path[:-1]), suffix=self.path[-1], version=self.version)

    def __hash__(self) -> int:
        return hash(self.to_string())

    def __repr__(self) -> str:
        return self.to_string()

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
        ) -> str: ...


IRI: TypeAlias = str


class Unit(BaseModel, ABC):
    value: str
    semantic_type: str | None = Field(None, alias="semanticType")
    unit_type: str | None = Field(None, alias="unitType")

    def __hash__(self) -> int:
        return hash(self.to_string())

    def __repr__(self) -> str:
        return self.to_string()

    @model_validator(mode="before")
    def from_string(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        from ._unit_lookup import ENTRY_BY_UNIT

        if value not in ENTRY_BY_UNIT:
            return dict(unit=value)
        entry = ENTRY_BY_UNIT[value]
        return dict(
            value=value,
            semanticType=entry.semantic_type,
            unitType=entry.unit_type,
        )

    @model_serializer
    def to_string(self) -> str:
        return self.value

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
        ) -> str: ...


class DTDLBase(BaseModel, ABC):
    type: ClassVar[str]
    spec_version: ClassVar[frozenset[str]]
    id_: DTMI | None = Field(None, alias="@id")
    comment: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    description: str | None = None

    @property
    def identifier_with_fallback(self) -> str:
        return (self.id_.model_dump() if self.id_ else self.display_name) or "MISSING"


PrimitiveSchema: TypeAlias = Literal[
    "boolean", "date", "dateTime", "double", "duration", "float", "integer", "long", "string", "time"
]


class DTDLBaseWithName(DTDLBase, ABC):
    name: str


class DTDLBaseWithSchema(DTDLBaseWithName, ABC):
    schema_: "Schema | DTMI | None" = Field(None, alias="schema")  # type: ignore[assignment]

    @field_validator("schema_", mode="before")
    def select_schema_type(cls, value: Any) -> Any:
        if isinstance(value, dict) and (type_ := value.get("@type")):
            context = Interface.default_context
            spec_version = context.rsplit(";", maxsplit=1)[1]
            try:
                cls_by_type = DTDL_CLS_BY_TYPE_BY_SPEC[spec_version]
            except KeyError:
                raise ValueError(f"DTDL Spec v{spec_version} is not supported: {context}") from None
            if isinstance(type_, str) and (cls_ := cls_by_type.get(type_)) is not None:
                return cls_.model_validate(value)
            elif isinstance(type_, list) and len(type_) == 2 and (cls_ := cls_by_type.get(type_[0])) is not None:
                # In the spec v2, the type of Telemetry and Property can be a list of two strings,
                # [[Telemetry|Property, "Semantic Type"].
                from ._unit_lookup import UNIT_TYPE_BY_SEMANTIC_TYPE

                if unit_type := UNIT_TYPE_BY_SEMANTIC_TYPE.get(type_[1]) and "unit" in value:
                    value["unit"] = {
                        "value": value["unit"],
                        "semanticType": type_[1],
                        "unitType": unit_type,
                    }
                return cls_.model_validate(value)
        return value


class DTDLField(DTDLBaseWithSchema):
    type = "Field"
    spec_version = frozenset(["2", "3"])


class Object(DTDLBase):
    type = "Object"
    spec_version = frozenset(["2", "3"])
    fields: list[DTDLField] | None = None


class MapKey(DTDLBaseWithName):
    type = "MapKey"
    spec_version = frozenset(["2", "3"])
    schema_: str = Field(alias="schema")


class MapValue(DTDLBaseWithSchema):
    type = "MapValue"
    spec_version = frozenset(["2", "3"])


class Map(DTDLBase):
    type = "Map"
    spec_version = frozenset(["2", "3"])
    map_key: MapKey = Field(alias="mapKey")
    map_value: MapValue = Field(alias="mapValue")


class EnumValue(DTDLBaseWithName):
    type = "EnumValue"
    spec_version = frozenset(["2", "3"])
    enum_value: str = Field(alias="enumValue")


class Enum(DTDLBase):
    type = "Enum"
    spec_version = frozenset(["2", "3"])
    enum_values: list[EnumValue] = Field(alias="enumValues")
    value_schema: PrimitiveSchema = Field(alias="valueSchema")


class Array(DTDLBase):
    type = "Array"
    spec_version = frozenset(["2", "3"])
    element_schema: "Schema" = Field(alias="elementSchema")


ComplexSchema: TypeAlias = Array | Enum | Map | Object

Schema: TypeAlias = PrimitiveSchema | ComplexSchema


class Component(DTDLBaseWithSchema):
    type = "Component"
    spec_version = frozenset(["2", "3"])
    schema_: "Interface | DTMI" = Field(alias="schema")  # type: ignore[assignment]


class Property(DTDLBaseWithSchema):
    type = "Property"
    spec_version = frozenset(["3"])
    writable: bool | None = None


class PropertyV2(Property):
    spec_version = frozenset(["2"])
    unit: Unit | None = None


class Relationship(DTDLBaseWithName):
    type = "Relationship"
    spec_version = frozenset(["2", "3"])
    min_multiplicity: int | None = Field(None, alias="minMultiplicity", le=0, ge=0)
    max_multiplicity: int | None = Field(None, alias="maxMultiplicity", ge=1)
    properties: list[Property] | None = None
    target: DTMI | None = None
    writable: bool | None = None


class CommandRequest(DTDLBaseWithSchema):
    type = "CommandRequest"
    spec_version = frozenset(["3"])


class CommandResponse(DTDLBaseWithSchema):
    type = "CommandResponse"
    spec_version = frozenset(["3"])


class CommandPayload(DTDLBaseWithSchema):
    type = "CommandPayload"
    spec_version = frozenset(["2"])


class Command(DTDLBaseWithSchema):
    type = "Command"
    spec_version = frozenset(["3"])
    request: CommandRequest | None = None
    response: CommandResponse | None = None


class CommandV2(DTDLBaseWithSchema):
    type = "Command"
    spec_version = frozenset(["2"])
    request: CommandPayload | None = None
    response: CommandPayload | None = None


class Telemetry(DTDLBaseWithSchema):
    type = "Telemetry"
    spec_version = frozenset(["3"])


class TelemetryV2(Telemetry):
    spec_version = frozenset(["2"])
    unit: Unit | None = None


class Interface(DTDLBase):
    type = "Interface"
    spec_version = frozenset(["2", "3"])
    default_context: ClassVar[IRI] = Field(
        "dtmi:dtdl:context;3",
        description="This can be set directly on the class to change the "
        "default context used when parsing a document.",
    )
    id_: DTMI = Field(alias="@id")  # type: ignore[assignment]
    context: IRI | None = Field(alias="@context")
    extends: list[DTMI] | None = None
    contents: list[Command | Component | Property | Relationship | Telemetry | DTMI | CommandV2] | None = None
    schemas: list[Array | Enum | Map | Object] | None = None

    @field_validator("context", mode="before")
    def list_to_string(cls, value: Any) -> Any:
        if isinstance(value, list) and len(value) == 1:
            return value[0]
        return value

    @field_validator("contents", "schemas", mode="before")
    def select_content_type(cls, value: Any, info) -> Any:
        if not isinstance(value, list):
            return value
        context = info.data.get("@context", cls.default_context)
        if isinstance(context, FieldInfo):
            context = context.default
        spec_version = context.rsplit(";", maxsplit=1)[1]
        try:
            cls_by_type = DTDL_CLS_BY_TYPE_BY_SPEC[spec_version]
        except KeyError:
            raise ValueError(f"DTDL Spec v{spec_version} is not supported: {context}") from None
        output: list[DTDLBase] = []
        for item in value:
            if isinstance(item, dict) and (type_ := item.get("@type")):
                if isinstance(type_, str) and (cls_ := cls_by_type.get(type_)) is not None:
                    item = cls_.model_validate(item)
                elif isinstance(type_, list) and len(type_) == 2 and (cls_ := cls_by_type.get(type_[0])) is not None:
                    # In the spec v2, the type of Telemetry and Property can be a list of two strings,
                    # [[Telemetry|Property, "Semantic Type"].
                    from ._unit_lookup import UNIT_TYPE_BY_SEMANTIC_TYPE

                    if (unit_type := UNIT_TYPE_BY_SEMANTIC_TYPE.get(type_[1])) and (unit := item.get("unit")):
                        item["unit"] = {
                            "value": unit,
                            "semanticType": type_[1],
                            "unitType": unit_type,
                        }
                    item = cls_.model_validate(item)
            else:
                warnings.warn(f"Invalid item {item} in {cls.__name__}.contents", stacklevel=2)
            output.append(item)
        return output


DTDL_CLS_BY_TYPE_BY_SPEC: dict[str, dict[str, type[DTDLBase]]] = {}
to_check = list(DTDLBase.__subclasses__())
while to_check:
    cls = to_check.pop()
    to_check.extend(cls.__subclasses__())
    if ABC in cls.__bases__:
        continue
    for spec in cls.spec_version:
        DTDL_CLS_BY_TYPE_BY_SPEC.setdefault(spec, {})[cls.type] = cls
del cls, to_check, spec
