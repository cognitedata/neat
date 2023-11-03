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

_DATA_TYPES: list[dict[str, str | type]] = [
    {"name": "boolean", "python": bool, "GraphQL": "Boolean", "dms": Boolean},
    {"name": "float", "python": float, "GraphQL": "Float", "dms": Float64},
    {"name": "integer", "python": int, "GraphQL": "Int", "dms": Int32},
    {"name": "nonPositiveInteger", "python": int, "GraphQL": "Int", "dms": Int32},
    {"name": "nonNegativeInteger", "python": int, "GraphQL": "Int", "dms": Int32},
    {"name": "negativeInteger", "python": "int", "GraphQL": "Int", "dms": Int32},
    {"name": "long", "python": int, "GraphQL": "Int", "dms": Int64},
    {"name": "string", "python": str, "GraphQL": "String", "dms": Text},
    {"name": "anyURI", "python": str, "GraphQL": "String", "dms": Text},
    {"name": "normalizedString", "python": str, "GraphQL": "String", "dms": Text},
    {"name": "token", "python": str, "GraphQL": "String", "dms": Text},
    # Graphql does not have a datetime/date type this is CDF specific
    {"name": "dateTime", "python": datetime, "GraphQL": "Timestamp", "dms": Timestamp},
    {"name": "date", "python": date, "GraphQL": "String", "dms": Date},
    # CDF specific types, not in XSD
    {"name": "timeseries", "python": TimeSeriesReference, "GraphQL": "TimeSeries", "dms": TimeSeriesReference},
    {"name": "file", "python": FileReference, "GraphQL": "File", "dms": FileReference},
    {"name": "sequence", "python": SequenceReference, "GraphQL": "Sequence", "dms": TimeSeriesReference},
    {"name": "json", "python": Json, "GraphQL": "Json", "dms": Json},
]


# mapping of XSD types to Python and GraphQL types
DATA_TYPE_MAPPING: dict[str, dict[str, type | str]] = {
    cast(str, entry["name"]): {key: entry[key] for key in ["python", "GraphQL", "dms"]} for entry in _DATA_TYPES
}


DMS_TO_DATA_TYPE: dict[type[PropertyType], str] = {}
for entry in _DATA_TYPES:
    if entry["dms"] not in DMS_TO_DATA_TYPE:
        DMS_TO_DATA_TYPE[cast(type[PropertyType], entry["dms"])] = cast(str, entry["name"])


def type_to_target_convention(type_: str, target_type_convention: str) -> type | str | PropertyType:
    """Returns the GraphQL type for a given XSD type."""
    return DATA_TYPE_MAPPING[type_][target_type_convention]
