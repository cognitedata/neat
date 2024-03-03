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


class DMSValueType(XSDValueType):
    type_: ClassVar[EntityTypes] = EntityTypes.dms_value_type

    def __str__(self) -> str:
        return self.dms._type


_DATA_TYPES: list[dict] = [
    {"name": "boolean", "python": bool, "GraphQL": "Boolean", "dms": Boolean},
    {"name": "float", "python": float, "GraphQL": "Float", "dms": Float64},
    {"name": "double", "python": float, "GraphQL": "Float", "dms": Float64},
    {"name": "integer", "python": int, "GraphQL": "Int", "dms": Int32},
    {"name": "nonPositiveInteger", "python": int, "GraphQL": "Int", "dms": Int32},
    {"name": "nonNegativeInteger", "python": int, "GraphQL": "Int", "dms": Int32},
    {"name": "negativeInteger", "python": int, "GraphQL": "Int", "dms": Int32},
    {"name": "long", "python": int, "GraphQL": "Int", "dms": Int64},
    {"name": "string", "python": str, "GraphQL": "String", "dms": Text},
    {"name": "langString", "python": str, "GraphQL": "String", "dms": Text},
    {"name": "anyURI", "python": str, "GraphQL": "String", "dms": Text},
    {"name": "normalizedString", "python": str, "GraphQL": "String", "dms": Text},
    {"name": "token", "python": str, "GraphQL": "String", "dms": Text},
    # Graphql does not have a datetime/date type this is CDF specific
    {"name": "dateTime", "python": datetime, "GraphQL": "Timestamp", "dms": Timestamp},
    {"name": "dateTimeStamp", "python": datetime, "GraphQL": "Timestamp", "dms": Timestamp},
    {"name": "date", "python": date, "GraphQL": "String", "dms": Date},
    # CDF specific types, not in XSD
    {"name": "timeseries", "python": TimeSeriesReference, "GraphQL": "TimeSeries", "dms": TimeSeriesReference},
    {"name": "file", "python": FileReference, "GraphQL": "File", "dms": FileReference},
    {"name": "sequence", "python": SequenceReference, "GraphQL": "Sequence", "dms": SequenceReference},
    {"name": "json", "python": Json, "GraphQL": "Json", "dms": Json},
]

_DMS_TYPES: list[dict] = [
    {"name": "boolean", "python": bool, "GraphQL": "Boolean", "dms": Boolean},
    {"name": "float", "python": float, "GraphQL": "Float", "dms": Float32},
    {"name": "double", "python": float, "GraphQL": "Float", "dms": Float64},
    {"name": "integer", "python": int, "GraphQL": "Int", "dms": Int32},
    {"name": "long", "python": int, "GraphQL": "Int", "dms": Int64},
    {"name": "string", "python": str, "GraphQL": "String", "dms": Text},
    {"name": "dateTimeStamp", "python": datetime, "GraphQL": "Timestamp", "dms": Timestamp},
    {"name": "timeseries", "python": TimeSeriesReference, "GraphQL": "TimeSeries", "dms": TimeSeriesReference},
    {"name": "file", "python": FileReference, "GraphQL": "File", "dms": FileReference},
    {"name": "sequence", "python": SequenceReference, "GraphQL": "Sequence", "dms": SequenceReference},
    {"name": "json", "python": Json, "GraphQL": "Json", "dms": Json},
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
        ),
    )
    for data_type in _DMS_TYPES
}
