import re
import sys
import typing
from datetime import date, datetime
from typing import Any, ClassVar

from cognite.client.data_classes import data_modeling as dms
from cognite.client.data_classes.data_modeling.data_types import Enum as DMSEnum
from pydantic import BaseModel, Field, model_serializer, model_validator
from pydantic.functional_validators import ModelWrapValidatorHandler
from rdflib import URIRef

from cognite.neat.v0.core._constants import XML_SCHEMA_NAMESPACE
from cognite.neat.v0.core._data_model._constants import (
    SPLIT_ON_COMMA_PATTERN,
    SPLIT_ON_EQUAL_PATTERN,
)
from cognite.neat.v0.core._data_model.models.entities._single_value import (
    ConceptEntity,
    UnitEntity,
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

# This patterns matches a string that is a data type, with optional content in parentheses.
# For example, it matches "float(unit=power:megaw)" as name="float" and content="unit=power:megaw"
_DATATYPE_PATTERN = re.compile(r"^(?P<name>[^(:]*)(\((?P<content>.+)\))?$")


class DataType(BaseModel):
    python: ClassVar[type]
    dms: ClassVar[type[dms.PropertyType]]
    graphql: ClassVar[str]
    xsd: ClassVar[str]
    sql: ClassVar[str]
    # Repeat all here, just to make mypy happy
    name: typing.Literal[
        "boolean",
        "token",
        "float",
        "double",
        "decimal",
        "integer",
        "nonPositiveInteger",
        "nonNegativeInteger",
        "long",
        "negativeInteger",
        "string",
        "langString",
        "anyURI",
        "normalizedString",
        "dateTime",
        "timestamp",
        "dateTimeStamp",
        "date",
        "plainLiteral",
        "Literal",
        "timeseries",
        "file",
        "sequence",
        "json",
        "enum",
        "",
    ] = ""

    @classmethod
    def load(cls, data: Any) -> Self:
        return cls.model_validate(data)

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)

    @model_validator(mode="wrap")
    def _load(cls, value: Any, handler: ModelWrapValidatorHandler["DataType"]) -> Any:
        if cls is not DataType or isinstance(value, DataType):
            # This is a subclass, let the subclass handle it
            return handler(value)
        elif isinstance(value, str) and (match := _DATATYPE_PATTERN.match(value)):
            name = match.group("name").casefold()
            cls_: type[DataType]
            if name in _DATA_TYPE_BY_DMS_TYPE:
                cls_ = _DATA_TYPE_BY_DMS_TYPE[name]
            elif name in _DATA_TYPE_BY_NAME:
                cls_ = _DATA_TYPE_BY_NAME[name]
            else:
                raise ValueError(f"Unknown data type: {value}") from None
            extra_args: dict[str, Any] = {}
            if content := match.group("content"):
                extra_args = dict(
                    SPLIT_ON_EQUAL_PATTERN.split(pair.strip()) for pair in SPLIT_ON_COMMA_PATTERN.split(content)
                )
                # Todo? Raise warning if extra_args contains keys that are not in the model fields
            instance = cls_(**extra_args)
            created = handler(instance)
            return created
        raise ValueError(f"Cannot load {cls.__name__} from {value}")

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return self._suffix_extra_args(self.model_fields["name"].default)

    def _suffix_extra_args(self, base: str) -> str:
        extra_fields: dict[str, str] = {}
        for field_id, field_ in self.model_fields.items():
            if field_id == "name":
                continue
            value = getattr(self, field_id)
            if value is None:
                continue
            extra_fields[field_.alias or field_id] = str(value)
        if extra_fields:
            content = ",".join(f"{key}={value}" for key, value in sorted(extra_fields.items(), key=lambda x: x[0]))
            return f"{base}({content})"
        return base

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self)) and str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))

    @classmethod
    def is_data_type(cls, value: str) -> bool:
        if match := _DATATYPE_PATTERN.match(value):
            name = match.group("name").casefold()
            return name in _DATA_TYPE_BY_NAME or name in _DATA_TYPE_BY_DMS_TYPE
        return False

    @classmethod
    def as_xml_uri_ref(cls) -> URIRef:
        return XML_SCHEMA_NAMESPACE[cls.xsd]

    @classmethod
    def convert_value(cls, value: Any) -> Any:
        if not issubclass(cls, Boolean):
            return cls.python(value)
        elif isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes"}
        else:
            return bool(value)


class Boolean(DataType):
    python = bool
    dms = dms.Boolean
    graphql = "Boolean"
    xsd = "boolean"
    sql = "BOOLEAN"
    name: typing.Literal["boolean"] = "boolean"


class Float(DataType):
    python = float
    dms = dms.Float32
    graphql = "Float"
    xsd = "float"
    sql = "FLOAT"

    name: typing.Literal["float"] = "float"
    unit: UnitEntity | None = None


