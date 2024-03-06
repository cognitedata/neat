import pytest
from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat.rules.models._rules._types import DataModelEntity


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
