import pytest
from cognite.client.data_classes.data_modeling import DataModelId, PropertyId, ViewId

from cognite.neat.rules.models._rules._types import DataModelEntity, Undefined, ViewPropEntity


class TestDataModelEntity:
    @pytest.mark.parametrize(
        "raw, expected, expected_id",
        [
            (
                "test:TestGraphQL1(version=3)",
                DataModelEntity(prefix="test", suffix="TestGraphQL1", version="3"),
                DataModelId("test", "TestGraphQL1", "3"),
            ),
            (
                "test:TestGraphQL1",
                DataModelEntity(prefix="test", suffix="TestGraphQL1", version=None),
                DataModelId("test", "TestGraphQL1", None),
            ),
        ],
    )
    def test_from_raw(self, raw: str, expected: DataModelEntity, expected_id: DataModelId) -> None:
        actual = DataModelEntity.from_raw(raw)

        assert actual == expected
        assert actual.as_id() == expected_id


class TestViewPropEntity:
    @pytest.mark.parametrize(
        "raw, expected, expected_id",
        [
            pytest.param(
                "test:TestGraphQL1(version=3):prop1",
                ViewPropEntity(prefix="test", suffix="TestGraphQL1", version="3", property_="prop1"),
                PropertyId(ViewId("test", "TestGraphQL1", "3"), "prop1"),
                id="Prefix, suffix, version and prop",
            ),
            pytest.param(
                "test:TestGraphQL1:prop1",
                ViewPropEntity(prefix="test", suffix="TestGraphQL1", version=None, property_="prop1"),
                PropertyId(ViewId("test", "TestGraphQL1", "default_version"), "prop1"),
                id="Prefix, suffix and prop. Skip version",
            ),
            pytest.param(
                "TestGraphQL1:prop1",
                ViewPropEntity(prefix=Undefined, suffix="TestGraphQL1", version=None, property_="prop1"),
                PropertyId(ViewId("default_space", "TestGraphQL1", "default_version"), "prop1"),
                id="Only suffix and prop",
            ),
        ],
    )
    def test_from_raw(self, raw: str, expected: ViewPropEntity, expected_id: PropertyId) -> None:
        actual = ViewPropEntity.from_raw(raw)

        assert actual == expected
        assert actual.as_prop_id("default_space", "default_version", standardize_casing=False) == expected_id
