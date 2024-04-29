from typing import Any

import pytest
from pydantic import BaseModel, Field

from cognite.neat.rules.models.data_types import (
    Boolean,
    DataType,
    Double,
    Float,
    Integer,
    Literal,
    NonNegativeInteger,
    NonPositiveInteger,
)
from cognite.neat.rules.models.entities import ClassEntity


class DemoProperty(BaseModel):
    property_: str = Field(alias="property")
    value_type: DataType | ClassEntity = Field(alias="valueType")

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class TestDataTypes:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("boolean", Boolean()),
            ("float", Float()),
            ("double", Double()),
            ("integer", Integer()),
            ("nonPositiveInteger", NonPositiveInteger()),
            ("nonNegativeInteger", NonNegativeInteger()),
        ],
    )
    def test_load(self, raw: str, expected: Literal):
        loaded = Literal.load(raw)

        assert loaded == expected

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (
                {"property": "a_boolean", "valueType": "boolean"},
                DemoProperty(property="a_boolean", valueType=Boolean()),
            ),
            (
                {"property": "a_float", "valueType": "float"},
                DemoProperty(property="a_float", valueType=Float()),
            ),
            (
                {"property": "a_class", "valueType": "my_namespace:person"},
                DemoProperty(property="a_class", valueType=ClassEntity(prefix="my_namespace", suffix="person")),
            ),
        ],
    )
    def test_create_property(self, raw: dict[str, Any], expected: DemoProperty):
        loaded = DemoProperty.model_validate(raw)

        assert loaded == expected
        assert loaded.dump() == raw
