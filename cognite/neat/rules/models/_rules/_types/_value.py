from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar, cast

from cognite.client.data_classes.data_modeling import (
    Boolean,
    Date,
    FileReference,
    Float32,
    Float64,
    Int32,
    Int64,
    Json,
    SequenceReference,
    Text,
    TimeSeriesReference,
    Timestamp,
)
from pydantic import BaseModel

from ._base import Entity, EntityTypes


class ValueTypeMapping(BaseModel):
    """Mapping between XSD, Python, DMS and Graphql types."""

    xsd: str
    python: type
    dms: type
    graphql: str
    sql: str


# mypy: ignore-errors
class XSDValueType(Entity):
    """Value type is a data/object type defined as a child of Entity model."""

    type_: ClassVar[EntityTypes] = EntityTypes.xsd_value_type
    mapping: ValueTypeMapping

    @property
    def python(self) -> type:
        """Returns the Python type for a given value type."""
        return cast(ValueTypeMapping, self.mapping).python

    @property
    def xsd(self) -> str:
        """Returns the XSD type for a given value type."""
        return cast(ValueTypeMapping, self.mapping).xsd

    @property
    def dms(self) -> type:
        """Returns the DMS type for a given value type."""
        return cast(ValueTypeMapping, self.mapping).dms

    @property
    def graphql(self) -> str:
        """Returns the Graphql type for a given value type."""
        return cast(ValueTypeMapping, self.mapping).graphql

    @property
    def sql(self) -> str:
        """Returns the SQL type for a given value type."""
        return cast(ValueTypeMapping, self.mapping).sql


class DMSValueType(XSDValueType):
    type_: ClassVar[EntityTypes] = EntityTypes.dms_value_type

    def __str__(self) -> str:
        return self.dms._type


_DATA_TYPES: list[dict] = [
    {"name": "boolean", "python": bool, "GraphQL": "Boolean", "dms": Boolean, "SQL": "BOOLEAN"},
    {"name": "float", "python": float, "GraphQL": "Float", "dms": Float64, "SQL": "FLOAT"},
    {"name": "double", "python": float, "GraphQL": "Float", "dms": Float64, "SQL": "DOUBLE"},
    {"name": "integer", "python": int, "GraphQL": "Int", "dms": Int32, "SQL": "INTEGER"},
    {"name": "nonPositiveInteger", "python": int, "GraphQL": "Int", "dms": Int32, "SQL": "INTEGER"},
    {"name": "nonNegativeInteger", "python": int, "GraphQL": "Int", "dms": Int32, "SQL": "INTEGER"},
    {"name": "negativeInteger", "python": int, "GraphQL": "Int", "dms": Int32, "SQL": "INTEGER"},
    {"name": "long", "python": int, "GraphQL": "Int", "dms": Int64, "SQL": "INTEGER"},
    {"name": "string", "python": str, "GraphQL": "String", "dms": Text, "SQL": "STRING"},
    {"name": "langString", "python": str, "GraphQL": "String", "dms": Text, "SQL": "STRING"},
    {"name": "anyURI", "python": str, "GraphQL": "String", "dms": Text, "SQL": "STRING"},
    {"name": "normalizedString", "python": str, "GraphQL": "String", "dms": Text, "SQL": "STRING"},
    {"name": "token", "python": str, "GraphQL": "String", "dms": Text, "SQL": "STRING"},
    # Graphql does not have a datetime/date type this is CDF specific
    {"name": "dateTime", "python": datetime, "GraphQL": "Timestamp", "dms": Timestamp, "SQL": "TIMESTAMP"},
    {"name": "dateTimeStamp", "python": datetime, "GraphQL": "Timestamp", "dms": Timestamp, "SQL": "TIMESTAMP"},
    {"name": "date", "python": date, "GraphQL": "String", "dms": Date, "SQL": "DATE"},
    # CDF specific types, not in XSD
    {
        "name": "timeseries",
        "python": TimeSeriesReference,
        "GraphQL": "TimeSeries",
        "dms": TimeSeriesReference,
        "SQL": "STRING",
    },
    {"name": "file", "python": FileReference, "GraphQL": "File", "dms": FileReference, "SQL": "STRING"},
    {"name": "sequence", "python": SequenceReference, "GraphQL": "Sequence", "dms": SequenceReference, "SQL": "STRING"},
    {"name": "json", "python": Json, "GraphQL": "Json", "dms": Json, "SQL": "STRING"},
]

_DMS_TYPES: list[dict] = [
    {"name": "boolean", "python": bool, "GraphQL": "Boolean", "dms": Boolean, "SQL": "BOOLEAN"},
    {"name": "float", "python": float, "GraphQL": "Float", "dms": Float32, "SQL": "FLOAT"},
    {"name": "double", "python": float, "GraphQL": "Float", "dms": Float64, "SQL": "DOUBLE"},
    {"name": "integer", "python": int, "GraphQL": "Int", "dms": Int32, "SQL": "INTEGER"},
    {"name": "long", "python": int, "GraphQL": "Int", "dms": Int64, "SQL": "INTEGER"},
    {"name": "string", "python": str, "GraphQL": "String", "dms": Text, "SQL": "STRING"},
    {"name": "dateTimeStamp", "python": datetime, "GraphQL": "Timestamp", "dms": Timestamp, "SQL": "TIMESTAMP"},
    {
        "name": "timeseries",
        "python": TimeSeriesReference,
        "GraphQL": "TimeSeries",
        "dms": TimeSeriesReference,
        "SQL": "STRING",
    },
    {"name": "file", "python": FileReference, "GraphQL": "File", "dms": FileReference, "SQL": "STRING"},
    {"name": "sequence", "python": SequenceReference, "GraphQL": "Sequence", "dms": SequenceReference, "SQL": "STRING"},
    {"name": "json", "python": Json, "GraphQL": "Json", "dms": Json, "SQL": "STRING"},
]

XSD_VALUE_TYPE_MAPPINGS: dict[str, XSDValueType] = {
    data_type["name"]: XSDValueType(
        prefix="xsd",
        suffix=cast(str, data_type["name"]),
        name=cast(str, data_type["name"]),
        mapping=ValueTypeMapping(
            xsd=data_type["name"],
            python=data_type["python"],
            dms=data_type["dms"],
            graphql=data_type["GraphQL"],
            sql=data_type["SQL"],
        ),
    )
    for data_type in _DATA_TYPES
}

DMS_VALUE_TYPE_MAPPINGS: dict[str, DMSValueType] = {
    data_type["dms"]._type.casefold(): DMSValueType(
        prefix="dms",
        suffix=data_type["dms"]._type.casefold(),
        name=data_type["dms"]._type.casefold(),
        mapping=ValueTypeMapping(
            xsd=data_type["name"],
            python=data_type["python"],
            dms=data_type["dms"],
            graphql=data_type["GraphQL"],
            sql=data_type["SQL"],
        ),
    )
    for data_type in _DMS_TYPES
}
