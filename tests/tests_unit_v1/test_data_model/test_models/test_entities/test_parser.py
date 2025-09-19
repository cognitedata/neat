import pytest

from cognite.neat.data_model.models.entities._parser import parse_entity


class TestEntityParser:
    @pytest.mark.parametrize(
        "entity_str, prefix, suffix, properties",
        [
            pytest.param(
                "asset:MyAsset(capacity=100,type=storage)",
                "asset",
                "MyAsset",
                {"capacity": "100", "type": "storage"},
                id="Entity with properties",
            ),
            pytest.param("MyAsset", "", "MyAsset", {}, id="Entity without prefix and properties"),
            pytest.param("asset:MyAsset", "asset", "MyAsset", {}, id="Entity with prefix but no properties"),
            pytest.param(
                "asset:MyAsset(          type=storage   , capacity=100          )",
                "asset",
                "MyAsset",
                {"capacity": "100", "type": "storage"},
                id="Entity with properties and extra spaces",
            ),
        ],
    )
    def test_parse_entity(self, entity_str: str, prefix: str, suffix: str, properties: dict[str, str]) -> None:
        parsed_prefix, parsed_suffix, parsed_properties = parse_entity(entity_str)
        assert parsed_prefix == prefix
        assert parsed_suffix == suffix
        assert parsed_properties == properties
