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
            pytest.param(
                "equipment:Pump1(unit=si:C(m3/s),maxPressure=5000)",
                "equipment",
                "Pump1",
                {"unit": "si:C(m3/s)", "maxPressure": "5000"},
                id="Entity with complex property values",
            ),
            pytest.param(
                "MyAsset(type=storage)",
                "",
                "MyAsset",
                {"type": "storage"},
                id="Entity without prefix but with properties",
            ),
            pytest.param(
                "",
                "",
                "",
                {},
                id="Empty entity string",
            ),
        ],
    )
    def test_parse_entity(self, entity_str: str, prefix: str, suffix: str, properties: dict[str, str]) -> None:
        parsed_prefix, parsed_suffix, parsed_properties = parse_entity(entity_str)
        assert parsed_prefix == prefix
        assert parsed_suffix == suffix
        assert parsed_properties == properties

    @pytest.mark.parametrize(
        "entity_str, error_msg",
        [
            pytest.param(
                "asset:MyAsset(capacity100,type=storage)",
                "Expected '=' after property name 'capacity100' at position 25",
                id="Missing '=' in property",
            ),
            pytest.param(
                "asset:MyAsset(capacity=100,type)",
                "Expected '=' after property name 'type' at position 31",
                id="Missing value in property",
            ),
            pytest.param(
                "asset:MyAsset(capacity=100,type=storage",
                r"Expected '\)' to close properties at position 39",
                id="Missing closing parenthesis",
            ),
        ],
    )
    def test_parse_entity_invalid_format(self, entity_str: str, error_msg: str) -> None:
        with pytest.raises(ValueError, match=error_msg):
            parse_entity(entity_str)
