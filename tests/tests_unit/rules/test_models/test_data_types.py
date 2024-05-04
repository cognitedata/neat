from typing import Any

import pytest
from pydantic import AnyHttpUrl, BaseModel, Field, field_serializer
from pydantic.networks import Url

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
from cognite.neat.rules.models.entities import ClassEntity, ReferenceEntity, URLEntity


class DemoProperty(BaseModel):
    property_: str = Field(alias="property")
    value_type: DataType | ClassEntity = Field(alias="valueType")
    reference: URLEntity | ReferenceEntity | None = Field(None, alias="Reference", union_mode="left_to_right")

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)

    @field_serializer("reference", when_used="unless-none")
    def as_str(reference: AnyHttpUrl) -> str:
        return str(reference)


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
                {
                    "property": "a_boolean",
                    "valueType": "boolean",
                    "Reference": "power:GeneratingUnit(property=activePower)",
                },
                DemoProperty(
                    property="a_boolean",
                    valueType=Boolean(),
                    Reference=ReferenceEntity(prefix="power", suffix="GeneratingUnit", property="activePower"),
                ),
            ),
            (
                {
                    "property": "a_float",
                    "valueType": "float",
                    "Reference": "http://www.w3.org/2003/01/geo/wgs84_pos#location",
                },
                DemoProperty(
                    property="a_float",
                    valueType=Float(),
                    Reference=Url("http://www.w3.org/2003/01/geo/wgs84_pos#location"),
                ),
            ),
            (
                {
                    "property": "a_class",
                    "valueType": "my_namespace:person",
                    "Reference": "another_namespace:GeneratingUnit",
                },
                DemoProperty(
                    property="a_class",
                    valueType=ClassEntity(prefix="my_namespace", suffix="person"),
                    Reference=ReferenceEntity(prefix="another_namespace", suffix="GeneratingUnit"),
                ),
            ),
            (
                {
                    "property": "a_class_versioned",
                    "valueType": "my_namespace:person(version=1)",
                    "Reference": "power:GeneratingUnit",
                },
                DemoProperty(
                    property="a_class_versioned",
                    valueType=ClassEntity(prefix="my_namespace", suffix="person", version="1"),
                    Reference=ReferenceEntity(prefix="power", suffix="GeneratingUnit"),
                ),
            ),
        ],
    )
    def test_create_property(self, raw: dict[str, Any], expected: DemoProperty):
        loaded = DemoProperty.model_validate(raw)

        assert loaded == expected
        assert loaded.dump() == raw
