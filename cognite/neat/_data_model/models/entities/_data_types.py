from datetime import date, datetime

from pydantic import Field

from cognite.neat._data_model._constants import XML_SCHEMA_NAMESPACE
from cognite.neat._data_model._identifiers import URI

from ._base import Entity


class UnitEntity(Entity): ...


class EnumCollectionEntity(Entity): ...


class DataType(Entity):
    prefix: str = Field("xsd", frozen=True)

    @property
    def python(self) -> type:
        raise NotImplementedError()

    @property
    def xsd(self) -> URI:
        return XML_SCHEMA_NAMESPACE[self.suffix]


class Boolean(DataType):
    suffix: str = Field("boolean", frozen=True)

    @property
    def python(self) -> type:
        return bool


class Float(DataType):
    suffix: str = Field("float", frozen=True)
    unit: UnitEntity | None = None

    @property
    def python(self) -> type:
        return float


class Double(DataType):
    suffix: str = Field("double", frozen=True)
    unit: UnitEntity | None = None

    @property
    def python(self) -> type:
        return float


class Integer(DataType):
    suffix: str = Field("integer", frozen=True)
    unit: UnitEntity | None = None

    @property
    def python(self) -> type:
        return int


class Long(DataType):
    suffix: str = Field("long", frozen=True)
    unit: UnitEntity | None = None

    @property
    def python(self) -> type:
        return int


class String(DataType):
    suffix: str = Field("string", frozen=True)
    max_text_size: int | None = Field(
        None,
        alias="maxTextSize",
        description="Specifies the maximum size in bytes of the text property, when encoded with utf-8.",
    )

    @property
    def python(self) -> type:
        return str


class AnyURI(DataType):
    suffix: str = Field("anyURI", frozen=True)

    @property
    def python(self) -> type:
        return str


class Date(DataType):
    suffix: str = Field("date", frozen=True)

    @property
    def python(self) -> type:
        return date


class DateTime(DataType):
    suffix: str = Field("dateTime", frozen=True)

    @property
    def python(self) -> type:
        return datetime


class DateTimeStamp(DataType):
    suffix: str = Field("dateTimeStamp", frozen=True)

    @property
    def python(self) -> type:
        return datetime


# CDF Specific extensions of XSD types


class Timeseries(DataType):
    suffix: str = Field("timeseries", frozen=True)


class File(DataType):
    suffix: str = Field("string", frozen=True)


class Sequence(DataType):
    suffix: str = Field("sequence", frozen=True)


class Json(DataType):
    suffix: str = Field("json", frozen=True)

    @property
    def python(self) -> type:
        return dict


class Enum(DataType):
    suffix: str = Field("enum", frozen=True)
    collection: EnumCollectionEntity
    unknown_value: str | None = Field(None, alias="unknownValue")
