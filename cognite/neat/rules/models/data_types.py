import sys
from datetime import date, datetime
from typing import Any, ClassVar

from cognite.client.data_classes import data_modeling as dms
from pydantic import BaseModel, model_serializer, model_validator
from pydantic.functional_validators import ModelWrapValidatorHandler

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class DataType(BaseModel):
    name: ClassVar[str]
    python: ClassVar[type]
    dms: ClassVar[type[dms.PropertyType]]
    graphql: ClassVar[str]
    xsd: ClassVar[str]
    sql: ClassVar[str]

    @classmethod
    def load(cls, data: Any) -> Self:
        return cls.model_validate(data)

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)

    @model_validator(mode="wrap")
    def _load(cls, value: Any, handler: ModelWrapValidatorHandler["DataType"]) -> Any:
        if isinstance(value, cls | dict):
            return value
        elif isinstance(value, str):
            try:
                return _DATA_TYPE_BY_NAME[value.casefold()]()
            except KeyError:
                raise ValueError(f"Unknown literal type: {value}") from None
        raise ValueError(f"Cannot load {cls.__name__} from {value}")

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self))


class Boolean(DataType):
    name = "boolean"
    python = bool
    dms = dms.Boolean
    graphql = "Boolean"
    xsd = "xsd:boolean"
    sql = "BOOLEAN"


class Float(DataType):
    name = "float"
    python = float
    dms = dms.Float32
    graphql = "Float"
    xsd = "xsd:float"
    sql = "FLOAT"


class Double(DataType):
    name = "double"
    python = float
    dms = dms.Float64
    graphql = "Float"
    xsd = "xsd:double"
    sql = "FLOAT"


class Integer(DataType):
    name = "integer"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "xsd:integer"
    sql = "INTEGER"


class NonPositiveInteger(DataType):
    name = "nonPositiveInteger"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "xsd:nonPositiveInteger"
    sql = "INTEGER"


class NonNegativeInteger(DataType):
    name = "nonNegativeInteger"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "xsd:nonNegativeInteger"
    sql = "INTEGER"


class NegativeInteger(DataType):
    name = "negativeInteger"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "xsd:negativeInteger"
    sql = "INTEGER"


class Long(DataType):
    name = "long"
    python = int
    dms = dms.Int64
    graphql = "Int"
    xsd = "xsd:long"
    sql = "BIGINT"


class String(DataType):
    name = "string"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:string"
    sql = "STRING"


class LangString(DataType):
    name = "langString"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:string"
    sql = "STRING"


class AnyURI(DataType):
    name = "anyURI"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:anyURI"
    sql = "STRING"


class NormalizedString(DataType):
    name = "normalizedString"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:normalizedString"
    sql = "STRING"


class Token(DataType):
    name = "token"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:string"
    sql = "STRING"


class DateTime(DataType):
    name = "dateTime"
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "xsd:dateTimeStamp"
    sql = "TIMESTAMP"


class DateTimeStamp(DataType):
    name = "dateTimeStamp"
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "xsd:dateTimeStamp"
    sql = "TIMESTAMP"


class Timestamp(DataType):
    name = "timestamp"
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "xsd:dateTimeStamp"
    sql = "TIMESTAMP"


class Date(DataType):
    name = "date"
    python = date
    dms = dms.Date
    graphql = "String"
    xsd = "xsd:date"
    sql = "DATE"


class PlainLiteral(DataType):
    name = "PlainLiteral"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:string"
    sql = "STRING"


class Literal(DataType):
    name = "Literal"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:string"
    sql = "STRING"


class Timeseries(DataType):
    name = "timeseries"
    python = dms.TimeSeriesReference
    dms = dms.TimeSeriesReference
    graphql = "TimeSeries"
    xsd = "xsd:string"
    sql = "STRING"


class File(DataType):
    name = "file"
    python = dms.FileReference
    dms = dms.FileReference
    graphql = "File"
    xsd = "xsd:string"
    sql = "STRING"


class Sequence(DataType):
    name = "sequence"
    python = dms.SequenceReference
    dms = dms.SequenceReference
    graphql = "Sequence"
    xsd = "xsd:string"
    sql = "STRING"


class Json(DataType):
    name = "json"
    python = dms.Json
    dms = dms.Json
    graphql = "Json"
    xsd = "xsd:string"
    sql = "STRING"


_DATA_TYPE_BY_NAME = {cls.name.casefold(): cls for cls in DataType.__subclasses__()}
