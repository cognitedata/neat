from __future__ import annotations

from datetime import date, datetime
from typing import cast

from cognite.client.data_classes.data_modeling import (
    Boolean,
    Date,
    FileReference,
    Float64,
    Int32,
    Int64,
    Json,
    PropertyType,
    SequenceReference,
    Text,
    TimeSeriesReference,
    Timestamp,
)
from pydantic import BaseModel

from cognite.neat.rules.models._base import Entity, EntityTypes


class ValueTypeMapping(BaseModel):
    """Mapping between XSD, Python, DMS and Graphql types."""

    xsd: str
    python: type
    dms: type
    graphql: str


class ValueType(Entity):
    """Value type is a data/object type defined as a child of Entity model."""

    mapping: ValueTypeMapping | None = None

    @property
    def python(self) -> type | None:
        """Returns the Python type for a given value type."""
        if self.type_ == EntityTypes.data_value_type:
            return cast(ValueTypeMapping, self.mapping).python
        else:
            return None

    @property
    def xsd(self) -> str | None:
        """Returns the XSD type for a given value type."""
        if self.type_ == EntityTypes.data_value_type:
            return cast(ValueTypeMapping, self.mapping).xsd
        else:
            return None

    @property
    def dms(self) -> type | None:
        """Returns the DMS type for a given value type."""
        if self.type_ == EntityTypes.data_value_type:
            return cast(ValueTypeMapping, self.mapping).dms
        else:
            return None

    @property
    def graphql(self) -> str | None:
        """Returns the Graphql type for a given value type."""
        if self.type_ == EntityTypes.data_value_type:
            return cast(ValueTypeMapping, self.mapping).graphql
        else:
            return None


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
    {"name": "sequence", "python": SequenceReference, "GraphQL": "Sequence", "dms": TimeSeriesReference},
    {"name": "json", "python": Json, "GraphQL": "Json", "dms": Json},
]

XSD_VALUE_TYPE_MAPPINGS: dict[str, ValueType] = {
    data_type["name"]: ValueType(
        prefix="xsd",
        suffix=cast(str, data_type["name"]),
        name=cast(str, data_type["name"]),
        type_=EntityTypes.data_value_type,
        mapping=ValueTypeMapping(
            xsd=data_type["name"],
            python=data_type["python"],
            dms=data_type["dms"],
            graphql=data_type["GraphQL"],
        ),
    )
    for data_type in _DATA_TYPES
}


DMS_VALUE_TYPE_MAPPINGS: dict[type[PropertyType], ValueType] = {}
for value_type in XSD_VALUE_TYPE_MAPPINGS.values():
    if value_type.dms not in DMS_VALUE_TYPE_MAPPINGS:
        DMS_VALUE_TYPE_MAPPINGS[cast(type[PropertyType], value_type.dms)] = cast(ValueType, value_type)
