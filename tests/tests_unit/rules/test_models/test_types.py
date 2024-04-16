import pytest
from cognite.client.data_classes.data_modeling import DataModelId, PropertyId, ViewId

from cognite.neat.rules.models._rules._types import DataModelEntity, ReferenceEntity, ViewPropEntity


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
                "test:TestGraphQL1(version=3, property=prop1)",
                ViewPropEntity(prefix="test", suffix="TestGraphQL1", version="3", property_="prop1"),
                PropertyId(ViewId("test", "TestGraphQL1", "3"), "prop1"),
                id="Prefix, suffix, version and prop",
            ),
            pytest.param(
                "test:TestGraphQL1(property=prop1)",
                ViewPropEntity(prefix="test", suffix="TestGraphQL1", version=None, property_="prop1"),
                PropertyId(ViewId("test", "TestGraphQL1", "default_version"), "prop1"),
                id="Prefix, suffix and prop. Skip version",
            ),
        ],
    )
    def test_from_raw(self, raw: str, expected: ViewPropEntity, expected_id: PropertyId) -> None:
        actual = ViewPropEntity.from_raw(raw)

        assert actual == expected
        assert actual.as_prop_id("default_space", "default_version") == expected_id


class TestReferenceType:
    @pytest.mark.parametrize(
        "raw, expected,",
        [
            pytest.param(
                "test:TestGraphQL1(version=3, property=prop1)",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version="3", property_="prop1"),
                id="Prefix, suffix, version and prop",
            ),
            pytest.param(
                "test:TestGraphQL1(property=prop1)",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version=None, property_="prop1"),
                id="Prefix, suffix and prop. Skip version",
            ),
            pytest.param(
                "test:TestGraphQL1(test:prop1)",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version=None, property_="prop1"),
                id="Prefix, suffix and prop. Skip version",
            ),
            pytest.param(
                "test:TestGraphQL1",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version=None, property_=None),
                id="Prefix, suffix and prop. Skip version",
            ),
        ],
    )
    def test_from_raw(self, raw: str, expected: ViewPropEntity) -> None:
        actual = ReferenceEntity.from_raw(raw)
        assert actual == expected
