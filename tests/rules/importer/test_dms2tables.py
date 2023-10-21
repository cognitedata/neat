import pytest
from cognite.client.data_classes.data_modeling import DataModel, DataModelApply, View, ViewList
from yaml import safe_load

from cognite.neat.rules import examples, importer, models, parser


@pytest.fixture(scope="session")
def power_grid_rules() -> models.TransformationRules:
    return parser.parse_rules_from_excel_file(examples.power_grid_model)


@pytest.fixture(scope="session")
def power_grid_data_model() -> DataModel[View]:
    return DataModel.load(safe_load(examples.power_grid_data_model.read_text()))


@pytest.fixture(scope="session")
def power_grid_views(power_grid_data_model: DataModelApply) -> ViewList:
    return ViewList(power_grid_data_model.views)


def test_import_information_model(power_grid_rules: models.TransformationRules, power_grid_views: ViewList) -> None:
    # Arrange
    dms_importer = importer.DMSImporter(power_grid_views)

    # Act
    rules = dms_importer.to_rules()

    # Assert
    assert sorted(rules.classes.keys()) == sorted(power_grid_rules.classes.keys())
    assert sorted((prop.class_id, prop.property_name) for prop in rules.properties.values()) == sorted(
        [(prop.class_id, prop.property_name) for prop in power_grid_rules.properties.values()]
        # The powerrules example lacks a circular dependency which was
        # added to the data model to demonstrate the FDM capability
        + [("GeographicalRegion", "subRegions")]
    )
