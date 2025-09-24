from collections import Counter
from typing import Any

import pytest
from pydantic import BaseModel, Field

from cognite.neat.v0.core._data_model.models.data_types import (
    Boolean,
    DataType,
    Double,
    Float,
    Integer,
    NonNegativeInteger,
    NonPositiveInteger,
)
from cognite.neat.v0.core._data_model.models.entities import ConceptEntity, UnitEntity


class DemoProperty(BaseModel):
    property_: str = Field(alias="property")
    value_type: DataType | ConceptEntity = Field(alias="valueType")

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)


class TestDataTypes:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (
                "float(unit=power:megaw)",
                Float(unit=UnitEntity(prefix="power", suffix="megaw")),
            ),
            (
                "double(unit=length:m)",
                Double(unit=UnitEntity(prefix="length", suffix="m")),
            ),
            ("boolean", Boolean()),
            ("float", Float()),
            ("double", Double()),
            ("integer", Integer()),
            ("nonPositiveInteger", NonPositiveInteger()),
            ("nonNegativeInteger", NonNegativeInteger()),
        ],
    )
    def test_load(self, raw: str, expected: DataType):
        loaded = DataType.load(raw)
        assert loaded == expected
        assert loaded.model_dump() == raw
        assert str(loaded) == raw

    def test_set_unit(self) -> None:
        unit = UnitEntity(prefix="power", suffix="megaw")
        float_ = Float(unit=unit)

        assert float_.unit == unit

    def test_with_without_unit_not_equal(self) -> None:
        float_ = Float()
        float_with_unit = Float(unit=UnitEntity(prefix="power", suffix="megaw"))

        assert float_ != float_with_unit

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (
                {
                    "property": "a_boolean",
                    "valueType": "boolean",
                },
                DemoProperty(
                    property="a_boolean",
                    valueType=Boolean(),
                ),
            ),
            (
                {
                    "property": "a_float",
                    "valueType": "float",
                },
                DemoProperty(
                    property="a_float",
                    valueType=Float(),
                ),
            ),
            (
                {
                    "property": "a_class",
                    "valueType": "my_namespace:person",
                },
                DemoProperty(
                    property="a_class",
                    valueType=ConceptEntity(prefix="my_namespace", suffix="person"),
                ),
            ),
            (
                {
                    "property": "a_class_versioned",
                    "valueType": "my_namespace:person(version=1)",
                },
                DemoProperty(
                    property="a_class_versioned",
                    valueType=ConceptEntity(prefix="my_namespace", suffix="person", version="1"),
                ),
            ),
        ],
    )
    def test_create_property(self, raw: dict[str, Any], expected: DemoProperty):
        loaded = DemoProperty.model_validate(raw)

        assert loaded == expected
        assert loaded.dump() == raw

    def test_unique_names(self) -> None:
        counted = Counter(cls_.model_fields["name"].default for cls_ in DataType.__subclasses__())

        duplicates = {name for name, count in counted.items() if count > 1}

        assert not duplicates, f"Duplicate names found: {duplicates}"
