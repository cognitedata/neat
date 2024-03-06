import json
import warnings
from abc import ABC
from collections.abc import Sequence
from pathlib import Path
from typing import Any, ClassVar, Literal, TypeAlias, overload

from pydantic import BaseModel, Field, field_validator

from cognite.neat.rules.models._rules import InformationRules, RoleTypes
from cognite.neat.rules.models._rules.base import SheetList
from cognite.neat.rules.validation import IssueList

from ._base import BaseImporter

# Todo Annotated
DTMI: TypeAlias = str

IRI: TypeAlias = str

from cognite.neat.rules._shared import Rules


class DTDLBase(BaseModel, ABC):
    type: ClassVar[str]
    id_: DTMI | None = Field(None, alias="@id")
    comment: str | None = None
    display_name: str | None = Field(None, alias="displayName")
    description: str | None = None


class DTDLImporter(BaseImporter):
    """Importer for DTDL (Digital Twin Definition Language) files. It can import a directory containing DTDL files and
    convert them to InformationRules.

    The DTDL v3 stanard is supported and defined at
    https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v3/DTDL.v3.md

    """

    def __init__(self, items: Sequence[DTDLBase], title: str | None = None):
        self._items = items
        self.title = title

    @classmethod
    def from_directory(cls, directory: Path) -> "DTDLImporter":
        items: list[DTDLBase] = []
        for filepath in directory.glob("**/*.json"):
            raw = json.loads(filepath.read_text())
            if isinstance(raw, dict):
                raw_list = [raw]
            elif isinstance(raw, list):
                raw_list = raw
            else:
                raise ValueError(f"Invalid json file {filepath}")
            for item in raw_list:
                if not (type_ := item.get("@type")):
                    warnings.warn(f"Invalid json file {filepath}. Missing '@type' key.", stacklevel=2)
                    continue
                cls_ = DTDL_CLS_BY_TYPE.get(type_)
                if cls_ is None:
                    warnings.warn(f"Invalid json file {filepath}. Unknown '@type' {type_}", stacklevel=2)
                    continue
                items.append(cls_.model_validate(item))
        return cls(items, directory.name)

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        IssueList([])
        properties = SheetList(data=[])
        classes = SheetList(data=[])

        {item.id_: item for item in self._items if item.id_}
        for item in self._items:
            if isinstance(item, Interface):
                ...

        InformationRules(
            metadata=self._default_metadata(),
            properties=properties,
            classes=classes,
        )


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