class Double(DataType):
    python = float
    dms = dms.Float64
    graphql = "Float"
    xsd = "double"
    sql = "FLOAT"

    name: typing.Literal["double"] = "double"
    unit: UnitEntity | None = None


class Decimal(DataType):
    python = float
    dms = dms.Float64
    graphql = "Float"
    xsd = "decimal"
    sql = "FLOAT"

    name: typing.Literal["decimal"] = "decimal"
    unit: UnitEntity | None = None


class Integer(DataType):
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "integer"
    sql = "INTEGER"

    name: typing.Literal["integer"] = "integer"


class NonPositiveInteger(DataType):
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "nonPositiveInteger"
    sql = "INTEGER"

    name: typing.Literal["nonPositiveInteger"] = "nonPositiveInteger"


class NonNegativeInteger(DataType):
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "nonNegativeInteger"
    sql = "INTEGER"

    name: typing.Literal["nonNegativeInteger"] = "nonNegativeInteger"


class NegativeInteger(DataType):
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "negativeInteger"
    sql = "INTEGER"

    name: typing.Literal["negativeInteger"] = "negativeInteger"


class Long(DataType):
    python = int
    dms = dms.Int64
    graphql = "Int"
    xsd = "long"
    sql = "BIGINT"

    name: typing.Literal["long"] = "long"


class String(DataType):
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "string"
    sql = "STRING"

    name: typing.Literal["string"] = "string"
    max_text_size: int | None = Field(
        None,
        alias="maxTextSize",
        description="Specifies the maximum size in bytes of the text property, when encoded with utf-8.",
    )


class LangString(DataType):
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "string"
    sql = "STRING"

    name: typing.Literal["langString"] = "langString"
    max_text_size: int | None = Field(
        None,
        alias="maxTextSize",
        description="Specifies the maximum size in bytes of the text property, when encoded with utf-8.",
    )


class AnyURI(DataType):
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "anyURI"
    sql = "STRING"

    name: typing.Literal["anyURI"] = "anyURI"


class NormalizedString(DataType):
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "normalizedString"
    sql = "STRING"

    name: typing.Literal["normalizedString"] = "normalizedString"


class Token(DataType):
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "string"
    sql = "STRING"

    name: typing.Literal["token"] = "token"


class DateTime(DataType):
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "dateTime"
    sql = "TIMESTAMP"

    name: typing.Literal["dateTime"] = "dateTime"


class Timestamp(DataType):
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "dateTimeStamp"
    sql = "TIMESTAMP"

    name: typing.Literal["timestamp"] = "timestamp"


class DateTimeStamp(DataType):
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "dateTimeStamp"
    sql = "TIMESTAMP"

    name: typing.Literal["dateTimeStamp"] = "dateTimeStamp"


class Date(DataType):
    python = date
    dms = dms.Date
    graphql = "String"
    xsd = "date"
    sql = "DATE"

    name: typing.Literal["date"] = "date"


class PlainLiteral(DataType):
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "plainLiteral"
    sql = "STRING"

    name: typing.Literal["plainLiteral"] = "plainLiteral"


class Literal(DataType):
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "string"
    sql = "STRING"

    name: typing.Literal["Literal"] = "Literal"


class Timeseries(DataType):
    python = str
    dms = dms.TimeSeriesReference
    graphql = "TimeSeries"
    xsd = "string"
    sql = "STRING"

    name: typing.Literal["timeseries"] = "timeseries"


class File(DataType):
    python = str
    dms = dms.FileReference
    graphql = "File"
    xsd = "string"
    sql = "STRING"

    name: typing.Literal["file"] = "file"


class Sequence(DataType):
    python = str
    dms = dms.SequenceReference
    graphql = "Sequence"
    xsd = "string"
    sql = "STRING"

    name: typing.Literal["sequence"] = "sequence"


class Json(DataType):
    python = dict
    dms = dms.Json
    graphql = "Json"
    xsd = "json"
    sql = "STRING"

    name: typing.Literal["json"] = "json"


class Enum(DataType):
    python = str
    dms = DMSEnum
    graphql = "Enum"
    xsd = "string"
    sql = "STRING"

    name: typing.Literal["enum"] = "enum"

    collection: ConceptEntity
    unknown_value: str | None = Field(None, alias="unknownValue")


_DATA_TYPE_BY_NAME = {cls.model_fields["name"].default.casefold(): cls for cls in DataType.__subclasses__()}
_seen = set()
_DATA_TYPE_BY_DMS_TYPE = {
    cls.dms._type.casefold(): cls
    for cls in DataType.__subclasses__()
    if cls.dms._type not in _seen and not _seen.add(cls.dms._type)  # type: ignore[func-returns-value]
}
del _seen
_XSD_TYPES = {cls_.xsd for cls_ in _DATA_TYPE_BY_NAME.values()}
