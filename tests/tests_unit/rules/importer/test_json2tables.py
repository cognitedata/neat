from cognite.neat.legacy.rules import importers
from tests import data


def test_json2rules_power_grid() -> None:
    # Arrange
    json_importer = importers.ArbitraryJSONImporter(data.POWER_GRID_JSON, "child-to-parent")
    expected_properties = {
        "GeographicalRegion": {"name"},
        "SubGraphicalRegion": {"name", "parent"},
        "Substation": {"name", "parent"},
        "Terminal": {"name", "aliasName", "parent"},
    }

    # Act
    rules = json_importer.to_rules()

    # Assert
    missing = set(rules.classes) - set(expected_properties)
    assert not missing, f"JSONImporter did not find classes {missing}"
    properties_by_class = rules.properties.groupby("class_id")
    for class_name, expected in expected_properties.items():
        missing = expected - {prop.property_name for prop in properties_by_class.get(class_name, []).values()}
        assert not missing, f"JSONImporter did not find properties {missing} for class {class_name}"
