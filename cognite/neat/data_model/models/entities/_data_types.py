import sys
from datetime import date, datetime

from pydantic import Field

from cognite.neat.data_model._constants import XML_SCHEMA_NAMESPACE
from cognite.neat.data_model._identifiers import URI

from ._base import Entity

if sys.version_info >= (3, 11):
    pass
else:
    pass


class UnitEntity(Entity):
    prefix: str
    suffix: str


class EnumCollectionEntity(Entity):
    prefix: str
    suffix: str


class DataType(Entity):
    prefix: str = "xsd"

    @property
    def python(self) -> type:
        raise NotImplementedError()

    @property
    def xsd(self) -> URI:
        return XML_SCHEMA_NAMESPACE[self.suffix]


class Boolean(DataType):
    suffix: str = "boolean"

    @property
    def python(self) -> type:
        return bool


class Float(DataType):
    suffix: str = "float"
    unit: UnitEntity | None = None

    @property
    def python(self) -> type:
        return float


class Double(DataType):
    suffix: str = "double"
    unit: UnitEntity | None = None

    @property
    def python(self) -> type:
        return float


class Integer(DataType):
    suffix: str = "integer"
    unit: UnitEntity | None = None

    @property
    def python(self) -> type:
        return int


class Long(DataType):
    suffix: str = "long"
    unit: UnitEntity | None = None

    @property
    def python(self) -> type:
        return int


class String(DataType):
    suffix: str = "string"
    max_text_size: int | None = Field(
        None,
        alias="maxTextSize",
        description="Specifies the maximum size in bytes of the text property, when encoded with utf-8.",
    )

    @property
    def python(self) -> type:
        return str


class AnyURI(DataType):
    suffix: str = "anyURI"

    @property
    def python(self) -> type:
        return str


class Date(DataType):
    suffix: str = "date"

    @property
    def python(self) -> type:
        return date


class DateTime(DataType):
    suffix: str = "dateTime"

    @property
    def python(self) -> type:
        return datetime


class DateTimeStamp(DataType):
    suffix: str = "dateTimeStamp"

    @property
    def python(self) -> type:
        return datetime


# CDF Specific extensions of XSD types


class Timeseries(DataType):
    suffix: str = "timeseries"


class File(DataType):
    suffix: str = "string"


class Sequence(DataType):
    suffix: str = "sequence"


class Json(DataType):
    suffix: str = "json"

    @property
    def python(self) -> type:
        return dict


class Enum(DataType):
    suffix: str = "enum"
    collection: EnumCollectionEntity
    unknown_value: str | None = Field(None, alias="unknownValue")
