from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import cast

from cognite.neat.rules.type_mapping import _DATA_TYPES

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum


class ValueTypeCategory(StrEnum):
    data = "data"
    object = "object"


@dataclass
class ValueTypeMapping:
    xsd: str | type
    python: str | type
    dms: str | type
    graphql: str | type


@dataclass
class ValueType:
    prefix: str
    name: str
    category: str
    mapping: ValueTypeMapping | None = None

    @property
    def python(self):
        if self.category == "data":
            return self.mapping.python
        else:
            return None

    @property
    def xsd(self):
        if self.category == "data":
            return self.mapping.xsd
        else:
            return None

    @property
    def dms(self):
        if self.category == "data":
            return self.mapping.dms
        else:
            return None

    @property
    def graphql(self):
        if self.category == "data":
            return self.mapping.graphql
        else:
            return None


PROPERTY_VALUE_TYPES = {
    data_type["name"]: ValueType(
        "xsd",
        cast(str, data_type["name"]),
        "data",
        ValueTypeMapping(
            data_type["name"],
            data_type["python"],
            data_type["dms"],
            data_type["GraphQL"],
        ),
    )
    for data_type in _DATA_TYPES
}
