import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cognite.neat._data_model.models.entities import ParsedEntity, parse_entities, parse_entity
from cognite.neat._data_model.models.entities._parser import SPECIAL_CHARACTERS


class TestEntityParser:
    @pytest.mark.parametrize(
        "entity_str,expected",
        [
            pytest.param(
                "#N/A",
                ParsedEntity("", "#N/A", {}),
                id="Special value as entity name",
            ),
            pytest.param(
                "asset:MyAsset(capacity=100,type=storage)",
                ParsedEntity("asset", "MyAsset", {"capacity": "100", "type": "storage"}),
                id="Entity with properties",
            ),
            pytest.param("MyAsset", ParsedEntity("", "MyAsset", {}), id="Entity without prefix and properties"),
            pytest.param(
                "asset:MyAsset", ParsedEntity("asset", "MyAsset", {}), id="Entity with prefix but no properties"
            ),
            pytest.param(
                "asset:MyAsset(          type=storage   , capacity=100          )",
                ParsedEntity("asset", "MyAsset", {"capacity": "100", "type": "storage"}),
                id="Entity with properties and extra spaces",
            ),
            pytest.param(
                "equipment:Pump1(unit=si:C(m3/s),maxPressure=5000)",
                ParsedEntity("equipment", "Pump1", {"unit": "si:C(m3/s)", "maxPressure": "5000"}),
                id="Entity with complex property values",
            ),
            pytest.param(
                "MyAsset(type=storage)",
                ParsedEntity("", "MyAsset", {"type": "storage"}),
                id="Entity without prefix but with properties",
            ),
            pytest.param(
                "",
                ParsedEntity("", "", {}),
                id="Empty entity string",
            ),
            pytest.param(
                "ny!@#$%^&*_+-{}[]|;:'<>.?/~`Asset(type=storage)",
                ParsedEntity("ny!@#$%^&*_+-{}[]|;", "'<>.?/~`Asset", {"type": "storage"}),
                id="Entity with special characters in name",
            ),
            pytest.param(
                "pump asset:My Asset(flow rate=1000, location=Plant 1)",
                ParsedEntity("pump asset", "My Asset", {"flow rate": "1000", "location": "Plant 1"}),
                id="Entity with spaces in prefix, suffix, and property values",
            ),
            pytest.param(
                "设备:泵1(单位=si:C(m3/s),最大压力=5000)",
                ParsedEntity("设备", "泵1", {"单位": "si:C(m3/s)", "最大压力": "5000"}),
                id="Entity with non-ASCII characters",
            ),
            pytest.param(
                "asset:MyAsset(capacity=100,capacity=200)",
                ParsedEntity("asset", "MyAsset", {"capacity": "200"}),
                id="Entity with duplicate property names (last one wins)",
            ),
            pytest.param(
                "asset:MyAsset(capacity==100)",
                ParsedEntity("asset", "MyAsset", {"capacity": "=100"}),
                id="Double '=' in property",
            ),
            pytest.param(
                "asset:MyAsset(capacity=100,type=storage,)",
                ParsedEntity("asset", "MyAsset", {"capacity": "100", "type": "storage"}),
                id="Trailing comma in properties",
            ),
            pytest.param(
                "asset:MyAsset(storage=high=capacity:Storage(with=redundancy))",
                ParsedEntity("asset", "MyAsset", {"storage": "high=capacity:Storage(with=redundancy)"}),
            ),
            pytest.param(
                '0(""="")',
                ParsedEntity("", "0", {'""': '""'}),
                id="Entity with empty strings as names and values",
            ),
            pytest.param(
                "centrifugal pump:Pump1()",
                ParsedEntity("centrifugal pump", "Pump1", {}),
                id="Empty properties",
            ),
        ],
    )
    def test_parse_entity(self, entity_str: str, expected: ParsedEntity) -> None:
        actual = parse_entity(entity_str)
        assert actual == expected

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
            pytest.param(
                "asset:MyAsset(capacity=100,type=storage)trailing",
                "Unexpected characters after properties at position 40",
                id="Trailing characters after properties",
            ),
            pytest.param(
                "asset:MyAsset(capacity=100,,type=storage)",
                "Expected property name at position 27. Got ','",
                id="Double comma in properties",
            ),
            pytest.param(
                ":",
                "Expected identifier at position 0",
                id="Only colon, missing prefix and suffix",
            ),
            pytest.param(
                "asset:MyAsset(()=())",
                r"Expected property name at position 14. Got '\('",
                id="Parentheses in property name",
            ),
            pytest.param(
                "asset:()",
                "Expected identifier after ':' at position 6",
                id="Missing suffix after prefix",
            ),
        ],
    )
    def test_parse_entity_invalid_format(self, entity_str: str, error_msg: str) -> None:
        with pytest.raises(ValueError, match=error_msg):
            parse_entity(entity_str)

    valid_identifier = st.text(
        alphabet=st.characters(blacklist_characters=SPECIAL_CHARACTERS),
        min_size=0,
        max_size=20,
    ).map(lambda s: s.strip())

    # Strategy for property names (avoid special characters)
    property_name = (
        st.text(
            alphabet=st.characters(blacklist_characters=SPECIAL_CHARACTERS),
            min_size=1,
            max_size=10,
        )
        .map(lambda s: s.strip())
        .filter(lambda s: s != "")
    )

    # Strategy for property values (can be more complex)
    property_value = st.text(alphabet=st.characters(), min_size=0, max_size=20).map(
        lambda s: s.strip().replace(",", "_").replace(")", "_").replace("(", "_")
    )

    # Strategy for generating property dictionaries
    properties = st.dictionaries(keys=property_name, values=property_value, max_size=5)

    @settings(max_examples=3)
    @given(prefix=valid_identifier, suffix=valid_identifier.filter(lambda s: s != ""), props=properties)
    def test_entity_roundtrip(self, prefix: str, suffix: str, props: dict[str, str]) -> None:
        """Test that entity strings can be parsed correctly and reconstruct to original data."""
        # Build entity string from components
        entity_str = prefix
        if prefix:
            entity_str += ":"
        entity_str += suffix

        if props:
            prop_str = ",".join(f"{k}={v}" for k, v in props.items())
            entity_str += f"({prop_str})"

        # Parse and check that we get expected values
        parsed = parse_entity(entity_str)

        assert parsed.prefix == prefix, f"Failed for entity string: {entity_str}"
        assert parsed.suffix == suffix, f"Failed for entity string: {entity_str}"
        assert parsed.properties == props, f"Failed for entity string: {entity_str}"

    @given(entity_str=st.text(min_size=1, max_size=50))
    def test_entity_parser_handles_arbitrary_input(self, entity_str: str) -> None:
        """Test that the parser either successfully parses or raises a clear ValueError."""
        try:
            parsed = parse_entity(entity_str)
            # If parsing succeeded, verify some basic invariants
            if entity_str.strip():
                assert parsed.suffix != "" or entity_str.strip() == ""
        except ValueError as e:
            # Ensure error message is descriptive
            assert str(e)
            assert len(str(e)) > 10

    @pytest.mark.parametrize(
        "entity_str, expected_entities",
        [
            pytest.param(
                "asset:MyAsset(capacity=100,type=storage),equipment:Pump1(unit=si:C(m3/s),maxPressure=5000)",
                [
                    ParsedEntity("asset", "MyAsset", {"capacity": "100", "type": "storage"}),
                    ParsedEntity("equipment", "Pump1", {"unit": "si:C(m3/s)", "maxPressure": "5000"}),
                ],
                id="Multiple entities with properties",
            ),
            pytest.param(
                "MyAsset,AnotherAsset",
                [
                    ParsedEntity("", "MyAsset", {}),
                    ParsedEntity("", "AnotherAsset", {}),
                ],
                id="Multiple entities without prefixes and properties",
            ),
            pytest.param(
                "asset:MyAsset,equipment:Pump1",
                [
                    ParsedEntity("asset", "MyAsset", {}),
                    ParsedEntity("equipment", "Pump1", {}),
                ],
                id="Multiple entities with prefixes but no properties",
            ),
            pytest.param(
                "asset:MyAsset(capacity=100,type=storage) , equipment:Pump1(unit=si:C(m3/s),maxPressure=5000)",
                [
                    ParsedEntity("asset", "MyAsset", {"capacity": "100", "type": "storage"}),
                    ParsedEntity("equipment", "Pump1", {"unit": "si:C(m3/s)", "maxPressure": "5000"}),
                ],
                id="Multiple entities with properties and extra spaces",
            ),
            pytest.param(
                "MyAsset(type=storage),AnotherAsset(location=Plant1)",
                [
                    ParsedEntity("", "MyAsset", {"type": "storage"}),
                    ParsedEntity("", "AnotherAsset", {"location": "Plant1"}),
                ],
                id="Multiple entities without prefixes but with properties",
            ),
            pytest.param(
                "",
                None,
                id="Empty entity string",
            ),
            pytest.param(
                "SingleEntity",
                [ParsedEntity("", "SingleEntity", {})],
                id="Single entity without prefix and properties",
            ),
            pytest.param(
                "asset:MyAsset(capacity=100,type=storage),,equipment:Pump1(unit=si:C(m3/s),maxPressure=5000)",
                [
                    ParsedEntity("asset", "MyAsset", {"capacity": "100", "type": "storage"}),
                    ParsedEntity("equipment", "Pump1", {"unit": "si:C(m3/s)", "maxPressure": "5000"}),
                ],
                id="Double comma between entities",
            ),
            pytest.param(
                "asset:MyAsset(capacity=100,type=storage),equipment:Pump1(unit=si:C(m3/s),maxPressure=5000),",
                [
                    ParsedEntity("asset", "MyAsset", {"capacity": "100", "type": "storage"}),
                    ParsedEntity("equipment", "Pump1", {"unit": "si:C(m3/s)", "maxPressure": "5000"}),
                ],
                id="Trailing comma after last entity",
            ),
            pytest.param(
                "asset:MyAsset(capacity==100),equipment:Pump1(unit=si:C(m3/s),maxPressure=5000)",
                [
                    ParsedEntity("asset", "MyAsset", {"capacity": "=100"}),
                    ParsedEntity("equipment", "Pump1", {"unit": "si:C(m3/s)", "maxPressure": "5000"}),
                ],
                id="Double '=' in property of first entity",
            ),
            pytest.param(
                '0(""=""),1(name=Test)',
                [
                    ParsedEntity("", "0", {'""': '""'}),
                    ParsedEntity("", "1", {"name": "Test"}),
                ],
                id="Entities with empty strings as names and values",
            ),
        ],
    )
    def test_parse_entities(self, entity_str: str, expected_entities: list[ParsedEntity] | None) -> None:
        parsed_entities = parse_entities(entity_str)
        assert parsed_entities == expected_entities

    @pytest.mark.parametrize(
        "entity, expected_str",
        [
            pytest.param(
                ParsedEntity("asset", "MyAsset", {"capacity": "100", "type": "storage"}),
                "asset:MyAsset(capacity=100,type=storage)",
                id="Entity with properties",
            ),
            pytest.param(
                ParsedEntity("", "MyAsset", {}),
                "MyAsset",
                id="Entity without prefix and properties",
            ),
            pytest.param(
                ParsedEntity("asset", "MyAsset", {}),
                "asset:MyAsset",
                id="Entity with prefix but no properties",
            ),
        ],
    )
    def test_entity_str_representation(self, entity: ParsedEntity, expected_str: str) -> None:
        assert str(entity) == expected_str
