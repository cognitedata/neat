import pytest
from cognite.client.data_classes.data_modeling import ContainerApplyList, DataModelApply
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


def test_import_information_model(
    power_grid_rules: models.TransformationRules, power_grid_containers: ContainerApplyList
) -> None:
    # Arrange
    information_model = importer.InformationModelImporter(power_grid_containers)

    # Act
    rules = information_model.to_rules()

    # Assert
    assert rules == power_grid_rules


@pytest.mark.skip(reason="Solution model is not implemented yet")
def test_import_solution_model(power_grid_rules, power_grid_containers):
    # Arrange
    solution_model = importer.SolutionModelImporter(power_grid_containers)

    # Act
    rules = solution_model.to_rules()

    # Assert
    assert rules == power_grid_rules
