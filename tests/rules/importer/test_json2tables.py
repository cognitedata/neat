from cognite.neat.rules import importer
from tests import data


def test_json2rules_power_grid() -> None:
    # Arrange
    json_importer = importer.JSONImporter(data.POWER_GRID_JSON)
    expected_properties = {
        "GeographicalRegion": {"name"},
        "SubGraphicalRegion": {"name", "parent"},
        "Substation": {"name", "parent"},
        "Terminal": {"name", "aliasName", "parent"},
    }

    # Act
    rules = json_importer.to_rules()

    # Assert
    assert not (
        missing := set(rules.classes) - set(expected_properties)
    ), f"JSONImporter did not find classes {missing}"
    properties_by_class = rules.properties.groupby("class_id")
    for class_name, expected in expected_properties.items():
        assert not (
            missing := expected - {prop.property_name for prop in properties_by_class.get(class_name, []).values()}
        ), f"JSONImporter did not find properties {missing} for class {class_name}"
