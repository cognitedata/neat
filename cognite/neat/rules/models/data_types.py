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
    # These are necessary for Pydantic to work
    # pydantic gets confused as we have no fields.
    __pydantic_extra__ = None
    __pydantic_fields_set__ = set()
    __pydantic_private__ = {}

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
            value_standardized = value.casefold()
            if cls_ := _DATA_TYPE_BY_DMS_TYPE.get(value_standardized):
                return cls_()
            elif cls_ := _DATA_TYPE_BY_NAME.get(value_standardized):
                return cls_()
            raise ValueError(f"Unknown literal type: {value}") from None
        raise ValueError(f"Cannot load {cls.__name__} from {value}")

    @model_serializer(when_used="unless-none", return_type=str)
    def as_str(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, type(self))

    def __hash__(self) -> int:
        return hash(str(self))

    @classmethod
    def is_data_type(cls, value: str) -> bool:
        return value.casefold() in _DATA_TYPE_BY_NAME or value.casefold() in _DATA_TYPE_BY_DMS_TYPE


class Boolean(DataType):
    name = "boolean"
    python = bool
    dms = dms.Boolean
    graphql = "Boolean"
    xsd = "boolean"
    sql = "BOOLEAN"


class Float(DataType):
    name = "float"
    python = float
    dms = dms.Float32
    graphql = "Float"
    xsd = "float"
    sql = "FLOAT"


class Double(DataType):
    name = "double"
    python = float
    dms = dms.Float64
    graphql = "Float"
    xsd = "double"
    sql = "FLOAT"


class Integer(DataType):
    name = "integer"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "integer"
    sql = "INTEGER"


class NonPositiveInteger(DataType):
    name = "nonPositiveInteger"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "nonPositiveInteger"
    sql = "INTEGER"


class NonNegativeInteger(DataType):
    name = "nonNegativeInteger"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "nonNegativeInteger"
    sql = "INTEGER"


class NegativeInteger(DataType):
    name = "negativeInteger"
    python = int
    dms = dms.Int32
    graphql = "Int"
    xsd = "negativeInteger"
    sql = "INTEGER"


class Long(DataType):
    name = "long"
    python = int
    dms = dms.Int64
    graphql = "Int"
    xsd = "long"
    sql = "BIGINT"


class String(DataType):
    name = "string"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "string"
    sql = "STRING"


class LangString(DataType):
    name = "langString"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "string"
    sql = "STRING"


class AnyURI(DataType):
    name = "anyURI"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "anyURI"
    sql = "STRING"


class NormalizedString(DataType):
    name = "normalizedString"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "normalizedString"
    sql = "STRING"


class Token(DataType):
    name = "token"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "string"
    sql = "STRING"


class DateTime(DataType):
    name = "dateTime"
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "dateTimeStamp"
    sql = "TIMESTAMP"


class Timestamp(DataType):
    name = "timestamp"
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "dateTimeStamp"
    sql = "TIMESTAMP"


class DateTimeStamp(DataType):
    name = "dateTimeStamp"
    python = datetime
    dms = dms.Timestamp
    graphql = "Timestamp"
    xsd = "dateTimeStamp"
    sql = "TIMESTAMP"


class Date(DataType):
    name = "date"
    python = date
    dms = dms.Date
    graphql = "String"
    xsd = "date"
    sql = "DATE"


class PlainLiteral(DataType):
    name = "PlainLiteral"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "plainLiteral"
    sql = "STRING"


class Literal(DataType):
    name = "Literal"
    python = str
    dms = dms.Text
    graphql = "String"
    xsd = "string"
    sql = "STRING"


class Timeseries(DataType):
    name = "timeseries"
    python = dms.TimeSeriesReference
    dms = dms.TimeSeriesReference
    graphql = "TimeSeries"
    xsd = "string"
    sql = "STRING"


class File(DataType):
    name = "file"
    python = dms.FileReference
    dms = dms.FileReference
    graphql = "File"
    xsd = "string"
    sql = "STRING"


class Sequence(DataType):
    name = "sequence"
    python = dms.SequenceReference
    dms = dms.SequenceReference
    graphql = "Sequence"
    xsd = "string"
    sql = "STRING"


class Json(DataType):
    name = "json"
    python = dms.Json
    dms = dms.Json
    graphql = "Json"
    xsd = "string"
    sql = "STRING"


_DATA_TYPE_BY_NAME = {cls.name.casefold(): cls for cls in DataType.__subclasses__()}
_seen = set()
_DATA_TYPE_BY_DMS_TYPE = {
    cls.dms._type.casefold(): cls
    for cls in DataType.__subclasses__()
    if cls.dms._type not in _seen and not _seen.add(cls.dms._type)  # type: ignore[func-returns-value]
}
del _seen
_XSD_TYPES = {cls_.xsd for cls_ in _DATA_TYPE_BY_NAME.values()}
