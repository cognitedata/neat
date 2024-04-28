import sys
from datetime import date, datetime
from typing import Any, ClassVar

from cognite.client.data_classes import data_modeling as dms
from pydantic import BaseModel, model_serializer, model_validator
from pydantic_core.core_schema import ValidationInfo

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Literal(BaseModel):
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
    def _load(cls, data: Any, info: ValidationInfo) -> Any:
        if isinstance(data, cls | dict):
            return data
        elif isinstance(data, str):
            try:
                return _LITERAL_BY_NAME[data.casefold()]()
            except KeyError:
                raise ValueError(f"Unknown literal type: {data}") from None
        raise ValueError(f"Cannot load {cls.__name__} from {data}")

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self))


class Boolean(Literal):
    name = "boolean"
    python = bool
    dms = dms.Boolean
    graphql = "Boolean"
    xsd = "xsd:boolean"
    sql = "BOOLEAN"


class Float(Literal):
    name = "float"
    python = float
    dms = dms.Float32
    graphql = "Float"
    xsd = "xsd:float"
    sql = "FLOAT"


class Double(Literal):
    name = "double"
    python = float
    dms = dms.Float64
    graphql = "Float"
    xsd = "xsd:double"
    sql = "FLOAT"


class Integer(Literal):
    name = "integer"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "xsd:integer"
    sql = "INTEGER"


class NonPositiveInteger(Literal):
    name = "nonPositiveInteger"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "xsd:nonPositiveInteger"
    sql = "INTEGER"


class NonNegativeInteger(Literal):
    name = "nonNegativeInteger"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "xsd:nonNegativeInteger"
    sql = "INTEGER"


class Long(Literal):
    name = "long"
    python = int
    dms = dms.Int64
    graphql = "Int"
    xsd = "xsd:long"
    sql = "BIGINT"


class AnyURI(Literal):
    name = "anyURI"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:anyURI"
    sql = "STRING"


class NormalizedString(Literal):
    name = "normalizedString"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:normalizedString"
    sql = "STRING"


class Token(Literal):
    name = "token"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:string"
    sql = "STRING"


class DateTime(Literal):
    name = "dateTime"
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "xsd:dateTimeStamp"
    sql = "TIMESTAMP"


class DateTimeStamp(Literal):
    name = "dateTimeStamp"
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "xsd:dateTimeStamp"
    sql = "TIMESTAMP"


class Date(Literal):
    name = "date"
    python = date
    dms = dms.Date
    graphql = "String"
    xsd = "xsd:date"
    sql = "DATE"


class PlainLiteral(Literal):
    name = "PlainLiteral"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "xsd:string"
    sql = "STRING"


#
# class Literal(Literal):


class Timeseries(Literal):
    name = "timeseries"
    python = dms.TimeSeriesReference
    dms = dms.TimeSeriesReference
    graphql = "TimeSeries"
    xsd = "xsd:string"
    sql = "STRING"


class File(Literal):
    name = "file"
    python = dms.FileReference
    dms = dms.FileReference
    graphql = "File"
    xsd = "xsd:string"
    sql = "STRING"


class Sequence(Literal):
    name = "sequence"
    python = dms.SequenceReference
    dms = dms.SequenceReference
    graphql = "Sequence"
    xsd = "xsd:string"
    sql = "STRING"


class Json(Literal):
    name = "json"
    python = dms.Json
    dms = dms.Json
    graphql = "Json"
    xsd = "xsd:string"
    sql = "STRING"


_LITERAL_BY_NAME = {cls.name.casefold(): cls for cls in Literal.__subclasses__()}
