import pytest
from cognite.client.data_classes.data_modeling import ContainerApplyList, DataModelApply, ViewApplyList
from yaml import safe_load

from cognite.neat.rules import examples, importer, models, parser


@pytest.fixture(scope="session")
def power_grid_rules() -> models.TransformationRules:
    return parser.parse_rules_from_excel_file(examples.power_grid_model)


@pytest.fixture(scope="session")
def power_grid_containers() -> ContainerApplyList:
    return ContainerApplyList._load(safe_load(examples.power_grid_containers.read_text()))


@pytest.fixture(scope="session")
def power_grid_data_model() -> DataModelApply:
    return DataModelApply.load(safe_load(examples.power_grid_data_model.read_text()))


@pytest.fixture(scope="session")
def power_grid_views(power_grid_data_model: DataModelApply) -> ViewApplyList:
    return ViewApplyList(power_grid_data_model.views)


@pytest.mark.skip(reason="Not implemented")
def test_import_information_model(
    power_grid_rules: models.TransformationRules,
    power_grid_containers: ContainerApplyList,
    power_grid_views: ViewApplyList,
) -> None:
    # Arrange
    information_model = importer.DMSImporter(power_grid_containers, power_grid_views)

    # Act
    rules = information_model.to_rules()

    # Assert
    assert rules == power_grid_rules


def test_import_information_model_missing_container(
    power_grid_containers: ContainerApplyList, power_grid_views: ViewApplyList
) -> None:
    # Act
    with pytest.raises(ValueError) as e:
        importer.DMSImporter(power_grid_containers[1:], power_grid_views)

    # Assert
    assert "Missing containers" in str(e.value)
